"""Compact parse-frame extractor with repair, retry, and cache behavior."""

from __future__ import annotations

import asyncio
import ast
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.config.redaction import redact_secret
from app.logic.frames import ParseFrame, parse_frame
from app.logic.validation import validate_parse_frame
from app.tracing import write_parser_replay_jsonl

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
_FRAME_EVENTS_PATH = Path("artifacts/frame_events.jsonl")
_RULE_IF_ALIASES = (
    "conditions",
    "condition",
    "antecedents",
    "antecedent",
    "requirements",
    "requirement",
    "prerequisites",
    "prerequisite",
    "given",
    "given_that",
    "when",
)
_RULE_THEN_ALIASES = (
    "consequences",
    "consequence",
    "consequents",
    "consequent",
    "results",
    "result",
    "outcomes",
    "outcome",
    "conclusions",
    "conclusion",
    "effects",
    "effect",
)
_PREDICATE_NAME_ALIASES = ("predicate", "property", "attribute", "state", "trait", "category", "label")
_RELATION_NAME_ALIASES = ("relation_type", "name", "predicate", "property", "attribute")
_NUMERIC_ATTRIBUTE_ALIASES = ("name", "metric", "measure", "field", "property", "score_type", "quantity")
_NUMERIC_VALUE_ALIASES = ("number", "amount", "score", "quantity_value", "numeric_value")
_NUMERIC_OPERATOR_ALIASES = ("operator", "comparison", "comparator")


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
                self._append_raw_response_event(request, cache_key=cache_key, raw_content=content)
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
                self._write_parser_replay_fixture(
                    request=request,
                    cache_key=cache_key,
                    raw_content=None,
                    diagnostics=diagnostics,
                    error_message=sanitized,
                )
                raise FrameExtractionError("Model call failed during frame extraction", diagnostics=diagnostics) from exc

            try:
                payload = _parse_json_object(content)
                payload, normalization_warnings = _normalize_model_payload(payload, request)
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
                    self._write_parser_replay_fixture(
                        request=request,
                        cache_key=cache_key,
                        raw_content=content,
                        diagnostics=diagnostics,
                        error_message=sanitized,
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
                    normalization_warnings=normalization_warnings,
                ),
            )

    def _append_raw_response_event(self, request: FrameExtractionInput, *, cache_key: str, raw_content: str) -> None:
        _append_frame_event(
            _FRAME_EVENTS_PATH,
            "raw_response",
            {
                "source_id": request.source_id,
                "source_text": request.source_text,
                "premise_id": request.premise_id,
                "candidate_label": request.candidate_label,
                "frame_mode": request.mode,
                "cache_key_hash": hashlib.sha256(cache_key.encode("utf-8")).hexdigest(),
                "model": self._client.model,
                "prompt_version": self._prompt_version,
                "extractor_version": self._extractor_version,
                "raw_response": raw_content,
            },
        )

    def _write_parser_replay_fixture(
        self,
        *,
        request: FrameExtractionInput,
        cache_key: str,
        raw_content: str | None,
        diagnostics: Mapping[str, Any],
        error_message: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        replay_path = Path("artifacts") / f"parser_replay_{timestamp}.jsonl"
        payload = {
            "source_id": request.source_id,
            "source_text": request.source_text,
            "premise_id": request.premise_id,
            "candidate_label": request.candidate_label,
            "frame_mode": request.mode,
            "cache_key_hash": hashlib.sha256(cache_key.encode("utf-8")).hexdigest(),
            "model": diagnostics.get("model"),
            "prompt_version": diagnostics.get("prompt_version"),
            "extractor_version": diagnostics.get("extractor_version"),
            "failure_type": diagnostics.get("failure_type"),
            "attempts": diagnostics.get("attempts"),
            "repair_count": diagnostics.get("repair_count"),
            "retry_count": diagnostics.get("retry_count"),
            "errors": list(diagnostics.get("errors", [])),
            "error_message": error_message,
            "raw_response": raw_content,
        }
        write_parser_replay_jsonl(replay_path, [payload])

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
        normalization_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_warnings = sorted(set(normalization_warnings or []))
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
            "normalization_applied": bool(normalized_warnings),
            "normalization_warnings": normalized_warnings,
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
    try:
        parsed = _loads_json_or_literal_object(content)
    except (json.JSONDecodeError, ValueError, SyntaxError) as exc:
        extracted = _extract_first_json_object(content)
        if extracted is None:
            raise ValueError("Model output must contain a parseable JSON object") from exc
        try:
            parsed = _loads_json_or_literal_object(extracted)
        except (json.JSONDecodeError, ValueError, SyntaxError) as extracted_exc:
            raise ValueError("Model output must contain a parseable JSON object") from extracted_exc
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed


def _loads_json_or_literal_object(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return ast.literal_eval(content)


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


def _append_frame_event(path: str | Path, event: str, payload: Mapping[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"event": event, "payload": dict(payload)}
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def _normalize_model_payload(payload: dict[str, Any], request: FrameExtractionInput) -> tuple[dict[str, Any], list[str]]:
    normalization_warnings: list[str] = []
    normalized = dict(payload)
    frame_payload = normalized.get("frame")
    if isinstance(frame_payload, Mapping):
        normalized = dict(frame_payload)
        _add_normalization_warning(normalization_warnings, "frame_wrapper_unwrapped")

    if "if_slots" in normalized and "if" not in normalized:
        normalized["if"] = normalized.pop("if_slots")
        _add_normalization_warning(normalization_warnings, "if_slots_renamed")
    if "then_slots" in normalized and "then" not in normalized:
        normalized["then"] = normalized.pop("then_slots")
        _add_normalization_warning(normalization_warnings, "then_slots_renamed")

    _promote_slot_alias(
        normalized,
        target_key="if",
        aliases=_RULE_IF_ALIASES,
        warning_prefix="rule_if_alias",
        normalization_warnings=normalization_warnings,
    )
    _promote_slot_alias(
        normalized,
        target_key="then",
        aliases=_RULE_THEN_ALIASES,
        warning_prefix="rule_then_alias",
        normalization_warnings=normalization_warnings,
    )

    kind = normalized.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        if "facts" in normalized:
            normalized["kind"] = "fact"
            _add_normalization_warning(normalization_warnings, "kind_inferred:fact")
        elif "if" in normalized and "then" in normalized:
            normalized["kind"] = "rule"
            _add_normalization_warning(normalization_warnings, "kind_inferred:rule")
        elif "claim" in normalized:
            normalized["kind"] = "claim"
            _add_normalization_warning(normalization_warnings, "kind_inferred:claim")

    if not isinstance(normalized.get("warnings"), list):
        normalized["warnings"] = []
        _add_normalization_warning(normalization_warnings, "warnings_defaulted")

    if request.mode == "premise":
        if "source_id" not in normalized:
            normalized["source_id"] = request.source_id
            _add_normalization_warning(normalization_warnings, "source_id_defaulted")
        if "source_text" not in normalized:
            normalized["source_text"] = request.source_text
            _add_normalization_warning(normalization_warnings, "source_text_defaulted")
        if "premise_id" not in normalized:
            normalized["premise_id"] = request.premise_id
            _add_normalization_warning(normalization_warnings, "premise_id_defaulted")
    else:
        if "source_id" not in normalized:
            normalized["source_id"] = request.source_id
            _add_normalization_warning(normalization_warnings, "source_id_defaulted")
        if "source_text" not in normalized:
            normalized["source_text"] = request.source_text
            _add_normalization_warning(normalization_warnings, "source_text_defaulted")
        if "candidate_label" not in normalized:
            normalized["candidate_label"] = request.candidate_label
            _add_normalization_warning(normalization_warnings, "candidate_label_defaulted")

    default_entity = _default_entity_for_frame(normalized, request.source_text)

    kind_text = normalized.get("kind")
    if (
        kind_text == "rule"
        and not _looks_like_slot_collection(normalized.get("if"))
        and _looks_like_slot_collection(normalized.get("then"))
        and not _source_has_conditional_marker(request.source_text)
    ):
        normalized["kind"] = "fact"
        normalized["facts"] = normalized["then"]
        kind_text = "fact"
        _add_normalization_warning(normalization_warnings, "rule_without_condition_retyped:fact")

    if kind_text == "fact":
        normalized["facts"] = _normalize_slot_collection(
            normalized.get("facts"),
            default_entity=default_entity,
            normalization_warnings=normalization_warnings,
        )
    elif kind_text == "rule":
        normalized["if"] = _normalize_slot_collection(
            normalized.get("if"),
            default_entity=default_entity,
            normalization_warnings=normalization_warnings,
        )
        normalized["then"] = _normalize_slot_collection(
            normalized.get("then"),
            default_entity=default_entity,
            normalization_warnings=normalization_warnings,
        )
        if not _has_nonempty_string(normalized.get("scope")):
            normalized["scope"] = default_entity or "entities"
            _add_normalization_warning(normalization_warnings, "scope_defaulted")
    elif kind_text == "claim":
        claim_value = normalized.get("claim")
        if request.mode == "premise":
            if isinstance(claim_value, Mapping):
                normalized["facts"] = [
                    _normalize_slot(
                        dict(claim_value),
                        default_entity=default_entity,
                        normalization_warnings=normalization_warnings,
                    )
                ]
            elif isinstance(claim_value, str) and claim_value.strip():
                normalized["facts"] = [
                    _predicate_slot_from_text(
                        claim_value,
                        default_entity=default_entity,
                        normalization_warnings=normalization_warnings,
                    )
                ]
            else:
                normalized["facts"] = [
                    _predicate_slot_from_text(
                        str(normalized.get("source_text") or request.source_text),
                        default_entity=default_entity,
                        normalization_warnings=normalization_warnings,
                    )
                ]
            if "facts" in normalized:
                normalized["kind"] = "fact"
                _add_normalization_warning(normalization_warnings, "premise_claim_retyped:fact")
            return normalized, normalization_warnings
        if isinstance(claim_value, Mapping):
            normalized["claim"] = _normalize_slot(
                dict(claim_value),
                default_entity=default_entity,
                normalization_warnings=normalization_warnings,
            )
        elif isinstance(claim_value, str) and claim_value.strip():
            normalized["claim"] = _predicate_slot_from_text(
                claim_value,
                default_entity=default_entity,
                normalization_warnings=normalization_warnings,
            )
        else:
            normalized["claim"] = _predicate_slot_from_text(
                str(normalized.get("source_text") or request.source_text),
                default_entity=default_entity,
                normalization_warnings=normalization_warnings,
            )
        if "answer_type" not in normalized:
            normalized["answer_type"] = "claim"
            _add_normalization_warning(normalization_warnings, "answer_type_defaulted")

    return normalized, normalization_warnings


def _normalize_slot_collection(
    value: Any,
    *,
    default_entity: Any,
    normalization_warnings: list[str],
) -> list[Any]:
    if isinstance(value, Mapping):
        items = [value]
        _add_normalization_warning(normalization_warnings, "slot_collection_wrapped")
    elif isinstance(value, list):
        items = value
    else:
        return []

    normalized_items: list[Any] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized_items.append(
                _normalize_slot(
                    dict(item),
                    default_entity=default_entity,
                    normalization_warnings=normalization_warnings,
                )
            )
        else:
            normalized_items.append(item)
    return normalized_items


def _normalize_slot(
    slot: dict[str, Any],
    *,
    default_entity: Any,
    normalization_warnings: list[str],
) -> dict[str, Any]:
    normalized = dict(slot)

    slot_type = normalized.get("type")
    if not isinstance(slot_type, str) or not slot_type.strip():
        inferred_type = _infer_slot_type(normalized)
        normalized["type"] = inferred_type
        _add_normalization_warning(normalization_warnings, f"slot_type_inferred:{inferred_type or 'unknown'}")
        slot_type = normalized.get("type")

    if normalized.get("type") in {"numeric_condition", "numeric_value"} and "value" not in normalized:
        for alias in _NUMERIC_VALUE_ALIASES:
            alias_value = normalized.get(alias)
            if _is_number(alias_value) or (isinstance(alias_value, str) and alias_value.strip()):
                normalized["value"] = alias_value
                _add_normalization_warning(normalization_warnings, f"numeric_value_alias:{alias}")
                break

    if normalized.get("type") in {"numeric_condition", "numeric_value"} and "value" in normalized:
        coerced_value, inferred_unit = _coerce_numeric_string(normalized.get("value"))
        if coerced_value is not None:
            normalized["value"] = coerced_value
            _add_normalization_warning(normalization_warnings, "numeric_string_value_coerced")
            if inferred_unit is not None and "unit" not in normalized:
                normalized["unit"] = inferred_unit
                _add_normalization_warning(normalization_warnings, f"numeric_unit_inferred:{inferred_unit}")

    if normalized.get("type") == "numeric_value" and not _is_number(normalized.get("value")):
        normalized["type"] = "predicate"
        if "name" not in normalized:
            attribute_value = normalized.get("attribute")
            value_text = normalized.get("value")
            if isinstance(attribute_value, str) and attribute_value.strip():
                normalized["name"] = attribute_value
            elif isinstance(value_text, str) and value_text.strip():
                normalized["name"] = value_text
        _add_normalization_warning(normalization_warnings, "numeric_value_retyped:predicate_non_numeric_value")

    if normalized.get("type") == "predicate":
        if "name" not in normalized:
            for alias in _PREDICATE_NAME_ALIASES:
                alias_value = normalized.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    normalized["name"] = alias_value
                    _add_normalization_warning(normalization_warnings, f"predicate_name_alias:{alias}")
                    break
        if "entity" not in normalized and isinstance(normalized.get("subject"), str):
            normalized["entity"] = normalized["subject"]
            _add_normalization_warning(normalization_warnings, "predicate_entity_alias:subject")
        if "entity" not in normalized and isinstance(default_entity, str):
            normalized["entity"] = default_entity
            _add_normalization_warning(normalization_warnings, "slot_entity_defaulted")

    if normalized.get("type") == "entity_relation":
        if not _has_nonempty_string(normalized.get("relation")):
            for alias in _RELATION_NAME_ALIASES:
                alias_value = normalized.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    normalized["relation"] = alias_value
                    _add_normalization_warning(normalization_warnings, f"relation_name_alias:{alias}")
                    break
        if "subject" not in normalized and isinstance(default_entity, str):
            normalized["subject"] = default_entity
            _add_normalization_warning(normalization_warnings, "relation_subject_defaulted")
        if "object" not in normalized:
            for alias in ("target", "destination", "object_entity", "value"):
                alias_value = normalized.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    normalized["object"] = alias_value
                    _add_normalization_warning(normalization_warnings, f"relation_object_alias:{alias}")
                    break

    if normalized.get("type") in {"numeric_condition", "numeric_value"}:
        if "attribute" not in normalized:
            for alias in _NUMERIC_ATTRIBUTE_ALIASES:
                alias_value = normalized.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    normalized["attribute"] = alias_value
                    _add_normalization_warning(normalization_warnings, f"numeric_attribute_alias:{alias}")
                    break
        if "op" not in normalized and normalized.get("type") == "numeric_condition":
            for alias in _NUMERIC_OPERATOR_ALIASES:
                alias_value = normalized.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    normalized["op"] = alias_value
                    _add_normalization_warning(normalization_warnings, f"numeric_operator_alias:{alias}")
                    break
        if "entity" not in normalized and isinstance(default_entity, str):
            normalized["entity"] = default_entity
            _add_normalization_warning(normalization_warnings, "slot_entity_defaulted")

    expression = normalized.get("expression")
    if isinstance(expression, Mapping):
        normalized["expression"] = _normalize_slot(
            dict(expression),
            default_entity=default_entity,
            normalization_warnings=normalization_warnings,
        )

    operands = normalized.get("operands")
    if normalized.get("type") == "arithmetic_expression" and isinstance(operands, Mapping):
        normalized["operands"] = [operands]
        _add_normalization_warning(normalization_warnings, "arithmetic_operands_wrapped")

    return normalized


def _add_normalization_warning(warnings: list[str], warning: str) -> None:
    if warning and warning not in warnings:
        warnings.append(warning)


def _infer_slot_type(slot: Mapping[str, Any]) -> str:
    has_numeric_attribute = "attribute" in slot or any(alias in slot for alias in _NUMERIC_ATTRIBUTE_ALIASES)
    has_numeric_value = "value" in slot or any(alias in slot for alias in _NUMERIC_VALUE_ALIASES)
    has_numeric_operator = "op" in slot or any(alias in slot for alias in _NUMERIC_OPERATOR_ALIASES)
    if {"subject", "relation", "object"}.issubset(slot.keys()):
        return "entity_relation"
    if "op" in slot and "operands" in slot:
        return "arithmetic_expression"
    if has_numeric_attribute and has_numeric_operator:
        return "numeric_condition"
    if has_numeric_attribute and has_numeric_value:
        return "numeric_value"
    if "name" in slot or any(alias in slot for alias in _PREDICATE_NAME_ALIASES):
        return "predicate"
    return ""


def _default_entity_for_frame(payload: Mapping[str, Any], source_text: str) -> str | None:
    for key in ("entity", "scope", "subject"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _infer_generic_entity_from_text(source_text)


def _infer_generic_entity_from_text(source_text: str) -> str | None:
    text = " ".join(source_text.split())
    if not text:
        return None
    lowered = text.lower()
    for prefix in ("all ", "every "):
        if lowered.startswith(prefix):
            rest = text[len(prefix) :]
            for marker in (" are ", " is ", " have ", " has ", " who ", " that "):
                marker_index = rest.lower().find(marker)
                if marker_index > 0:
                    candidate = rest[:marker_index].strip(" .,;:")
                    if candidate:
                        return candidate
            break
    words = text.split()
    if len(words) > 1 and words[0].strip(" .,;:?").lower() in {"does", "do", "did", "is", "are", "can", "could", "will", "would", "should"}:
        second_word = words[1].strip(" .,;:?")
        if second_word and second_word[:1].isupper():
            return second_word
    first_word = words[0].strip(" .,;:") if words else ""
    if first_word and first_word[:1].isupper():
        return first_word
    return None


def _source_has_conditional_marker(source_text: str) -> bool:
    lowered = f" {' '.join(source_text.lower().split())} "
    return any(
        marker in lowered
        for marker in (
            " if ",
            " when ",
            " whenever ",
            " who ",
            " provided that ",
            " unless ",
            " requires ",
            " requirement ",
        )
    )


def _predicate_slot_from_text(
    text: str,
    *,
    default_entity: Any,
    normalization_warnings: list[str],
) -> dict[str, Any]:
    entity = default_entity if isinstance(default_entity, str) and default_entity.strip() else _infer_generic_entity_from_text(text)
    if not entity:
        entity = "entity"
    _add_normalization_warning(normalization_warnings, "claim_text_wrapped_as_predicate")
    return {
        "type": "predicate",
        "entity": entity,
        "name": _predicate_name_from_text(text),
        "polarity": True,
    }


def _predicate_name_from_text(text: str) -> str:
    cleaned = " ".join(text.split()).strip(" .,;:?")
    return cleaned or "claim_text"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _has_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _coerce_numeric_string(value: Any) -> tuple[float | int | None, str | None]:
    if not isinstance(value, str):
        return None, None
    stripped = value.strip()
    if not stripped:
        return None, None
    inferred_unit: str | None = None
    if stripped.endswith("%"):
        inferred_unit = "percent"
        stripped = stripped[:-1].strip()
    normalized = stripped.replace(",", "")
    if re.fullmatch(r"[-+]?\d+", normalized):
        return int(normalized), inferred_unit
    if re.fullmatch(r"[-+]?(?:\d+\.\d+|\d+\.|\.\d+)", normalized):
        return float(normalized), inferred_unit
    return None, None


def _promote_slot_alias(
    payload: dict[str, Any],
    *,
    target_key: str,
    aliases: tuple[str, ...],
    warning_prefix: str,
    normalization_warnings: list[str],
) -> None:
    if _looks_like_slot_collection(payload.get(target_key)):
        return
    for alias in aliases:
        alias_value = payload.get(alias)
        if _looks_like_slot_collection(alias_value):
            payload[target_key] = alias_value
            _add_normalization_warning(normalization_warnings, f"{warning_prefix}:{alias}")
            return


def _looks_like_slot_collection(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list):
        return any(isinstance(item, Mapping) for item in value)
    return False
