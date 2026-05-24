"""Serialization and runtime-safety guards for debug/proof traces."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Sequence

from app.config.redaction import REDACTED_TOKEN, is_sensitive_key, redact_secret

from .models import DebugTrace, ProofTraceStep, REFERENCE_ONLY_TRACE_KEYS


def assert_runtime_safe_trace_payload(payload: Mapping[str, Any]) -> None:
    """Reject trace payloads containing reference-only training fields."""
    violations: list[str] = []

    def walk(value: Any, path: list[str]) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                normalized = key_text.strip().lower()
                if normalized in REFERENCE_ONLY_TRACE_KEYS:
                    violations.append(".".join([*path, key_text]))
                walk(item, [*path, key_text])
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, [*path, str(index)])

    walk(payload, [])
    if violations:
        location = ", ".join(sorted(violations))
        raise ValueError(f"Trace payload contains reference-only fields: {location}")


def serialize_proof_trace_step(step: ProofTraceStep) -> dict[str, Any]:
    payload = asdict(step)
    assert_runtime_safe_trace_payload(payload)
    return redact_trace_payload(payload)


def serialize_proof_trace_steps(steps: Sequence[ProofTraceStep]) -> list[dict[str, Any]]:
    return [serialize_proof_trace_step(step) for step in steps]


def serialize_debug_trace(trace: DebugTrace) -> dict[str, Any]:
    payload = asdict(trace)
    assert_runtime_safe_trace_payload(payload)
    return redact_trace_payload(payload)


def redact_trace_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _sanitize_value(payload)


def _sanitize_value(value: Any) -> Any:
    if is_dataclass(value):
        return _sanitize_value(asdict(value))

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                sanitized[key_text] = _redact_leaf(item)
            else:
                sanitized[key_text] = _sanitize_value(item)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]

    return value


def _redact_leaf(value: Any) -> str:
    if value is None:
        return redact_secret(None)
    if isinstance(value, str):
        return redact_secret(value)
    if isinstance(value, (int, float, bool)):
        return redact_secret(str(value))
    return REDACTED_TOKEN
