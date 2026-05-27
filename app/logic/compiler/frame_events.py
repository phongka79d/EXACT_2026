"""Frame lifecycle helpers for parser/validator/compiler artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from app.logic.frames import parse_frame
from app.logic.validation import validate_parse_frame

from .frame_compiler import compile_frame_to_ast

FRAME_EVENT_PATH = Path("artifacts/frame_events.jsonl")


def compile_frame_payload_with_events(payload: Mapping[str, Any], *, events_path: str | Path = FRAME_EVENT_PATH):
    frame = parse_frame(payload)
    _append_frame_event(events_path, "normalized_frame", _to_payload(frame))
    try:
        validate_parse_frame(frame)
        _append_frame_event(events_path, "validated_frame", _to_payload(frame))
        ast = compile_frame_to_ast(frame)
        _append_frame_event(events_path, "compiled_ast", _to_payload(ast))
        return ast
    except Exception as exc:
        _append_frame_event(
            events_path,
            "rejected",
            {
                "kind": getattr(frame, "kind", "unknown"),
                "source_id": getattr(frame, "source_id", None),
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise


def _append_frame_event(path: str | Path, event: str, payload: Mapping[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"event": event, "payload": payload}
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def _to_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("Unsupported frame event payload value")
