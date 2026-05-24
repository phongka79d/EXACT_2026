"""Compact parse-frame extractor with repair, retry, and cache behavior."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.config.redaction import redact_secret
from app.logic.frames import ParseFrame, parse_frame
from app.logic.validation import validate_parse_frame

from .client import OpenAICompatibleChatClient
from .errors import FrameExtractionError, LLMResponseError, LLMTransientError
from .prompts import (
    EXTRACTOR_VERSION,
    PROMPT_VERSION,
    build_candidate_frame_messages,
    build_premise_frame_messages,
    build_repair_frame_messages,
)

REFERENCE_ONLY_INPUT_KEYS = frozenset({"premises-fol", "premises_fol", "answer", "explanation", "idx"})
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


@dataclass(frozen=True)
class FrameExtractionInput:
    mode: Literal["premise", "candidate"]
    source_id: str
    source_text: str
    premise_id: int | None = None
    candidate_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("FrameExtractionInput.source_id must be non-empty")
        if not self.source_text.strip():
            raise ValueError("FrameExtractionInput.source_text must be non-empty")
        if self.mode == "premise" and self.premise_id is None:
            raise ValueError("Premise frame extraction requires premise_id")
        if self.mode == "candidate" and not (self.candidate_label and self.candidate_label.strip()):
            raise ValueError("Candidate frame extraction requires candidate_label")
        assert_runtime_safe_metadata(self.metadata)


@dataclass(frozen=True)
class FrameExtractionResult:
    frame: ParseFrame
    raw_content: str
    raw_payload: dict[str, Any]
    cache_key: str
    diagnostics: dict[str, Any]


class ChatCompletionClient(Protocol):
    model: str
    sanitized_endpoint: str
    api_key_for_redaction: str

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


class FrameExtractor(Protocol):
    async def extract_frame(self, request: FrameExtractionInput) -> FrameExtractionResult: ...


class MockFrameExtractor:
    """Deterministic extractor used in unit tests and offline fixtures."""

    def __init__(
        self,
        *,
        responses: Mapping[str, ParseFrame | Mapping[str, Any]] | None = None,
        default_response: ParseFrame | Mapping[str, Any] | None = None,
    ):
        self._responses = dict(responses or {})
        self._default = default_response

    async def extract_frame(self, request: FrameExtractionInput) -> FrameExtractionResult:
        payload_or_frame = self._responses.get(request.source_id, self._default)
        if payload_or_frame is None:
            raise FrameExtractionError(
                f"No mock frame response configured for source_id={request.source_id!r}",
                diagnostics={"model": "mock", "cache_hit": False},
            )

        frame, raw_payload = _coerce_frame(payload_or_frame)
        cache_key = build_frame_cache_key(
            request,
            model="mock",
            prompt_version="mock",
            extractor_version="mock",
        )
        return FrameExtractionResult(
            frame=frame,
            raw_content=json.dumps(raw_payload, ensure_ascii=True),
            raw_payload=raw_payload,
            cache_key=cache_key,
            diagnostics={
                "model": "mock",
                "prompt_version": "mock",
                "extractor_version": "mock",
                "attempts": 1,
                "repair_count": 0,
                "retry_count": 0,
                "cache_hit": False,
                "errors": [],
            },
        )


class LLMFrameExtractor:
    """Runtime frame extractor with strict validation and repair loop."""

    def __init__(
        self,
        client: ChatCompletionClient,
        *,
        prompt_version: str = PROMPT_VERSION,
        extractor_version: str = EXTRACTOR_VERSION,
        max_attempts: int = 3,
        max_repairs: int = 1,
        max_tokens: int = 512,
        base_backoff_seconds: float = 0.2,
        jitter_seconds: float = 0.05,
        cache: dict[str, tuple[ParseFrame, dict[str, Any], str]] | None = None,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_generator: random.Random | None = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if max_repairs < 0:
            raise ValueError("max_repairs must be >= 0")
        self._client = client
        self._prompt_version = prompt_version
        self._extractor_version = extractor_version
        self._max_attempts = max_attempts
        self._max_repairs = max_repairs
        self._max_tokens = max_tokens
        self._base_backoff_seconds = base_backoff_seconds
        self._jitter_seconds = jitter_seconds
        self._cache = cache if cache is not None else {}
        self._sleep = sleep_func
        self._random = random_generator or random.Random(0)

    async def extract_frame(self, request: FrameExtractionInput) -> FrameExtractionResult:
        cache_key = build_frame_cache_key(
            request,
            model=self._client.model,
            prompt_version=self._prompt_version,
            extractor_version=self._extractor_version,
        )

        if cache_key in self._cache:
            cached_frame, cached_payload, cached_raw_content = self._cache[cache_key]
            return FrameExtractionResult(
                frame=cached_frame,
                raw_payload=dict(cached_payload),
                raw_content=cached_raw_content,
                cache_key=cache_key,
                diagnostics=self._build_diagnostics(
                    attempts=0,
                    repair_count=0,
                    retry_count=0,
                    cache_hit=True,
                    errors=[],
                ),
            )

        messages = self._build_initial_messages(request)
        total_attempts = 0
        total_retries = 0
        repair_count = 0
        errors: list[str] = []

        while True:
            try:
                content, call_attempts, call_retries = await self._call_model_with_retry(messages)
                total_attempts += call_attempts
                total_retries += call_retries
            except (LLMTransientError, LLMResponseError) as exc:
                sanitized = _sanitize_error_message(str(exc), api_key=self._client.api_key_for_redaction)
                diagnostics = self._build_diagnostics(
                    attempts=total_attempts + 1,
                    repair_count=repair_count,
                    retry_count=total_retries,
                    cache_hit=False,
                    errors=[*errors, sanitized],
                    failure_type="provider_error",
                )
                raise FrameExtractionError("Model call failed during frame extraction", diagnostics=diagnostics) from exc

            try:
                payload = _parse_json_object(content)
                payload = _normalize_model_payload(payload, request)
                frame = parse_frame(payload)
                validate_parse_frame(frame)
            except (json.JSONDecodeError, ValueError) as exc:
                sanitized = _sanitize_error_message(str(exc), api_key=self._client.api_key_for_redaction)
                errors.append(sanitized)
                if repair_count >= self._max_repairs:
                    diagnostics = self._build_diagnostics(
                        attempts=total_attempts,
                        repair_count=repair_count,
                        retry_count=total_retries,
                        cache_hit=False,
                        errors=errors,
                        failure_type="frame_validation_error",
                    )
                    raise FrameExtractionError(
                        "Frame extraction failed after repair attempts",
                        diagnostics=diagnostics,
                    ) from exc

                repair_count += 1
                messages = build_repair_frame_messages(
                    source_text=request.source_text,
                    source_id=request.source_id,
                    premise_id=request.premise_id,
                    candidate_label=request.candidate_label,
                    frame_mode=request.mode,
                    validation_error=sanitized,
                )
                continue

            self._cache[cache_key] = (frame, dict(payload), content)
            return FrameExtractionResult(
                frame=frame,
                raw_payload=dict(payload),
                raw_content=content,
                cache_key=cache_key,
                diagnostics=self._build_diagnostics(
                    attempts=total_attempts,
                    repair_count=repair_count,
                    retry_count=total_retries,
                    cache_hit=False,
                    errors=errors,
                ),
            )

    def _build_initial_messages(self, request: FrameExtractionInput) -> list[dict[str, str]]:
        if request.mode == "premise":
            assert request.premise_id is not None
            return build_premise_frame_messages(
                source_text=request.source_text,
                source_id=request.source_id,
                premise_id=request.premise_id,
            )
        assert request.candidate_label is not None
        return build_candidate_frame_messages(
            source_text=request.source_text,
            source_id=request.source_id,
            candidate_label=request.candidate_label,
        )

    async def _call_model_with_retry(self, messages: list[dict[str, str]]) -> tuple[str, int, int]:
        attempt = 0
        retry_count = 0
        while True:
            attempt += 1
            try:
                content = await self._client.complete(messages, temperature=0.0, max_tokens=self._max_tokens)
                return content, attempt, retry_count
            except LLMTransientError:
                if attempt >= self._max_attempts:
                    raise
                retry_count += 1
                delay = self._backoff_delay_seconds(attempt)
                await self._sleep(delay)
            except LLMResponseError:
                raise

    def _backoff_delay_seconds(self, attempt: int) -> float:
        base = self._base_backoff_seconds * (2 ** (attempt - 1))
        jitter = self._random.random() * self._jitter_seconds
        return base + jitter

    def _build_diagnostics(
        self,
        *,
        attempts: int,
        repair_count: int,
        retry_count: int,
        cache_hit: bool,
        errors: list[str],
        failure_type: str | None = None,
    ) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {
            "model": self._client.model,
            "prompt_version": self._prompt_version,
            "extractor_version": self._extractor_version,
            "attempts": attempts,
            "repair_count": repair_count,
            "retry_count": retry_count,
            "cache_hit": cache_hit,
            "errors": list(errors),
            "endpoint": self._client.sanitized_endpoint,
        }
        if failure_type is not None:
            diagnostics["failure_type"] = failure_type
        return diagnostics


def build_default_llm_frame_extractor(
    env_path: str = ".env",
    *,
    timeout_seconds: float = 20.0,
    max_attempts: int = 3,
    max_repairs: int = 1,
) -> LLMFrameExtractor:
    client = OpenAICompatibleChatClient.from_env(env_path=env_path, timeout_seconds=timeout_seconds)
    return LLMFrameExtractor(client=client, max_attempts=max_attempts, max_repairs=max_repairs)


def build_frame_cache_key(
    request: FrameExtractionInput,
    *,
    model: str,
    prompt_version: str,
    extractor_version: str,
) -> str:
    normalized_text = " ".join(request.source_text.split())
    material = "\n".join(
        (
            request.mode,
            normalized_text,
            prompt_version.strip(),
            extractor_version.strip(),
            model.strip(),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"frame:{digest}"


def assert_runtime_safe_metadata(metadata: Mapping[str, Any]) -> None:
    violations: list[str] = []

    def walk(value: Any, path: list[str]) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                normalized = key_text.strip().lower()
                if normalized in REFERENCE_ONLY_INPUT_KEYS:
                    violations.append(".".join([*path, key_text]))
                walk(item, [*path, key_text])
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, [*path, str(index)])

    walk(metadata, [])
    if violations:
        joined = ", ".join(sorted(violations))
        raise ValueError(f"Frame extractor metadata contains reference-only fields: {joined}")


def _coerce_frame(payload_or_frame: ParseFrame | Mapping[str, Any]) -> tuple[ParseFrame, dict[str, Any]]:
    if isinstance(payload_or_frame, Mapping):
        payload = dict(payload_or_frame)
        frame = parse_frame(payload)
    else:
        frame = payload_or_frame
        payload = _frame_to_payload(frame)
    validate_parse_frame(frame)
    return frame, payload


def _frame_to_payload(frame: ParseFrame) -> dict[str, Any]:
    if hasattr(frame, "__dict__"):
        payload = dict(frame.__dict__)
        if "if_slots" in payload:
            payload["if"] = payload.pop("if_slots")
        if "then_slots" in payload:
            payload["then"] = payload.pop("then_slots")
        return json.loads(json.dumps(payload, default=_json_fallback))
    raise TypeError(f"Unsupported frame object type: {type(frame)!r}")


def _json_fallback(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return value.__dict__
    raise TypeError(f"Value is not JSON serializable: {type(value)!r}")


def _parse_json_object(content: str) -> dict[str, Any]:
    parsed: Any
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(content)
        if extracted is None:
            raise
        parsed = json.loads(extracted)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed


def _sanitize_error_message(message: str, *, api_key: str | None) -> str:
    compact = " ".join(message.split())
    sanitized = compact
    if api_key:
        sanitized = sanitized.replace(api_key, redact_secret(api_key))
    sanitized = _BEARER_RE.sub(f"Bearer {redact_secret('token')}", sanitized)
    if len(sanitized) <= 240:
        return sanitized
    return f"{sanitized[:240]}..."


def _extract_first_json_object(content: str) -> str | None:
    text = content.strip()
    if not text:
        return None

    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _normalize_model_payload(payload: dict[str, Any], request: FrameExtractionInput) -> dict[str, Any]:
    normalized = dict(payload)
    frame_payload = normalized.get("frame")
    if isinstance(frame_payload, Mapping):
        normalized = dict(frame_payload)

    if "if_slots" in normalized and "if" not in normalized:
        normalized["if"] = normalized.pop("if_slots")
    if "then_slots" in normalized and "then" not in normalized:
        normalized["then"] = normalized.pop("then_slots")

    kind = normalized.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        if "facts" in normalized:
            normalized["kind"] = "fact"
        elif "if" in normalized and "then" in normalized:
            normalized["kind"] = "rule"
        elif "claim" in normalized:
            normalized["kind"] = "claim"

    if not isinstance(normalized.get("warnings"), list):
        normalized["warnings"] = []

    if request.mode == "premise":
        normalized.setdefault("source_id", request.source_id)
        normalized.setdefault("source_text", request.source_text)
        normalized.setdefault("premise_id", request.premise_id)
    else:
        normalized.setdefault("source_id", request.source_id)
        normalized.setdefault("source_text", request.source_text)
        normalized.setdefault("candidate_label", request.candidate_label)

    default_entity = normalized.get("entity")

    kind_text = normalized.get("kind")
    if kind_text == "fact":
        normalized["facts"] = _normalize_slot_collection(normalized.get("facts"), default_entity=default_entity)
    elif kind_text == "rule":
        normalized["if"] = _normalize_slot_collection(normalized.get("if"), default_entity=default_entity)
        normalized["then"] = _normalize_slot_collection(normalized.get("then"), default_entity=default_entity)
        normalized.setdefault("scope", "entities")
    elif kind_text == "claim":
        claim_value = normalized.get("claim")
        if isinstance(claim_value, Mapping):
            normalized["claim"] = _normalize_slot(dict(claim_value), default_entity=default_entity)
        normalized.setdefault("answer_type", "claim")

    return normalized


def _normalize_slot_collection(value: Any, *, default_entity: Any) -> list[Any]:
    if isinstance(value, Mapping):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    normalized_items: list[Any] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized_items.append(_normalize_slot(dict(item), default_entity=default_entity))
        else:
            normalized_items.append(item)
    return normalized_items


def _normalize_slot(slot: dict[str, Any], *, default_entity: Any) -> dict[str, Any]:
    normalized = dict(slot)

    slot_type = normalized.get("type")
    if not isinstance(slot_type, str) or not slot_type.strip():
        normalized["type"] = _infer_slot_type(normalized)
        slot_type = normalized.get("type")

    if normalized.get("type") == "predicate" and "entity" not in normalized and isinstance(default_entity, str):
        normalized["entity"] = default_entity

    if normalized.get("type") in {"numeric_condition", "numeric_value"}:
        if "entity" not in normalized and isinstance(default_entity, str):
            normalized["entity"] = default_entity

    expression = normalized.get("expression")
    if isinstance(expression, Mapping):
        normalized["expression"] = _normalize_slot(dict(expression), default_entity=default_entity)

    operands = normalized.get("operands")
    if normalized.get("type") == "arithmetic_expression" and isinstance(operands, Mapping):
        normalized["operands"] = [operands]

    return normalized


def _infer_slot_type(slot: Mapping[str, Any]) -> str:
    if {"subject", "relation", "object"}.issubset(slot.keys()):
        return "entity_relation"
    if "op" in slot and "operands" in slot:
        return "arithmetic_expression"
    if "attribute" in slot and "op" in slot:
        return "numeric_condition"
    if "attribute" in slot and "value" in slot:
        return "numeric_value"
    if "name" in slot:
        return "predicate"
    return ""
