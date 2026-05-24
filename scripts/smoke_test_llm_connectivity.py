"""Credential-gated early LLM connectivity smoke check for Batch 4."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import EnvConfigError, load_runtime_config


def run_smoke(env_path: str | Path, timeout_seconds: float) -> tuple[dict[str, Any], int]:
    try:
        config = load_runtime_config(env_path)
    except EnvConfigError as exc:
        return (
            {
                "status": "blocked",
                "reason": "missing_or_invalid_env",
                "detail": str(exc),
            },
            2,
        )

    endpoint = _build_chat_completions_endpoint(config.shopaikey_base_url)
    payload = {
        "model": config.shopaikey_model,
        "messages": [
            {"role": "system", "content": "Return concise JSON only."},
            {"role": "user", "content": 'Return {"ping":"pong"}.'},
        ],
        "temperature": 0.0,
        "max_tokens": 32,
    }
    request = urllib.request.Request(
        endpoint,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.shopaikey_api_key}",
        },
        data=json.dumps(payload).encode("utf-8"),
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as exc:
        return (
            {
                "status": "failed",
                "reason": "http_error",
                "http_status": exc.code,
                "detail": exc.reason,
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            1,
        )
    except urllib.error.URLError as exc:
        return (
            {
                "status": "blocked",
                "reason": "network_or_provider_unavailable",
                "detail": str(exc.reason),
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            2,
        )
    except TimeoutError:
        return (
            {
                "status": "blocked",
                "reason": "timeout",
                "detail": f"Timed out after {timeout_seconds}s",
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            2,
        )
    except socket.timeout:
        return (
            {
                "status": "blocked",
                "reason": "timeout",
                "detail": f"Timed out after {timeout_seconds}s",
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            2,
        )
    except json.JSONDecodeError as exc:
        return (
            {
                "status": "failed",
                "reason": "invalid_json_response",
                "detail": str(exc),
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            1,
        )

    try:
        content = _extract_choice_content(data)
    except ValueError as exc:
        return (
            {
                "status": "failed",
                "reason": "unexpected_response_shape",
                "detail": str(exc),
                "endpoint": _sanitize_endpoint(endpoint),
                "model": config.shopaikey_model,
            },
            1,
        )

    return (
        {
            "status": "passed",
            "endpoint": _sanitize_endpoint(endpoint),
            "model": config.shopaikey_model,
            "response_shape": "choices[0].message.content",
            "sample_content_preview": _safe_preview(content),
        },
        0,
    )


def _build_chat_completions_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def _extract_choice_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Missing non-empty `choices` list")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("`choices[0]` must be an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("Missing `choices[0].message` object")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Missing non-empty `choices[0].message.content`")
    return content.strip()


def _sanitize_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.hostname or "unknown-host"
    scheme = parsed.scheme or "https"
    path = parsed.path or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{scheme}://{host}{port}{path}"


def _safe_preview(content: str, max_length: int = 80) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[:max_length]}..."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an early credential-gated LLM connectivity smoke check.")
    parser.add_argument("--env-path", default=".env", help="Path to .env file")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    result, exit_code = run_smoke(env_path=args.env_path, timeout_seconds=args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
