"""Explanation-ready proof-trace view models and builders."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Sequence

from app.tracing import DebugTrace, ProofTraceStep, SourceCitation, assert_runtime_safe_trace_payload

_STEP_PHASE_ORDER = {
    "numeric": 1,
    "solver": 2,
    "decision": 3,
}


@dataclass(frozen=True)
class ExplanationFact:
    fact_id: str
    text: str
    step_id: str
    route_label: str
    used_premise_ids: list[int] = field(default_factory=list)
    citations: list[SourceCitation] = field(default_factory=list)


@dataclass(frozen=True)
class NumericComputation:
    computation_id: str
    name: str
    value: float | int | str
    unit: str | None = None
    expression: str | None = None
    sources: list[SourceCitation] = field(default_factory=list)
    step_id: str = "numeric_layer"


@dataclass(frozen=True)
class ExplanationReadyStep:
    trace_step_id: str
    step_id: str
    phase: Literal["numeric", "solver", "decision"]
    phase_order: int
    route_label: str
    action: str
    status: Literal["ok", "failed", "partial"]
    used_premise_ids: list[int] = field(default_factory=list)
    derived_facts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    citations: list[SourceCitation] = field(default_factory=list)
    confidence: float | None = None
    confidence_penalty: float | None = None
    route_details: dict[str, Any] = field(default_factory=dict)
    decision_details: dict[str, Any] | None = None
    numeric_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ExplanationReadyTrace:
    sample_id: str | None
    record_id: int | None
    question_id: int | None
    status: Literal["ok", "failed", "partial"]
    ordered_step_ids: list[str] = field(default_factory=list)
    premise_facts: list[ExplanationFact] = field(default_factory=list)
    derived_facts: list[ExplanationFact] = field(default_factory=list)
    numeric_computations: list[NumericComputation] = field(default_factory=list)
    solver_steps: list[ExplanationReadyStep] = field(default_factory=list)
    final_decision: ExplanationReadyStep | None = None


def build_explanation_ready_trace(trace: DebugTrace) -> ExplanationReadyTrace:
    premise_facts: list[ExplanationFact] = []
    derived_facts: list[ExplanationFact] = []
    numeric_computations: list[NumericComputation] = []
    solver_steps: list[ExplanationReadyStep] = []
    final_decision: ExplanationReadyStep | None = None
    ordered_step_ids: list[str] = []
    premise_counter = 0
    derived_counter = 0
    numeric_counter = 0

    for index, step in enumerate(trace.proof_trace, start=1):
        normalized = _normalize_step(step, index)
        ordered_step_ids.append(normalized.trace_step_id)

        if normalized.phase == "numeric":
            for entry in normalized.numeric_details:
                numeric_counter += 1
                numeric_computations.append(
                    NumericComputation(
                        computation_id=f"numeric_{numeric_counter:04d}",
                        name=str(entry.get("name", "")).strip() or "computed_value",
                        value=entry.get("value", ""),
                        unit=_optional_string(entry.get("unit")),
                        expression=_optional_string(entry.get("expression")),
                        sources=_deserialize_citations(entry.get("sources", [])),
                        step_id=normalized.step_id,
                    )
                )
            for fact_text in normalized.derived_facts:
                derived_counter += 1
                derived_facts.append(
                    ExplanationFact(
                        fact_id=f"derived_fact_{derived_counter:04d}",
                        text=fact_text,
                        step_id=normalized.step_id,
                        route_label=normalized.route_label,
                        used_premise_ids=list(normalized.used_premise_ids),
                        citations=list(normalized.citations),
                    )
                )
            continue

        if normalized.phase == "solver":
            for fact_text in _premise_fact_strings(step):
                premise_counter += 1
                premise_facts.append(
                    ExplanationFact(
                        fact_id=f"premise_fact_{premise_counter:04d}",
                        text=fact_text,
                        step_id=normalized.step_id,
                        route_label=normalized.route_label,
                        used_premise_ids=list(normalized.used_premise_ids),
                        citations=list(normalized.citations),
                    )
                )
            for fact_text in _derived_fact_strings(step):
                derived_counter += 1
                derived_facts.append(
                    ExplanationFact(
                        fact_id=f"derived_fact_{derived_counter:04d}",
                        text=fact_text,
                        step_id=normalized.step_id,
                        route_label=normalized.route_label,
                        used_premise_ids=list(normalized.used_premise_ids),
                        citations=list(normalized.citations),
                    )
                )
            solver_steps.append(normalized)
            continue

        final_decision = normalized

    view = ExplanationReadyTrace(
        sample_id=trace.sample_id,
        record_id=trace.record_id,
        question_id=trace.question_id,
        status=trace.status,
        ordered_step_ids=ordered_step_ids,
        premise_facts=premise_facts,
        derived_facts=derived_facts,
        numeric_computations=numeric_computations,
        solver_steps=solver_steps,
        final_decision=final_decision,
    )
    payload = asdict(view)
    assert_runtime_safe_trace_payload(payload)
    return view


def _normalize_step(step: ProofTraceStep, index: int) -> ExplanationReadyStep:
    phase = _phase_for_route(step.solver_route)
    metadata = dict(step.metadata)
    route_details = metadata.get("route_details") if isinstance(metadata.get("route_details"), dict) else {}
    confidence = _coerce_float(metadata.get("confidence"))
    confidence_penalty = _coerce_float(metadata.get("confidence_penalty"))
    decision_details = metadata.get("decision_details") if isinstance(metadata.get("decision_details"), dict) else None
    numeric_details = metadata.get("computed_values")
    if not isinstance(numeric_details, list):
        numeric_details = []
    return ExplanationReadyStep(
        trace_step_id=f"trace_step_{index:04d}_{step.step_id}",
        step_id=step.step_id,
        phase=phase,
        phase_order=_STEP_PHASE_ORDER[phase],
        route_label=step.solver_route,
        action=step.action,
        status=step.status,
        used_premise_ids=list(step.used_premise_ids),
        derived_facts=list(step.derived_facts),
        warnings=list(step.warnings),
        citations=list(step.citations),
        confidence=confidence,
        confidence_penalty=confidence_penalty,
        route_details=dict(route_details),
        decision_details=dict(decision_details) if isinstance(decision_details, dict) else None,
        numeric_details=list(numeric_details),
    )


def _phase_for_route(route: str) -> Literal["numeric", "solver", "decision"]:
    if route == "numeric":
        return "numeric"
    if route == "decision":
        return "decision"
    return "solver"


def _premise_fact_strings(step: ProofTraceStep) -> list[str]:
    values = step.metadata.get("premise_facts")
    if isinstance(values, list):
        return [str(item) for item in values if isinstance(item, str) and item.strip()]
    return []


def _derived_fact_strings(step: ProofTraceStep) -> list[str]:
    premise_fact_set = set(_premise_fact_strings(step))
    return [item for item in step.derived_facts if item not in premise_fact_set]


def _deserialize_citations(values: Any) -> list[SourceCitation]:
    if not isinstance(values, list):
        return []
    citations: list[SourceCitation] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        source_id = str(value.get("source_id", "")).strip()
        if not source_id:
            continue
        citations.append(
            SourceCitation(
                source_id=source_id,
                source_text=_optional_string(value.get("source_text")),
                premise_id=_optional_int(value.get("premise_id")),
                candidate_label=_optional_string(value.get("candidate_label")),
            )
        )
    return citations


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, float):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    return None
