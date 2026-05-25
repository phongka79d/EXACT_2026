"""Deterministic numeric extraction, evaluation, and routing helpers."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Iterable, Mapping, Sequence

from app.logic.ast import (
    AndNode,
    ArithNode,
    CompareNode,
    ConstTerm,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    LogicNode,
    NotNode,
    NumRefNode,
    NumberTerm,
    NumericExpression,
    OrNode,
    VarTerm,
)
from app.logic.frames import (
    ArithmeticExpressionSlot,
    ClaimFrame,
    CompoundFrame,
    FactFrame,
    FrameSlot,
    NumericConditionSlot,
    NumericValueSlot,
    ParseFrame,
    RuleFrame,
)

from .models import (
    DerivedNumericFact,
    NumericComparison,
    NumericConflict,
    NumericLayerResult,
    NumericProvenance,
    NumericQuantity,
    NumericSourceRecord,
    Z3ConstraintCandidate,
)

_COMPARISON_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bat\s+least\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">="),
    (re.compile(r"\bminimum(?:\s+of)?\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">="),
    (re.compile(r"\bor\s+higher\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">="),
    (re.compile(r"\bno\s+less\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">="),
    (re.compile(r"\bat\s+most\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<="),
    (re.compile(r"\bmaximum(?:\s+of)?\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<="),
    (re.compile(r"\bno\s+more\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<="),
    (re.compile(r"\bwithin\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<="),
    (re.compile(r"\bhigher\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">"),
    (re.compile(r"\bgreater\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">"),
    (re.compile(r"\blower\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<"),
    (re.compile(r"\bless\s+than\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<"),
    (re.compile(r"\bbefore\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), "<"),
    (re.compile(r"\bafter\s+(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE), ">"),
)

_BETWEEN_PATTERN = re.compile(r"\bbetween\s+(?P<low>\d+(?:\.\d+)?)\s+and\s+(?P<high>\d+(?:\.\d+)?)", re.IGNORECASE)
_VALUE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent|gpa|points?|credits?|semesters?|days?|hours?|weeks?|months?|years?)?",
    re.IGNORECASE,
)
_NUMERIC_SIGNAL_PATTERN = re.compile(
    r"(\d+|percent|percentage|gpa|score|credit|semester|deadline|duration|fee|penalty|average|weighted|threshold|at least|at most|before|after|between)",
    re.IGNORECASE,
)
_ATTRIBUTE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("gpa", "gpa"),
    ("score", "score"),
    ("credits", "credits"),
    ("credit", "credits"),
    ("semester", "semester"),
    ("fee", "fee"),
    ("penalty", "penalty"),
    ("average", "average"),
    ("weighted", "weighted_score"),
    ("duration", "duration"),
    ("deadline", "deadline"),
    ("day", "days"),
    ("hour", "hours"),
    ("week", "weeks"),
    ("month", "months"),
    ("year", "years"),
    ("rank", "rank"),
    ("threshold", "threshold"),
    ("time", "time"),
)


def build_numeric_layer(
    *,
    premise_frames: Sequence[ParseFrame],
    premise_asts: Sequence[LogicNode],
    candidate_asts: Sequence[LogicNode] = (),
) -> NumericLayerResult:
    """Create deterministic numeric context before symbolic solving."""

    warnings: list[str] = []

    frame_quantities, frame_comparisons, frame_warnings = _extract_from_frames(premise_frames)
    warnings.extend(frame_warnings)

    ast_quantities, ast_comparisons, ast_sources, ast_warnings = _extract_from_asts([*premise_asts, *candidate_asts])
    warnings.extend(ast_warnings)

    frame_sources = [_source_record_from_frame(frame) for frame in premise_frames]
    source_records = _dedupe_source_records([*frame_sources, *ast_sources])
    supplemental_quantities, supplemental_comparisons, supplemental_warnings = _extract_from_source_text(source_records)
    warnings.extend(supplemental_warnings)

    resolved_quantities, supplemental_selected, conflicts, conflict_warnings = _resolve_quantities(
        ast_quantities=ast_quantities,
        frame_quantities=frame_quantities,
        supplemental_quantities=supplemental_quantities,
    )
    warnings.extend(conflict_warnings)

    authoritative_comparisons = [*ast_comparisons, *frame_comparisons]
    supplemental_selected_comparisons = _select_supplemental_comparisons(
        authoritative_comparisons=authoritative_comparisons,
        supplemental_comparisons=supplemental_comparisons,
    )
    comparisons = [*authoritative_comparisons, *supplemental_selected_comparisons]
    derived_facts, z3_constraints, eval_warnings = _evaluate_comparisons(comparisons, resolved_quantities)
    warnings.extend(eval_warnings)

    quantity_facts = [_quantity_as_fact(quantity) for quantity in resolved_quantities.values()]
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


def _extract_from_frames(frames: Sequence[ParseFrame]) -> tuple[list[NumericQuantity], list[NumericComparison], list[str]]:
    quantities: list[NumericQuantity] = []
    comparisons: list[NumericComparison] = []
    warnings: list[str] = []

    for frame in frames:
        frame_entity = frame.entity if isinstance(frame, FactFrame) else None
        for slot in _iter_frame_slots(frame):
            provenance = _provenance_from_frame(frame, method="frame_slot")
            if isinstance(slot, NumericValueSlot):
                span = _find_numeric_span(frame.source_text, slot.value)
                quantity = NumericQuantity(
                    attribute=_normalize_name(slot.attribute),
                    entity=(slot.entity or frame_entity),
                    value=float(slot.value),
                    unit=slot.unit,
                    provenance=_with_span(provenance, span),
                    origin="frame",
                )
                quantities.append(quantity)
                continue

            if isinstance(slot, NumericConditionSlot):
                comparisons.append(
                    NumericComparison(
                        op=slot.op,
                        left_attribute=_normalize_name(slot.attribute),
                        left_entity=slot.entity,
                        right_value=float(slot.value) if slot.value is not None else None,
                        right_expression_text=_slot_expression_to_text(slot.expression) if slot.expression else None,
                        provenance=provenance,
                        origin="frame",
                    )
                )
                continue

            if isinstance(slot, ArithmeticExpressionSlot):
                warnings.append(
                    "Frame arithmetic_expression slot without numeric_condition wrapper was observed and kept for AST-based evaluation."
                )

    return quantities, comparisons, warnings


def _extract_from_asts(nodes: Sequence[LogicNode]) -> tuple[list[NumericQuantity], list[NumericComparison], list[NumericSourceRecord], list[str]]:
    quantities: list[NumericQuantity] = []
    comparisons: list[NumericComparison] = []
    sources: list[NumericSourceRecord] = []
    warnings: list[str] = []

    for root in nodes:
        source_id = getattr(root, "source_id", None)
        source_text = getattr(root, "source_text", None)
        if isinstance(source_id, str) and source_id.strip() and isinstance(source_text, str) and source_text.strip():
            sources.append(
                NumericSourceRecord(
                    source_id=source_id,
                    source_text=source_text,
                    premise_id=getattr(root, "premise_id", None),
                    candidate_label=getattr(root, "candidate_label", None),
                )
            )

        for node in _walk_logic_node(root):
            if not isinstance(node, CompareNode):
                continue
            provenance = _provenance_from_ast(node)
            left_attr, left_entity = _comparison_left_signature(node.left)
            right_value = node.right.value if isinstance(node.right, NumberTerm) else None
            comparison = NumericComparison(
                op=node.op,
                left_attribute=left_attr,
                left_entity=left_entity,
                right_value=float(right_value) if right_value is not None else None,
                right_expression_text=_numeric_expression_to_text(node.right),
                provenance=provenance,
                origin="ast",
                left_expression=node.left,
                right_expression=node.right,
                ast_node=node,
            )
            comparisons.append(comparison)

            quantity = _quantity_from_compare_node(node, provenance)
            if quantity is not None:
                quantities.append(quantity)

    return quantities, comparisons, sources, warnings


def _extract_from_source_text(
    source_records: Sequence[NumericSourceRecord],
) -> tuple[list[NumericQuantity], list[NumericComparison], list[str]]:
    quantities: list[NumericQuantity] = []
    comparisons: list[NumericComparison] = []
    warnings: list[str] = []

    for record in source_records:
        source_text = record.source_text
        found_any = False
        entity = _infer_entity(source_text)

        for between_match in _BETWEEN_PATTERN.finditer(source_text):
            found_any = True
            attribute = _infer_attribute(source_text, between_match.start())
            low = float(between_match.group("low"))
            high = float(between_match.group("high"))
            low_provenance = _provenance_from_source_record(record, between_match.start("low"), between_match.end("low"))
            high_provenance = _provenance_from_source_record(record, between_match.start("high"), between_match.end("high"))
            comparisons.append(
                NumericComparison(
                    op=">=",
                    left_attribute=attribute,
                    left_entity=entity,
                    right_value=low,
                    right_expression_text=str(low),
                    provenance=low_provenance,
                    origin="source_text",
                )
            )
            comparisons.append(
                NumericComparison(
                    op="<=",
                    left_attribute=attribute,
                    left_entity=entity,
                    right_value=high,
                    right_expression_text=str(high),
                    provenance=high_provenance,
                    origin="source_text",
                )
            )

        for pattern, operator in _COMPARISON_PHRASES:
            for match in pattern.finditer(source_text):
                found_any = True
                attribute = _infer_attribute(source_text, match.start())
                value = float(match.group("value"))
                provenance = _provenance_from_source_record(record, match.start("value"), match.end("value"))
                comparisons.append(
                    NumericComparison(
                        op=operator,
                        left_attribute=attribute,
                        left_entity=entity,
                        right_value=value,
                        right_expression_text=str(value),
                        provenance=provenance,
                        origin="source_text",
                    )
                )

        for value_match in _VALUE_PATTERN.finditer(source_text):
            value = float(value_match.group("value"))
            unit_text = value_match.group("unit")
            attribute = _infer_attribute(source_text, value_match.start())
            provenance = _provenance_from_source_record(record, value_match.start(), value_match.end())
            quantities.append(
                NumericQuantity(
                    attribute=attribute,
                    entity=entity,
                    value=value,
                    unit=_normalize_unit(unit_text),
                    provenance=provenance,
                    origin="source_text",
                )
            )
            found_any = True

        if _NUMERIC_SIGNAL_PATTERN.search(source_text) and not found_any:
            warnings.append(
                f"Numeric parse warning for {record.source_id}: numeric signal detected but no deterministic quantity/comparison extracted."
            )

    return quantities, comparisons, warnings


def _resolve_quantities(
    *,
    ast_quantities: Sequence[NumericQuantity],
    frame_quantities: Sequence[NumericQuantity],
    supplemental_quantities: Sequence[NumericQuantity],
) -> tuple[dict[tuple[str, str, str], NumericQuantity], list[NumericQuantity], list[NumericConflict], list[str]]:
    warnings: list[str] = []
    conflicts: list[NumericConflict] = []
    resolved: dict[tuple[str, str, str], NumericQuantity] = {}

    for quantity in ast_quantities:
        resolved[quantity.key] = quantity

    for quantity in frame_quantities:
        existing = resolved.get(quantity.key)
        if existing is None:
            resolved[quantity.key] = quantity
            continue
        if not _numeric_equal(existing.value, quantity.value):
            conflicts.append(
                NumericConflict(
                    key=_stringify_key(quantity.key),
                    preferred_value=existing.value,
                    rejected_value=quantity.value,
                    preferred_origin=existing.origin,
                    rejected_origin=quantity.origin,
                    preferred_source_id=existing.provenance.source_id,
                    rejected_source_id=quantity.provenance.source_id,
                )
            )
            warnings.append(
                f"Numeric conflict detected for {quantity.attribute}: AST value {existing.value} was kept over frame value {quantity.value}."
            )

    supplemental_selected: list[NumericQuantity] = []
    for quantity in supplemental_quantities:
        existing = resolved.get(quantity.key)
        if existing is None:
            resolved[quantity.key] = quantity
            supplemental_selected.append(quantity)
            continue
        if _numeric_equal(existing.value, quantity.value):
            continue
        conflicts.append(
            NumericConflict(
                key=_stringify_key(quantity.key),
                preferred_value=existing.value,
                rejected_value=quantity.value,
                preferred_origin=existing.origin,
                rejected_origin=quantity.origin,
                preferred_source_id=existing.provenance.source_id,
                rejected_source_id=quantity.provenance.source_id,
            )
        )
        warnings.append(
            f"Numeric conflict detected for {quantity.attribute}: {existing.origin} value {existing.value} was kept over source-text value {quantity.value}."
        )

    return resolved, supplemental_selected, conflicts, warnings


def _select_supplemental_comparisons(
    *,
    authoritative_comparisons: Sequence[NumericComparison],
    supplemental_comparisons: Sequence[NumericComparison],
) -> list[NumericComparison]:
    selected: list[NumericComparison] = []
    for supplemental in supplemental_comparisons:
        if any(
            _is_covered_by_authoritative_comparison(supplemental, authoritative)
            for authoritative in authoritative_comparisons
        ):
            continue
        selected.append(supplemental)
    return selected


def _is_covered_by_authoritative_comparison(
    supplemental: NumericComparison,
    authoritative: NumericComparison,
) -> bool:
    if not _same_provenance_target(supplemental.provenance, authoritative.provenance):
        return False
    if supplemental.op != authoritative.op:
        return False

    supplemental_value = _comparison_numeric_right_value(supplemental)
    authoritative_value = _comparison_numeric_right_value(authoritative)
    if supplemental_value is None or authoritative_value is None:
        return False
    if not _numeric_equal(supplemental_value, authoritative_value):
        return False

    return _attributes_compatible(authoritative.left_attribute, supplemental.left_attribute)


def _same_provenance_target(left: NumericProvenance, right: NumericProvenance) -> bool:
    return (
        left.source_id == right.source_id
        and left.premise_id == right.premise_id
        and left.candidate_label == right.candidate_label
    )


def _comparison_numeric_right_value(comparison: NumericComparison) -> float | None:
    if comparison.right_value is not None:
        return comparison.right_value
    if comparison.right_expression_text is None:
        return None
    try:
        return float(comparison.right_expression_text)
    except ValueError:
        return None


def _attributes_compatible(authoritative_attribute: str | None, supplemental_attribute: str | None) -> bool:
    if authoritative_attribute is None or supplemental_attribute is None:
        return True

    authoritative = _normalize_name(authoritative_attribute)
    supplemental = _normalize_name(supplemental_attribute)
    if authoritative == supplemental:
        return True
    if supplemental == "value":
        return True
    return supplemental in authoritative or authoritative in supplemental


def _evaluate_comparisons(
    comparisons: Sequence[NumericComparison],
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
) -> tuple[list[DerivedNumericFact], list[Z3ConstraintCandidate], list[str]]:
    derived: list[DerivedNumericFact] = []
    z3_constraints: list[Z3ConstraintCandidate] = []
    warnings: list[str] = []
    seen_expressions: set[str] = set()

    for comparison in comparisons:
        if (
            comparison.origin == "frame"
            and comparison.left_expression is None
            and comparison.right_expression is None
            and comparison.right_value is None
            and comparison.right_expression_text is not None
        ):
            # Frame-level arithmetic slots are extracted for traceability, while
            # deterministic arithmetic evaluation runs on compiled AST comparisons.
            continue

        expression_text = _comparison_expression_text(comparison)
        if expression_text in seen_expressions:
            continue
        seen_expressions.add(expression_text)

        notes: list[tuple[str, float, str | None]] = []
        try:
            left_value = _resolve_left_value(comparison, quantities, notes)
            right_value = _resolve_right_value(comparison, quantities, notes)
            comparison_result = _apply_compare(comparison.op, left_value, right_value)
        except (LookupError, ValueError, ZeroDivisionError) as exc:
            reason = _constraint_reason(exc)
            warnings.append(
                f"Numeric comparison {expression_text!r} from {comparison.provenance.source_id} was routed to Z3 constraints: {reason}."
            )
            z3_constraints.append(
                Z3ConstraintCandidate(
                    expression=expression_text,
                    reason=reason,
                    sources=[comparison.provenance],
                )
            )
            continue

        for note_text, note_value, note_unit in notes:
            derived.append(
                DerivedNumericFact(
                    name="numeric_expression",
                    value=note_value,
                    expression=f"{note_text} = {_render_number(note_value)}",
                    unit=note_unit,
                    sources=[comparison.provenance],
                )
            )

        derived.append(
            DerivedNumericFact(
                name="numeric_comparison",
                value=comparison_result,
                expression=f"{expression_text} -> {str(comparison_result).lower()}",
                sources=[comparison.provenance],
            )
        )

    return derived, z3_constraints, warnings


def _resolve_left_value(
    comparison: NumericComparison,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if comparison.left_expression is not None:
        return _evaluate_numeric_expression(comparison.left_expression, quantities, notes)

    if comparison.left_attribute is None:
        raise LookupError("left_attribute_missing")

    quantity = _lookup_quantity(
        quantities,
        attribute=comparison.left_attribute,
        entity=comparison.left_entity,
        unit=None,
    )
    if quantity is None:
        raise LookupError("left_numeric_reference_missing")
    return quantity.value


def _resolve_right_value(
    comparison: NumericComparison,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if comparison.right_expression is not None:
        return _evaluate_numeric_expression(comparison.right_expression, quantities, notes)
    if comparison.right_value is not None:
        return comparison.right_value
    raise LookupError("right_expression_missing")


def _evaluate_numeric_expression(
    expression: NumericExpression,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if isinstance(expression, NumberTerm):
        return float(expression.value)

    if isinstance(expression, NumRefNode):
        entity = _term_to_entity(expression.args[0]) if expression.args else None
        quantity = _lookup_quantity(quantities, attribute=expression.name, entity=entity, unit=expression.unit)
        if quantity is None:
            raise LookupError(f"num_ref_missing:{expression.name}")
        return quantity.value

    if isinstance(expression, ArithNode):
        operand_values = [_evaluate_numeric_expression(operand, quantities, notes) for operand in expression.operands]
        result = _evaluate_arithmetic(expression.op, operand_values)
        notes.append((_numeric_expression_to_text(expression), result, None))
        return result

    if isinstance(expression, ConstTerm | VarTerm):
        raise LookupError("symbolic_term_requires_z3")

    raise ValueError(f"Unsupported numeric expression type: {type(expression)!r}")


def _evaluate_arithmetic(op: str, operand_values: Sequence[float]) -> float:
    if not operand_values:
        raise ValueError("numeric_operation_missing_operands")

    if op == "add":
        return float(sum(operand_values))
    if op == "sub":
        head, *rest = operand_values
        return float(head - sum(rest))
    if op == "mul":
        value = 1.0
        for operand in operand_values:
            value *= operand
        return float(value)
    if op == "div":
        head, *rest = operand_values
        value = float(head)
        for operand in rest:
            if operand == 0:
                raise ZeroDivisionError("numeric_division_by_zero")
            value /= operand
        return value
    if op == "percentage_of":
        if len(operand_values) != 2:
            raise ValueError("percentage_of_requires_two_operands")
        return float((operand_values[0] / 100.0) * operand_values[1])
    if op == "average":
        return float(sum(operand_values) / len(operand_values))
    if op == "weighted_average":
        if len(operand_values) < 2 or len(operand_values) % 2 != 0:
            raise ValueError("weighted_average_requires_value_weight_pairs")
        weighted_sum = 0.0
        weight_total = 0.0
        for index in range(0, len(operand_values), 2):
            value = operand_values[index]
            weight = operand_values[index + 1]
            weighted_sum += value * weight
            weight_total += weight
        if weight_total == 0:
            raise ValueError("weighted_average_requires_nonzero_total_weight")
        return float(weighted_sum / weight_total)
    if op in {"date_add", "time_add"}:
        return float(sum(operand_values))

    raise ValueError(f"unsupported_numeric_operator:{op}")


def _lookup_quantity(
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    *,
    attribute: str,
    entity: str | None,
    unit: str | None,
) -> NumericQuantity | None:
    normalized_attribute = _normalize_name(attribute)
    normalized_entity = (entity or "").strip().lower()
    normalized_unit = (unit or "").strip().lower()
    candidates = [
        (normalized_attribute, normalized_entity, normalized_unit),
        (normalized_attribute, normalized_entity, ""),
        (normalized_attribute, "", normalized_unit),
        (normalized_attribute, "", ""),
    ]
    for key in candidates:
        quantity = quantities.get(key)
        if quantity is not None:
            return quantity

    if normalized_unit == "":
        for key, quantity in quantities.items():
            if key[0] == normalized_attribute and key[1] == normalized_entity:
                return quantity
        if normalized_entity:
            for key, quantity in quantities.items():
                if key[0] == normalized_attribute and key[1] == "":
                    return quantity
    return None


def _iter_frame_slots(frame: ParseFrame) -> Iterable[FrameSlot]:
    if isinstance(frame, RuleFrame):
        yield from frame.if_slots
        yield from frame.then_slots
        return
    if isinstance(frame, FactFrame):
        yield from frame.facts
        return
    if isinstance(frame, ClaimFrame):
        yield frame.claim
        return
    if isinstance(frame, CompoundFrame):
        yield from frame.parts
        return


def _walk_logic_node(node: LogicNode) -> Iterable[LogicNode]:
    yield node
    if isinstance(node, NotNode):
        yield from _walk_logic_node(node.body)
        return
    if isinstance(node, AndNode | OrNode):
        for operand in node.operands:
            yield from _walk_logic_node(operand)
        return
    if isinstance(node, ImpliesNode):
        yield from _walk_logic_node(node.if_node)
        yield from _walk_logic_node(node.then)
        return
    if isinstance(node, ForallNode | ExistsNode):
        yield from _walk_logic_node(node.body)
        return


def _quantity_from_compare_node(node: CompareNode, provenance: NumericProvenance) -> NumericQuantity | None:
    if node.op != "=":
        return None

    if isinstance(node.left, NumRefNode) and isinstance(node.right, NumberTerm):
        entity = _term_to_entity(node.left.args[0]) if node.left.args else None
        return NumericQuantity(
            attribute=_normalize_name(node.left.name),
            entity=entity,
            value=float(node.right.value),
            unit=node.right.unit or node.left.unit,
            provenance=provenance,
            origin="ast",
        )

    if isinstance(node.right, NumRefNode) and isinstance(node.left, NumberTerm):
        entity = _term_to_entity(node.right.args[0]) if node.right.args else None
        return NumericQuantity(
            attribute=_normalize_name(node.right.name),
            entity=entity,
            value=float(node.left.value),
            unit=node.left.unit or node.right.unit,
            provenance=provenance,
            origin="ast",
        )

    return None


def _comparison_left_signature(left: NumericExpression) -> tuple[str | None, str | None]:
    if isinstance(left, NumRefNode):
        entity = _term_to_entity(left.args[0]) if left.args else None
        return _normalize_name(left.name), entity
    return None, None


def _term_to_entity(term: object) -> str | None:
    if isinstance(term, ConstTerm):
        return term.name
    if isinstance(term, VarTerm):
        return term.name
    return None


def _slot_expression_to_text(expression: ArithmeticExpressionSlot | None) -> str | None:
    if expression is None:
        return None
    rendered_operands: list[str] = []
    for operand in expression.operands:
        if isinstance(operand, (int, float)):
            rendered_operands.append(_render_number(float(operand)))
        elif isinstance(operand, Mapping):
            if "attribute" in operand:
                rendered_operands.append(_normalize_name(str(operand["attribute"])))
            elif "value" in operand and isinstance(operand["value"], (int, float)):
                rendered_operands.append(_render_number(float(operand["value"])))
            else:
                rendered_operands.append("expr")
        else:
            rendered_operands.append(str(operand))
    return f"{expression.op}({', '.join(rendered_operands)})"


def _numeric_expression_to_text(expression: NumericExpression) -> str:
    if isinstance(expression, NumberTerm):
        if expression.unit:
            return f"{_render_number(float(expression.value))} {expression.unit}"
        return _render_number(float(expression.value))
    if isinstance(expression, NumRefNode):
        if expression.args:
            args = ", ".join(_term_to_text(item) for item in expression.args)
            return f"{expression.name}({args})"
        return expression.name
    if isinstance(expression, ArithNode):
        args = ", ".join(_numeric_expression_to_text(item) for item in expression.operands)
        return f"{expression.op}({args})"
    if isinstance(expression, ConstTerm | VarTerm):
        return _term_to_text(expression)
    return "expr"


def _term_to_text(term: ConstTerm | VarTerm | NumberTerm) -> str:
    if isinstance(term, ConstTerm | VarTerm):
        return term.name
    if isinstance(term, NumberTerm):
        return _render_number(float(term.value))
    return "term"


def _comparison_expression_text(comparison: NumericComparison) -> str:
    left = comparison.left_attribute
    if left is None and comparison.left_expression is not None:
        left = _numeric_expression_to_text(comparison.left_expression)
    if left is None:
        left = "value"
    right = comparison.right_expression_text
    if right is None and comparison.right_expression is not None:
        right = _numeric_expression_to_text(comparison.right_expression)
    if right is None and comparison.right_value is not None:
        right = _render_number(comparison.right_value)
    if right is None:
        right = "expr"
    return f"{left} {comparison.op} {right}"


def _apply_compare(op: str, left: float, right: float) -> bool:
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "=":
        return _numeric_equal(left, right)
    if op == "!=":
        return not _numeric_equal(left, right)
    if op == ">=":
        return left >= right
    if op == ">":
        return left > right
    raise ValueError(f"Unsupported comparison operator: {op}")


def _quantity_as_fact(quantity: NumericQuantity) -> DerivedNumericFact:
    entity_text = quantity.entity if quantity.entity else "*"
    unit_text = f" {quantity.unit}" if quantity.unit else ""
    return DerivedNumericFact(
        name="numeric_quantity",
        value=quantity.value,
        expression=f"{quantity.attribute}({entity_text}) = {_render_number(quantity.value)}{unit_text}",
        unit=quantity.unit,
        sources=[quantity.provenance],
    )


def _provenance_from_frame(frame: ParseFrame, *, method: str) -> NumericProvenance:
    return NumericProvenance(
        source_id=frame.source_id,
        source_text=frame.source_text,
        premise_id=getattr(frame, "premise_id", None),
        candidate_label=getattr(frame, "candidate_label", None),
        method=method,  # type: ignore[arg-type]
    )


def _provenance_from_ast(node: CompareNode) -> NumericProvenance:
    source_id = getattr(node, "source_id", None) or "unknown_source"
    source_text = getattr(node, "source_text", None) or "unknown_source_text"
    return NumericProvenance(
        source_id=source_id,
        source_text=source_text,
        premise_id=getattr(node, "premise_id", None),
        candidate_label=getattr(node, "candidate_label", None),
        method="ast_node",
    )


def _provenance_from_source_record(record: NumericSourceRecord, span_start: int, span_end: int) -> NumericProvenance:
    return NumericProvenance(
        source_id=record.source_id,
        source_text=record.source_text,
        premise_id=record.premise_id,
        candidate_label=record.candidate_label,
        span_start=span_start,
        span_end=span_end,
        span_text=record.source_text[span_start:span_end],
        method="source_text",
    )


def _source_record_from_frame(frame: ParseFrame) -> NumericSourceRecord:
    return NumericSourceRecord(
        source_id=frame.source_id,
        source_text=frame.source_text,
        premise_id=getattr(frame, "premise_id", None),
        candidate_label=getattr(frame, "candidate_label", None),
    )


def _dedupe_source_records(records: Sequence[NumericSourceRecord]) -> list[NumericSourceRecord]:
    deduped: dict[tuple[str, int | None, str | None], NumericSourceRecord] = {}
    for record in records:
        key = (record.source_id, record.premise_id, record.candidate_label)
        deduped[key] = record
    return list(deduped.values())


def _find_numeric_span(source_text: str, value: float | int) -> tuple[int, int] | None:
    normalized_value = _render_number(float(value))
    match = re.search(re.escape(normalized_value), source_text)
    if match is None:
        return None
    return match.start(), match.end()


def _with_span(provenance: NumericProvenance, span: tuple[int, int] | None) -> NumericProvenance:
    if span is None:
        return provenance
    start, end = span
    return NumericProvenance(
        source_id=provenance.source_id,
        source_text=provenance.source_text,
        premise_id=provenance.premise_id,
        candidate_label=provenance.candidate_label,
        span_start=start,
        span_end=end,
        span_text=provenance.source_text[start:end],
        method=provenance.method,
    )


def _infer_attribute(source_text: str, pivot_index: int) -> str:
    lowered = source_text.lower()
    best_attribute = "value"
    best_distance = 10_000
    for keyword, attribute in _ATTRIBUTE_KEYWORDS:
        for match in re.finditer(re.escape(keyword), lowered):
            distance = abs(match.start() - pivot_index)
            if distance < best_distance:
                best_distance = distance
                best_attribute = attribute
    return _normalize_name(best_attribute)


def _infer_entity(source_text: str) -> str | None:
    for match in re.finditer(r"\b[A-Z][a-zA-Z0-9_]*\b", source_text):
        token = match.group(0)
        if token.lower() in {"if", "then", "and", "or", "the", "a", "an"}:
            continue
        return _normalize_name(token)
    return None


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    lowered = unit.strip().lower()
    if lowered == "%":
        return "percent"
    if lowered == "percent":
        return "percent"
    return lowered


def _normalize_name(text: str) -> str:
    lowered = "".join(character.lower() if character.isalnum() else "_" for character in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    return collapsed or "value"


def _constraint_reason(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return "numeric_constraint_requires_z3"
    return message


def _numeric_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9


def _stringify_key(key: tuple[str, str, str]) -> str:
    attribute, entity, unit = key
    return f"{attribute}|{entity or '*'}|{unit or '*'}"


def _render_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")
