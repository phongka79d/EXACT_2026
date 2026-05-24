"""Deterministic compilation from compact parse frames to typed AST nodes."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.logic.ast.nodes import (
    AndNode,
    ArithNode,
    CompareNode,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    LogicNode,
    NotNode,
    NumRefNode,
    NumericExpression,
    OrNode,
    PredNode,
    QuantifiedVariable,
)
from app.logic.ast.terms import ConstTerm, NumberTerm, Term, VarTerm, parse_term
from app.logic.frames.models import (
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
)


def compile_frame_to_ast(frame: ParseFrame) -> LogicNode:
    if isinstance(frame, AmbiguousFrame):
        raise ValueError("Ambiguous frames cannot be compiled to AST")

    if isinstance(frame, ClaimFrame):
        node = _compile_slot(frame.claim)
        return _with_metadata(
            node,
            source_id=frame.source_id,
            source_text=frame.source_text,
            candidate_label=frame.candidate_label,
        )

    if isinstance(frame, CompoundFrame):
        parts = [_compile_slot(slot) for slot in frame.parts]
        combined = _join_nodes(frame.operator, parts)
        return _with_metadata(
            combined,
            source_id=frame.source_id,
            source_text=frame.source_text,
            premise_id=frame.premise_id,
            candidate_label=frame.candidate_label,
        )

    if isinstance(frame, FactFrame):
        compiled = [_compile_slot(slot, frame_entity=frame.entity) for slot in frame.facts]
        combined = _join_nodes("and", compiled)
        return _with_metadata(
            combined,
            source_id=frame.source_id,
            source_text=frame.source_text,
            premise_id=frame.premise_id,
        )

    antecedent = _join_nodes("and", [_compile_slot(slot) for slot in frame.if_slots])
    consequent = _join_nodes("and", [_compile_slot(slot) for slot in frame.then_slots])
    implication = ImpliesNode(type="implies", if_node=antecedent, then=consequent)
    variable = _scope_to_quantified_var(frame.scope)
    return ForallNode(
        type="forall",
        vars=[variable],
        body=implication,
        source_id=frame.source_id,
        source_text=frame.source_text,
        premise_id=frame.premise_id,
    )


def _compile_slot(slot: FrameSlot, *, frame_entity: str | None = None) -> LogicNode:
    if isinstance(slot, PredicateSlot):
        return _compile_predicate_slot(slot)
    if isinstance(slot, NumericConditionSlot):
        return _compile_numeric_condition_slot(slot)
    if isinstance(slot, NumericValueSlot):
        entity = slot.entity or frame_entity
        if not entity:
            raise ValueError("numeric_value slot requires an entity from slot or fact frame")
        left = NumRefNode(type="num_ref", name=_to_snake_case(slot.attribute), args=[_entity_to_term(entity)], unit=slot.unit)
        right = NumberTerm(kind="number", value=slot.value, unit=slot.unit)
        return CompareNode(type="compare", op="=", left=left, right=right)
    if isinstance(slot, ArithmeticExpressionSlot):
        return _compile_arithmetic_expression_slot(slot)
    if isinstance(slot, EntityRelationSlot):
        args: list[Term] = [_entity_to_term(slot.subject), _entity_to_term(slot.object)]
        node: LogicNode = PredNode(type="pred", name=_to_snake_case(slot.relation), args=args)
        return NotNode(type="not", body=node) if not slot.polarity else node

    raise ValueError(f"Unsupported frame slot instance: {type(slot)!r}")


def _compile_predicate_slot(slot: PredicateSlot) -> LogicNode:
    node: LogicNode = PredNode(
        type="pred",
        name=_to_snake_case(slot.name),
        args=[_entity_to_term(slot.entity)],
    )
    return NotNode(type="not", body=node) if not slot.polarity else node


def _compile_numeric_condition_slot(slot: NumericConditionSlot) -> LogicNode:
    left = NumRefNode(type="num_ref", name=_to_snake_case(slot.attribute), args=[_entity_to_term(slot.entity)], unit=slot.unit)
    if slot.expression is not None:
        right: NumericExpression = _compile_arithmetic_expression_slot(slot.expression)
    elif slot.value is not None:
        right = NumberTerm(kind="number", value=slot.value, unit=slot.unit)
    else:
        raise ValueError("numeric_condition requires `value` or `expression`")
    return CompareNode(type="compare", op=slot.op, left=left, right=right)


def _compile_arithmetic_expression_slot(slot: ArithmeticExpressionSlot) -> ArithNode:
    operands: list[NumericExpression] = [_compile_numeric_operand(item) for item in slot.operands]
    return ArithNode(type="arith", op=slot.op, operands=operands)


def _compile_numeric_operand(value: Any) -> NumericExpression:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return NumberTerm(kind="number", value=value)
    if isinstance(value, dict):
        if value.get("kind") in {"var", "const", "number"}:
            return parse_term(value)
        if value.get("type") == "arithmetic_expression":
            nested = ArithmeticExpressionSlot(type="arithmetic_expression", op=str(value.get("op", "")), operands=list(value.get("operands", [])))
            return _compile_arithmetic_expression_slot(nested)
        if "attribute" in value:
            entity = value.get("entity")
            args = [_entity_to_term(entity)] if isinstance(entity, str) and entity.strip() else []
            return NumRefNode(type="num_ref", name=_to_snake_case(str(value["attribute"])), args=args, unit=value.get("unit"))
        if "value" in value and isinstance(value["value"], (int, float)) and not isinstance(value["value"], bool):
            return NumberTerm(kind="number", value=value["value"], unit=value.get("unit"))
    raise ValueError("Unsupported arithmetic operand in frame slot")


def _join_nodes(operator: str, nodes: list[LogicNode]) -> LogicNode:
    if not nodes:
        raise ValueError("Cannot combine an empty node list")
    if len(nodes) == 1:
        return nodes[0]
    if operator == "and":
        return AndNode(type="and", operands=nodes)
    if operator == "or":
        return OrNode(type="or", operands=nodes)
    raise ValueError(f"Unsupported compound operator: {operator}")


def _scope_to_quantified_var(scope: str) -> QuantifiedVariable:
    normalized = _to_snake_case(scope)
    singular = normalized[:-1] if normalized.endswith("s") and len(normalized) > 1 else normalized
    return QuantifiedVariable(name="x", domain=singular or None)


def _entity_to_term(entity: str) -> Term:
    normalized = _to_snake_case(entity)
    if normalized in {"x", "student", "person", "learner", "candidate"}:
        return VarTerm(kind="var", name="x")
    return ConstTerm(kind="const", name=normalized, surface=entity)


def _to_snake_case(text: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "_" for char in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    if not collapsed:
        raise ValueError("Cannot normalize empty text to snake_case")
    return collapsed


def _with_metadata(
    node: LogicNode,
    *,
    source_id: str,
    source_text: str,
    premise_id: int | None = None,
    candidate_label: str | None = None,
) -> LogicNode:
    return replace(
        node,
        source_id=source_id,
        source_text=source_text,
        premise_id=premise_id,
        candidate_label=candidate_label,
    )
