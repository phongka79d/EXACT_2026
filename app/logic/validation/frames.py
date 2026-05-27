"""Validation helpers for compact parse frames."""

from __future__ import annotations

import re

from app.logic.frames.models import (
    ARITHMETIC_OPERATORS,
    COMPOUND_OPERATORS,
    NUMERIC_OPERATORS,
    AmbiguousFrame,
    ArithmeticExpressionSlot,
    ClaimFrame,
    CompoundFrame,
    EntityRelationSlot,
    FactFrame,
    FrameSlot,
    NumericConditionSlot,
    NumericValueSlot,
    ParseFrame,
    PredicateSlot,
    RuleFrame,
)

_SCOPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]*$")
_ANSWER_TYPES = frozenset({"yes_no", "yes_no_unknown", "mcq", "numeric", "open_ended", "claim", "unknown"})


def validate_parse_frame(frame: ParseFrame) -> None:
    _validate_common_metadata(frame.source_id, frame.source_text, frame.warnings)

    if isinstance(frame, RuleFrame):
        _validate_rule_frame(frame)
        return
    if isinstance(frame, FactFrame):
        _validate_fact_frame(frame)
        return
    if isinstance(frame, ClaimFrame):
        _validate_claim_frame(frame)
        return
    if isinstance(frame, CompoundFrame):
        _validate_compound_frame(frame)
        return
    if isinstance(frame, AmbiguousFrame):
        _validate_ambiguous_frame(frame)
        return

    raise ValueError(f"Unsupported parse frame type: {type(frame)!r}")


def _validate_rule_frame(frame: RuleFrame) -> None:
    if not _SCOPE_RE.match(frame.scope):
        raise ValueError(f"Invalid rule scope: {frame.scope!r}")
    if not frame.if_slots:
        raise ValueError("Rule frame must contain at least one `if` slot")
    if not frame.then_slots:
        raise ValueError("Rule frame must contain at least one `then` slot")
    for slot in frame.if_slots:
        _validate_slot(slot)
    for slot in frame.then_slots:
        _validate_slot(slot)


def _validate_fact_frame(frame: FactFrame) -> None:
    if not frame.facts:
        raise ValueError("Fact frame must contain at least one fact slot")
    for slot in frame.facts:
        _validate_slot(slot)


def _validate_claim_frame(frame: ClaimFrame) -> None:
    if frame.answer_type not in _ANSWER_TYPES:
        raise ValueError(f"Unsupported claim answer_type: {frame.answer_type}")
    if not frame.candidate_label.strip():
        raise ValueError("Claim frame requires a non-empty candidate_label")
    _validate_slot(frame.claim)


def _validate_compound_frame(frame: CompoundFrame) -> None:
    if frame.operator not in COMPOUND_OPERATORS:
        raise ValueError(f"Unsupported compound operator: {frame.operator}")
    if len(frame.parts) < 2:
        raise ValueError("Compound frame requires at least two parts")
    if frame.premise_id is None and frame.candidate_label is None:
        raise ValueError("Compound frame requires either premise_id or candidate_label metadata")
    for slot in frame.parts:
        _validate_slot(slot)


def _validate_ambiguous_frame(frame: AmbiguousFrame) -> None:
    if not frame.reason.strip():
        raise ValueError("Ambiguous frame reason must be a non-empty string")
    if not frame.options:
        raise ValueError("Ambiguous frame must include at least one option")
    if any(not option.strip() for option in frame.options):
        raise ValueError("Ambiguous frame options must be non-empty strings")


def _validate_slot(slot: FrameSlot) -> None:
    if isinstance(slot, PredicateSlot):
        if not slot.entity.strip():
            raise ValueError("predicate.entity must be non-empty")
        if not slot.name.strip():
            raise ValueError("predicate.name must be non-empty")
        return

    if isinstance(slot, NumericConditionSlot):
        if slot.op not in NUMERIC_OPERATORS:
            raise ValueError(f"Unsupported numeric operator: {slot.op}")
        if slot.value is None and slot.expression is None:
            raise ValueError("numeric_condition must provide either value or expression")
        if slot.expression is not None:
            _validate_slot(slot.expression)
        return

    if isinstance(slot, NumericValueSlot):
        if not slot.attribute.strip():
            raise ValueError("numeric_value.attribute must be non-empty")
        return

    if isinstance(slot, ArithmeticExpressionSlot):
        if slot.op not in ARITHMETIC_OPERATORS:
            raise ValueError(f"Unsupported arithmetic operator: {slot.op}")
        if len(slot.operands) < 2:
            raise ValueError("arithmetic_expression must contain at least two operands")
        return

    if isinstance(slot, EntityRelationSlot):
        if not slot.subject.strip() or not slot.relation.strip() or not slot.object.strip():
            raise ValueError("entity_relation requires non-empty subject/relation/object")
        if slot.complement is not None and not slot.complement.strip():
            raise ValueError("entity_relation.complement must be non-empty when provided")
        return

    raise ValueError(f"Unsupported slot type: {type(slot)!r}")


def _validate_common_metadata(source_id: str, source_text: str, warnings: list[str]) -> None:
    if not source_id.strip():
        raise ValueError("source_id must be a non-empty string")
    if not source_text.strip():
        raise ValueError("source_text must be a non-empty string")
    if any(not warning.strip() for warning in warnings):
        raise ValueError("warnings must contain only non-empty strings")
