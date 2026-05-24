"""Secret-redaction helpers for logs, traces, and reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED_TOKEN = "<redacted>"
_SENSITIVE_KEY_HINTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "authorization",
    "auth",
    "password",
)


def redact_secret(secret: str | None, *, visible_prefix: int = 4, visible_suffix: int = 2) -> str:
    """Mask a secret string while preserving a short prefix/suffix."""
    if secret is None:
        return REDACTED_TOKEN

    cleaned = secret.strip()
    if not cleaned:
        return REDACTED_TOKEN

    if len(cleaned) <= visible_prefix + visible_suffix:
        return REDACTED_TOKEN

    return f"{cleaned[:visible_prefix]}...{cleaned[-visible_suffix:]}"


def is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(hint in lowered for hint in _SENSITIVE_KEY_HINTS)


def redact_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``values`` with sensitive entries redacted."""
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        if is_sensitive_key(key):
            redacted[key] = redact_secret(str(value) if value is not None else None)
        else:
            redacted[key] = value
    return redacted

