"""Async OpenAI-compatible HTTP client for configured ShopAIKey endpoints."""

from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.config import RuntimeConfig, load_runtime_config

from .errors import LLMResponseError, LLMTransientError

_TRANSIENT_HTTP_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenAICompatibleChatClient:
    """Small async client for OpenAI-compatible chat-completions endpoints."""

    def __init__(self, config: RuntimeConfig, *, timeout_seconds: float = 20.0):
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._endpoint = _build_chat_completions_endpoint(config.shopaikey_base_url)
        self._sanitized_endpoint = _sanitize_endpoint(self._endpoint)

    @classmethod
    def from_env(cls, env_path: str | Path = ".env", *, timeout_seconds: float = 20.0) -> "OpenAICompatibleChatClient":
        config = load_runtime_config(env_path)
        return cls(config, timeout_seconds=timeout_seconds)

    @property
    def model(self) -> str:
        return self._config.shopaikey_model

    @property
    def sanitized_endpoint(self) -> str:
        return self._sanitized_endpoint

    @property
    def api_key_for_redaction(self) -> str:
        return self._config.shopaikey_api_key

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": self._config.shopaikey_model,
            "messages": _normalize_messages(messages),
            "temperature": self._config.llm_temperature if temperature is None else temperature,
            "max_tokens": self._config.llm_max_tokens if max_tokens is None else max_tokens,
        }

        response_payload = await asyncio.to_thread(self._post_json_sync, payload)
        return _extract_choice_content(response_payload)

    def _post_json_sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self._endpoint,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.shopaikey_api_key}",
            },
            data=json.dumps(payload).encode("utf-8"),
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                body = response.read().decode("utf-8")
                parsed = json.loads(body)
        except urllib.error.HTTPError as exc:
            detail = exc.reason
            if exc.code in _TRANSIENT_HTTP_CODES:
                raise LLMTransientError(
                    f"Transient HTTP error {exc.code} at {self._sanitized_endpoint}: {detail}"
                ) from exc
            raise LLMResponseError(
                f"HTTP error {exc.code} at {self._sanitized_endpoint}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMTransientError(
                f"Network/provider unavailable at {self._sanitized_endpoint}: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise LLMTransientError(
                f"Timeout while calling {self._sanitized_endpoint} after {self._timeout_seconds}s"
            ) from exc
        except socket.timeout as exc:
            raise LLMTransientError(
                f"Timeout while calling {self._sanitized_endpoint} after {self._timeout_seconds}s"
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Provider returned invalid JSON at {self._sanitized_endpoint}: {exc}") from exc

        if not isinstance(parsed, dict):
            raise LLMResponseError("Provider response must be a JSON object")
        return parsed


def _build_chat_completions_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def _sanitize_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.hostname or "unknown-host"
    scheme = parsed.scheme or "https"
    path = parsed.path or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{scheme}://{host}{port}{path}"


def _normalize_messages(messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if not isinstance(role, str) or not role.strip():
            raise ValueError("Each chat message must contain non-empty `role`")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Each chat message must contain non-empty `content`")
        normalized.append({"role": role.strip(), "content": content.strip()})
    if not normalized:
        raise ValueError("At least one chat message is required")
    return normalized


def _extract_choice_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseError("Missing non-empty `choices` list")
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise LLMResponseError("`choices[0]` must be an object")
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise LLMResponseError("Missing `choices[0].message` object")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMResponseError("Missing non-empty `choices[0].message.content`")
    return content.strip()

