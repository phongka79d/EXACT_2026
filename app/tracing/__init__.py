"""Tracing contracts and artifact writers for debug and proof visibility."""

from .citations import CitationRegistry, CitationResolution, build_source_registry
from .artifact_contracts import (
    FRAME_EVENTS_PATH,
    NUMERIC_VALIDATION_FAILURES_PATH,
    PARSER_REPLAY_PREFIX,
    write_numeric_validation_failures_jsonl,
    write_parser_replay_jsonl,
)
from .models import (
    REFERENCE_ONLY_TRACE_KEYS,
    ROOT_CAUSE_CATEGORIES,
    CacheMetadata,
    DebugTrace,
    NumericDerivation,
    ProofTraceStep,
    SourceCitation,
    TraceStage,
)
from .serialization import (
    assert_runtime_safe_trace_payload,
    serialize_debug_trace,
    serialize_proof_trace_step,
    serialize_proof_trace_steps,
)
from .writers import (
    write_debug_trace_json,
    write_debug_trace_jsonl,
    write_trace_payload_json,
    write_trace_payload_jsonl,
)

__all__ = [
    "CitationRegistry",
    "CitationResolution",
    "FRAME_EVENTS_PATH",
    "NUMERIC_VALIDATION_FAILURES_PATH",
    "PARSER_REPLAY_PREFIX",
    "REFERENCE_ONLY_TRACE_KEYS",
    "ROOT_CAUSE_CATEGORIES",
    "CacheMetadata",
    "DebugTrace",
    "NumericDerivation",
    "ProofTraceStep",
    "SourceCitation",
    "TraceStage",
    "build_source_registry",
    "assert_runtime_safe_trace_payload",
    "serialize_debug_trace",
    "serialize_proof_trace_step",
    "serialize_proof_trace_steps",
    "write_numeric_validation_failures_jsonl",
    "write_parser_replay_jsonl",
    "write_debug_trace_json",
    "write_debug_trace_jsonl",
    "write_trace_payload_json",
    "write_trace_payload_jsonl",
]
