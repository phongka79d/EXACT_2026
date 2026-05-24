"""Typed debug/proof trace schemas for runtime observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TRACE_FINAL_STATUSES = frozenset({"ok", "failed", "partial"})
TRACE_STAGE_STATUSES = frozenset({"ok", "failed", "partial", "skipped"})

ROOT_CAUSE_CATEGORIES = frozenset(
    {
        "annotation_noise",
        "api_error",
        "ast_validation_error",
        "candidate_extraction_error",
        "data_validation_error",
        "decision_error",
        "explanation_error",
        "fallback_error",
        "frame_compile_error",
        "frame_validation_error",
        "llm_frame_error",
        "normalization_error",
        "numeric_extraction_error",
        "output_formatting_error",
        "proof_search_error",
        "quantifier_instantiation_error",
        "question_parsing_error",
        "schema_validation_error",
        "semantic_fallback_used",
        "solver_capability_gap",
        "solver_routing_error",
        "timeout_error",
        "z3_encoding_error",
    }
)

REFERENCE_ONLY_TRACE_KEYS = frozenset({"premises-fol", "premises_fol", "answer", "explanation", "idx"})


@dataclass(frozen=True)
class SourceCitation:
    source_id: str
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("SourceCitation.source_id must be non-empty")


@dataclass(frozen=True)
class NumericDerivation:
    name: str
    value: float | int | str
    unit: str | None = None
    expression: str | None = None
    sources: list[SourceCitation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("NumericDerivation.name must be non-empty")


@dataclass(frozen=True)
class ProofTraceStep:
    step_id: str
    action: str
    solver_route: str
    status: Literal["ok", "failed", "partial"] = "ok"
    used_premise_ids: list[int] = field(default_factory=list)
    derived_facts: list[str] = field(default_factory=list)
    numeric_derivations: list[NumericDerivation] = field(default_factory=list)
    citations: list[SourceCitation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.step_id.strip():
            raise ValueError("ProofTraceStep.step_id must be non-empty")
        if not self.action.strip():
            raise ValueError("ProofTraceStep.action must be non-empty")
        if not self.solver_route.strip():
            raise ValueError("ProofTraceStep.solver_route must be non-empty")
        if self.status not in TRACE_FINAL_STATUSES:
            raise ValueError(f"Unsupported proof-trace status: {self.status}")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("ProofTraceStep.duration_ms must be non-negative")
        if any(not isinstance(item, int) for item in self.used_premise_ids):
            raise ValueError("ProofTraceStep.used_premise_ids must contain integers")


@dataclass(frozen=True)
class TraceStage:
    name: str
    status: Literal["ok", "failed", "partial", "skipped"]
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("TraceStage.name must be non-empty")
        if self.status not in TRACE_STAGE_STATUSES:
            raise ValueError(f"Unsupported trace stage status: {self.status}")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("TraceStage.duration_ms must be non-negative")


@dataclass(frozen=True)
class CacheMetadata:
    mode: Literal["local", "api", "none"] = "none"
    cache_key: str | None = None
    cache_key_hash: str | None = None
    cache_hit: bool | None = None
    single_flight_waited: bool | None = None


@dataclass(frozen=True)
class DebugTrace:
    sample_id: str | None
    record_id: int | None
    question_id: int | None
    status: Literal["ok", "failed", "partial"] = "ok"
    root_cause_category: str | None = None
    root_cause_message: str | None = None
    created_at: str | None = None
    total_duration_ms: float | None = None
    premises_hash: str | None = None
    warnings: list[str] = field(default_factory=list)
    stages: list[TraceStage] = field(default_factory=list)
    cache: CacheMetadata = field(default_factory=CacheMetadata)
    proof_trace: list[ProofTraceStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in TRACE_FINAL_STATUSES:
            raise ValueError(f"Unsupported debug-trace status: {self.status}")
        if self.total_duration_ms is not None and self.total_duration_ms < 0:
            raise ValueError("DebugTrace.total_duration_ms must be non-negative")
        if self.root_cause_category is not None and self.root_cause_category not in ROOT_CAUSE_CATEGORIES:
            raise ValueError(
                "Unsupported root cause category: "
                f"{self.root_cause_category}. Allowed categories: {sorted(ROOT_CAUSE_CATEGORIES)}"
            )
        if self.sample_id is not None and not self.sample_id.strip():
            raise ValueError("DebugTrace.sample_id must be non-empty when provided")
