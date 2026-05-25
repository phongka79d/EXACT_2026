"""Deterministic numeric extraction, resolution, evaluation, and routing."""

from __future__ import annotations

from dataclasses import asdict
from typing import Sequence

from app.logic.ast import LogicNode
from app.logic.frames import ParseFrame

from .evaluator import evaluate_comparisons, quantity_as_fact
from .extractors import (
    dedupe_source_records,
    extract_from_asts,
    extract_from_frames,
    extract_from_source_text,
    source_record_from_frame,
)
from .models import NumericLayerResult
from .resolution import resolve_quantities, select_supplemental_comparisons
from .routing import build_z3_constraint_candidates


def build_numeric_layer(
    *,
    premise_frames: Sequence[ParseFrame],
    premise_asts: Sequence[LogicNode],
    candidate_asts: Sequence[LogicNode] = (),
) -> NumericLayerResult:
    """Create deterministic numeric context before symbolic solving."""

    warnings: list[str] = []

    frame_quantities, frame_comparisons, frame_warnings = extract_from_frames(premise_frames)
    warnings.extend(frame_warnings)

    ast_quantities, ast_comparisons, ast_sources, ast_warnings = extract_from_asts([*premise_asts, *candidate_asts])
    warnings.extend(ast_warnings)

    frame_sources = [source_record_from_frame(frame) for frame in premise_frames]
    source_records = dedupe_source_records([*frame_sources, *ast_sources])
    supplemental_quantities, supplemental_comparisons, supplemental_warnings = extract_from_source_text(source_records)
    warnings.extend(supplemental_warnings)

    resolved_quantities, supplemental_selected, conflicts, conflict_warnings = resolve_quantities(
        ast_quantities=ast_quantities,
        frame_quantities=frame_quantities,
        supplemental_quantities=supplemental_quantities,
    )
    warnings.extend(conflict_warnings)

    authoritative_comparisons = [*ast_comparisons, *frame_comparisons]
    supplemental_selected_comparisons = select_supplemental_comparisons(
        authoritative_comparisons=authoritative_comparisons,
        supplemental_comparisons=supplemental_comparisons,
    )
    comparisons = [*authoritative_comparisons, *supplemental_selected_comparisons]

    derived_facts, routing_requests, eval_warnings = evaluate_comparisons(comparisons, resolved_quantities)
    warnings.extend(eval_warnings)

    z3_constraints = build_z3_constraint_candidates(routing_requests)
    quantity_facts = [quantity_as_fact(quantity) for quantity in resolved_quantities.values()]
    all_derived = [*quantity_facts, *derived_facts]

    solver_context = {
        "numeric_facts": [
            {
                "attribute": quantity.attribute,
                "entity": quantity.entity,
                "value": quantity.value,
                "unit": quantity.unit,
                "origin": quantity.origin,
                "provenance": asdict(quantity.provenance),
            }
            for quantity in resolved_quantities.values()
        ],
        "comparisons": [
            {
                "op": comparison.op,
                "left_attribute": comparison.left_attribute,
                "left_entity": comparison.left_entity,
                "right_value": comparison.right_value,
                "right_expression_text": comparison.right_expression_text,
                "origin": comparison.origin,
                "provenance": asdict(comparison.provenance),
            }
            for comparison in comparisons
        ],
        "derived_facts": [
            {
                "name": fact.name,
                "value": fact.value,
                "expression": fact.expression,
                "unit": fact.unit,
                "sources": [asdict(source) for source in fact.sources],
            }
            for fact in all_derived
        ],
        "z3_constraints": [
            {"expression": candidate.expression, "reason": candidate.reason, "sources": [asdict(source) for source in candidate.sources]}
            for candidate in z3_constraints
        ],
        "conflicts": [asdict(conflict) for conflict in conflicts],
        "warnings": list(warnings),
    }

    return NumericLayerResult(
        frame_quantities=frame_quantities,
        ast_quantities=ast_quantities,
        supplemental_quantities=supplemental_selected,
        comparisons=comparisons,
        derived_facts=all_derived,
        z3_constraints=z3_constraints,
        conflicts=conflicts,
        warnings=warnings,
        solver_context=solver_context,
    )
