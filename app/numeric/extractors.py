"""Numeric extraction helpers for frames, ASTs, and source text."""

from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

from app.logic.ast import (
    AndNode,
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

from .models import NumericComparison, NumericProvenance, NumericQuantity, NumericSourceRecord

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


def extract_from_frames(frames: Sequence[ParseFrame]) -> tuple[list[NumericQuantity], list[NumericComparison], list[str]]:
    quantities: list[NumericQuantity] = []
    comparisons: list[NumericComparison] = []
    warnings: list[str] = []

    for frame in frames:
        frame_entity = frame.entity if isinstance(frame, FactFrame) else None
        for slot in _iter_frame_slots(frame):
            provenance = provenance_from_frame(frame, method="frame_slot")
            if isinstance(slot, NumericValueSlot):
                span = _find_numeric_span(frame.source_text, slot.value)
                quantity = NumericQuantity(
                    attribute=normalize_name(slot.attribute),
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
                        left_attribute=normalize_name(slot.attribute),
                        left_entity=slot.entity,
                        right_value=float(slot.value) if slot.value is not None else None,
                        right_expression_text=slot_expression_to_text(slot.expression) if slot.expression else None,
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


def extract_from_asts(nodes: Sequence[LogicNode]) -> tuple[list[NumericQuantity], list[NumericComparison], list[NumericSourceRecord], list[str]]:
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
            provenance = provenance_from_ast(node)
            left_attr, left_entity = comparison_left_signature(node.left)
            right_value = node.right.value if isinstance(node.right, NumberTerm) else None
            comparison = NumericComparison(
                op=node.op,
                left_attribute=left_attr,
                left_entity=left_entity,
                right_value=float(right_value) if right_value is not None else None,
                right_expression_text=None,
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


def extract_from_source_text(
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
            low_provenance = provenance_from_source_record(record, between_match.start("low"), between_match.end("low"))
            high_provenance = provenance_from_source_record(record, between_match.start("high"), between_match.end("high"))
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
                provenance = provenance_from_source_record(record, match.start("value"), match.end("value"))
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
            provenance = provenance_from_source_record(record, value_match.start(), value_match.end())
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


def source_record_from_frame(frame: ParseFrame) -> NumericSourceRecord:
    return NumericSourceRecord(
        source_id=frame.source_id,
        source_text=frame.source_text,
        premise_id=getattr(frame, "premise_id", None),
        candidate_label=getattr(frame, "candidate_label", None),
    )


def dedupe_source_records(records: Sequence[NumericSourceRecord]) -> list[NumericSourceRecord]:
    deduped: dict[tuple[str, int | None, str | None], NumericSourceRecord] = {}
    for record in records:
        key = (record.source_id, record.premise_id, record.candidate_label)
        deduped[key] = record
    return list(deduped.values())


def comparison_left_signature(left: NumericExpression) -> tuple[str | None, str | None]:
    if isinstance(left, NumRefNode):
        entity = term_to_entity(left.args[0]) if left.args else None
        return normalize_name(left.name), entity
    return None, None


def term_to_entity(term: object) -> str | None:
    if isinstance(term, ConstTerm):
        return term.name
    if isinstance(term, VarTerm):
        return term.name
    return None


def slot_expression_to_text(expression: ArithmeticExpressionSlot | None) -> str | None:
    if expression is None:
        return None
    rendered_operands: list[str] = []
    for operand in expression.operands:
        if isinstance(operand, int | float):
            rendered_operands.append(render_number(float(operand)))
        elif isinstance(operand, Mapping):
            if "attribute" in operand:
                rendered_operands.append(normalize_name(str(operand["attribute"])))
            elif "value" in operand and isinstance(operand["value"], int | float):
                rendered_operands.append(render_number(float(operand["value"])))
            else:
                rendered_operands.append("expr")
        else:
            rendered_operands.append(str(operand))
    return f"{expression.op}({', '.join(rendered_operands)})"


def provenance_from_frame(frame: ParseFrame, *, method: str) -> NumericProvenance:
    return NumericProvenance(
        source_id=frame.source_id,
        source_text=frame.source_text,
        premise_id=getattr(frame, "premise_id", None),
        candidate_label=getattr(frame, "candidate_label", None),
        method=method,  # type: ignore[arg-type]
    )


def provenance_from_ast(node: CompareNode) -> NumericProvenance:
    source_id = getattr(node, "source_id", None) or "unknown_source"
    source_text = getattr(node, "source_text", None) or "unknown_source_text"
    return NumericProvenance(
        source_id=source_id,
        source_text=source_text,
        premise_id=getattr(node, "premise_id", None),
        candidate_label=getattr(node, "candidate_label", None),
        method="ast_node",
    )


def provenance_from_source_record(record: NumericSourceRecord, span_start: int, span_end: int) -> NumericProvenance:
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


def normalize_name(text: str) -> str:
    lowered = "".join(character.lower() if character.isalnum() else "_" for character in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    return collapsed or "value"


def render_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


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
        entity = term_to_entity(node.left.args[0]) if node.left.args else None
        return NumericQuantity(
            attribute=normalize_name(node.left.name),
            entity=entity,
            value=float(node.right.value),
            unit=node.right.unit or node.left.unit,
            provenance=provenance,
            origin="ast",
        )

    if isinstance(node.right, NumRefNode) and isinstance(node.left, NumberTerm):
        entity = term_to_entity(node.right.args[0]) if node.right.args else None
        return NumericQuantity(
            attribute=normalize_name(node.right.name),
            entity=entity,
            value=float(node.left.value),
            unit=node.left.unit or node.right.unit,
            provenance=provenance,
            origin="ast",
        )

    return None


def _find_numeric_span(source_text: str, value: float | int) -> tuple[int, int] | None:
    normalized_value = render_number(float(value))
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
    return normalize_name(best_attribute)


def _infer_entity(source_text: str) -> str | None:
    for match in re.finditer(r"\b[A-Z][a-zA-Z0-9_]*\b", source_text):
        token = match.group(0)
        if token.lower() in {"if", "then", "and", "or", "the", "a", "an"}:
            continue
        return normalize_name(token)
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
