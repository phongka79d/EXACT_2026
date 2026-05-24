"""JSON/JSONL artifact writers for tracing outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import DebugTrace
from .serialization import assert_runtime_safe_trace_payload, redact_trace_payload, serialize_debug_trace


def write_trace_payload_json(path: str | Path, payload: Mapping[str, Any], *, indent: int = 2) -> Path:
    safe_payload = redact_trace_payload(payload)
    assert_runtime_safe_trace_payload(safe_payload)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(safe_payload, ensure_ascii=True, indent=indent, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_trace_payload_jsonl(path: str | Path, payloads: Sequence[Mapping[str, Any]]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_lines: list[str] = []
    for payload in payloads:
        safe_payload = redact_trace_payload(payload)
        assert_runtime_safe_trace_payload(safe_payload)
        serialized_lines.append(json.dumps(safe_payload, ensure_ascii=True, sort_keys=True))
    output_path.write_text("\n".join(serialized_lines) + "\n", encoding="utf-8")
    return output_path


def write_debug_trace_json(path: str | Path, trace: DebugTrace, *, indent: int = 2) -> Path:
    return write_trace_payload_json(path, serialize_debug_trace(trace), indent=indent)


def write_debug_trace_jsonl(path: str | Path, traces: Sequence[DebugTrace]) -> Path:
    payloads = [serialize_debug_trace(trace) for trace in traces]
    return write_trace_payload_jsonl(path, payloads)
