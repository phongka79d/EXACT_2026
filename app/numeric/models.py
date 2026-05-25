"""Typed contracts for deterministic numeric extraction and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.logic.ast import CompareNode, NumericExpression

NUMERIC_ORIGINS = frozenset({"frame", "ast", "source_text"})
NUMERIC_COMPARISON_OPERATORS = frozenset({"<", "<=", "=", "!=", ">=", ">"})


@dataclass(frozen=True)
class NumericProvenance:
    source_id: str
    source_text: str
    premise_id: int | None = None
    candidate_label: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    span_text: str | None = None
    method: Literal["frame_slot", "ast_node", "source_text"] = "frame_slot"

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("NumericProvenance.source_id must be non-empty")
        if not self.source_text.strip():
            raise ValueError("NumericProvenance.source_text must be non-empty")
        if self.method not in {"frame_slot", "ast_node", "source_text"}:
            raise ValueError(f"Unsupported NumericProvenance.method: {self.method}")
        if self.span_start is not None and self.span_start < 0:
            raise ValueError("NumericProvenance.span_start must be >= 0")
        if self.span_end is not None and self.span_end < 0:
            raise ValueError("NumericProvenance.span_end must be >= 0")
        if self.span_start is not None and self.span_end is not None and self.span_end < self.span_start:
            raise ValueError("NumericProvenance.span_end must be >= span_start")


@dataclass(frozen=True)
class NumericQuantity:
    attribute: str
    entity: str | None
    value: float
    unit: str | None
    provenance: NumericProvenance
    origin: Literal["frame", "ast", "source_text"]

    def __post_init__(self) -> None:
        if not self.attribute.strip():
            raise ValueError("NumericQuantity.attribute must be non-empty")
        if self.origin not in NUMERIC_ORIGINS:
            raise ValueError(f"Unsupported NumericQuantity.origin: {self.origin}")

    @property
    def key(self) -> tuple[str, str, str]:
        return (
            self.attribute.strip().lower(),
            (self.entity or "").strip().lower(),
            (self.unit or "").strip().lower(),
        )


@dataclass(frozen=True)
class NumericComparison:
    op: str
    left_attribute: str | None
    left_entity: str | None
    right_value: float | None
    right_expression_text: str | None
    provenance: NumericProvenance
    origin: Literal["frame", "ast", "source_text"]
    left_expression: NumericExpression | None = None
    right_expression: NumericExpression | None = None
    ast_node: CompareNode | None = None

    def __post_init__(self) -> None:
        if self.op not in NUMERIC_COMPARISON_OPERATORS:
            raise ValueError(f"Unsupported numeric comparison operator: {self.op}")
        if self.origin not in NUMERIC_ORIGINS:
            raise ValueError(f"Unsupported NumericComparison.origin: {self.origin}")


@dataclass(frozen=True)
class DerivedNumericFact:
    name: str
    value: float | bool
    expression: str
    unit: str | None = None
    sources: list[NumericProvenance] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("DerivedNumericFact.name must be non-empty")
        if not self.expression.strip():
            raise ValueError("DerivedNumericFact.expression must be non-empty")


@dataclass(frozen=True)
class NumericConflict:
    key: str
    preferred_value: float
    rejected_value: float
    preferred_origin: Literal["frame", "ast", "source_text"]
    rejected_origin: Literal["frame", "ast", "source_text"]
    preferred_source_id: str
    rejected_source_id: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("NumericConflict.key must be non-empty")


@dataclass(frozen=True)
class Z3ConstraintCandidate:
    expression: str
    reason: str
    sources: list[NumericProvenance] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.expression.strip():
            raise ValueError("Z3ConstraintCandidate.expression must be non-empty")
        if not self.reason.strip():
            raise ValueError("Z3ConstraintCandidate.reason must be non-empty")


@dataclass(frozen=True)
class NumericSourceRecord:
    source_id: str
    source_text: str
    premise_id: int | None = None
    candidate_label: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("NumericSourceRecord.source_id must be non-empty")
        if not self.source_text.strip():
            raise ValueError("NumericSourceRecord.source_text must be non-empty")


@dataclass(frozen=True)
class NumericLayerResult:
    frame_quantities: list[NumericQuantity]
    ast_quantities: list[NumericQuantity]
    supplemental_quantities: list[NumericQuantity]
    comparisons: list[NumericComparison]
    derived_facts: list[DerivedNumericFact]
    z3_constraints: list[Z3ConstraintCandidate]
    conflicts: list[NumericConflict]
    warnings: list[str]
    solver_context: dict[str, object]

