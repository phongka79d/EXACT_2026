"""Artifact contract writers for parser and numeric incident logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .serialization import assert_runtime_safe_trace_payload, redact_trace_payload

FRAME_EVENTS_PATH = Path("artifacts/frame_events.jsonl")
PARSER_REPLAY_PREFIX = "parser_replay_"
NUMERIC_VALIDATION_FAILURES_PATH = Path("artifacts/numeric_validation_failures.jsonl")


def write_parser_replay_jsonl(path: str | Path, payloads: Sequence[Mapping[str, Any]]) -> Path:
    output_path = Path(path)
    if not output_path.name.startswith(PARSER_REPLAY_PREFIX) or output_path.suffix != ".jsonl":
        raise ValueError("Parser replay artifact path must match parser_replay_*.jsonl")
    return _write_payloads_jsonl(output_path, payloads)


def write_numeric_validation_failures_jsonl(path: str | Path, payloads: Sequence[Mapping[str, Any]]) -> Path:
    output_path = Path(path)
    if output_path.name != NUMERIC_VALIDATION_FAILURES_PATH.name:
        raise ValueError("Numeric validation artifact path must be numeric_validation_failures.jsonl")
    return _write_payloads_jsonl(output_path, payloads)


def _write_payloads_jsonl(path: Path, payloads: Sequence[Mapping[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for payload in payloads:
        safe_payload = redact_trace_payload(payload)
        assert_runtime_safe_trace_payload(safe_payload)
        lines.append(json.dumps(safe_payload, ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
