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
        return _with_metadata_recursive(
            node,
            source_id=frame.source_id,
            source_text=frame.source_text,
            candidate_label=frame.candidate_label,
        )

    if isinstance(frame, CompoundFrame):
        parts = [
            _with_metadata_recursive(
                _compile_slot(slot),
                source_id=frame.source_id,
                source_text=frame.source_text,
                premise_id=frame.premise_id,
                candidate_label=frame.candidate_label,
            )
            for slot in frame.parts
        ]
        combined = _join_nodes(frame.operator, parts)
        return _with_metadata_recursive(
            combined,
            source_id=frame.source_id,
            source_text=frame.source_text,
            premise_id=frame.premise_id,
            candidate_label=frame.candidate_label,
        )

    if isinstance(frame, FactFrame):
        compiled = [
            _with_metadata_recursive(
                _compile_slot(slot, frame_entity=frame.entity),
                source_id=frame.source_id,
                source_text=frame.source_text,
                premise_id=frame.premise_id,
            )
            for slot in frame.facts
        ]
        combined = _join_nodes("and", compiled)
        return _with_metadata_recursive(
            combined,
            source_id=frame.source_id,
            source_text=frame.source_text,
            premise_id=frame.premise_id,
        )

    scope_signature = _phrase_signature(frame.scope)
    antecedent = _join_nodes(
        "and",
        [
            _with_metadata_recursive(
                _compile_slot(slot, scope_signature=scope_signature),
                source_id=frame.source_id,
                source_text=frame.source_text,
                premise_id=frame.premise_id,
            )
            for slot in frame.if_slots
        ],
    )
    consequent = _join_nodes(
        "and",
        [
            _with_metadata_recursive(
                _compile_slot(slot, scope_signature=scope_signature),
                source_id=frame.source_id,
                source_text=frame.source_text,
                premise_id=frame.premise_id,
            )
            for slot in frame.then_slots
        ],
    )
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


def _compile_slot(
    slot: FrameSlot,
    *,
    frame_entity: str | None = None,
    scope_signature: str | None = None,
) -> LogicNode:
    if isinstance(slot, PredicateSlot):
        return _compile_predicate_slot(slot, scope_signature=scope_signature)
    if isinstance(slot, NumericConditionSlot):
        return _compile_numeric_condition_slot(slot, scope_signature=scope_signature)
    if isinstance(slot, NumericValueSlot):
        entity = slot.entity or frame_entity
        if not entity:
            raise ValueError("numeric_value slot requires an entity from slot or fact frame")
        left = NumRefNode(
            type="num_ref",
            name=_to_snake_case(slot.attribute),
            args=[_entity_to_term(entity, scope_signature=scope_signature)],
            unit=slot.unit,
        )
        right = NumberTerm(kind="number", value=slot.value, unit=slot.unit)
        return CompareNode(type="compare", op="=", left=left, right=right)
    if isinstance(slot, ArithmeticExpressionSlot):
        return _compile_arithmetic_expression_slot(slot)
    if isinstance(slot, EntityRelationSlot):
        args: list[Term] = [
            _entity_to_term(slot.subject, scope_signature=scope_signature),
            _entity_to_term(slot.object, scope_signature=scope_signature),
        ]
        node: LogicNode = PredNode(type="pred", name=_to_snake_case(slot.relation), args=args)
        return NotNode(type="not", body=node) if not slot.polarity else node

    raise ValueError(f"Unsupported frame slot instance: {type(slot)!r}")


def _compile_predicate_slot(slot: PredicateSlot, *, scope_signature: str | None = None) -> LogicNode:
    node: LogicNode = PredNode(
        type="pred",
        name=_to_snake_case(slot.name),
        args=[_entity_to_term(slot.entity, scope_signature=scope_signature)],
    )
    return NotNode(type="not", body=node) if not slot.polarity else node


def _compile_numeric_condition_slot(slot: NumericConditionSlot, *, scope_signature: str | None = None) -> LogicNode:
    left = NumRefNode(
        type="num_ref",
        name=_to_snake_case(slot.attribute),
        args=[_entity_to_term(slot.entity, scope_signature=scope_signature)],
        unit=slot.unit,
    )
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


def _entity_to_term(entity: str, *, scope_signature: str | None = None) -> Term:
    normalized = _to_snake_case(entity)
    if scope_signature is not None and _phrase_signature(entity) == scope_signature:
        return VarTerm(kind="var", name="x")
    if normalized in {"x", "student", "students", "person", "people", "learner", "learners", "candidate", "candidates"}:
        return VarTerm(kind="var", name="x")
    return ConstTerm(kind="const", name=normalized, surface=entity)


def _phrase_signature(text: str) -> str:
    normalized = _to_snake_case(text)
    tokens = [token for token in normalized.split("_") if token and token not in {"a", "an", "the"}]
    singularized = [_singularize_token(token) for token in tokens]
    return "_".join(singularized)


def _singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith(("sses", "shes", "ches", "xes", "zes")):
        return token[:-2]
    if len(token) > 2 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _to_snake_case(text: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "_" for char in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    if not collapsed:
        raise ValueError("Cannot normalize empty text to snake_case")
    return collapsed


def _with_metadata_recursive(
    node: LogicNode,
    *,
    source_id: str,
    source_text: str,
    premise_id: int | None = None,
    candidate_label: str | None = None,
) -> LogicNode:
    updated = replace(
        node,
        source_id=source_id,
        source_text=source_text,
        premise_id=premise_id,
        candidate_label=candidate_label,
    )
    if isinstance(updated, NotNode):
        return replace(updated, body=_with_metadata_recursive(updated.body, source_id=source_id, source_text=source_text, premise_id=premise_id, candidate_label=candidate_label))
    if isinstance(updated, AndNode | OrNode):
        return replace(
            updated,
            operands=[
                _with_metadata_recursive(
                    item,
                    source_id=source_id,
                    source_text=source_text,
                    premise_id=premise_id,
                    candidate_label=candidate_label,
                )
                for item in updated.operands
            ],
        )
    if isinstance(updated, ImpliesNode):
        return replace(
            updated,
            if_node=_with_metadata_recursive(
                updated.if_node,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
            then=_with_metadata_recursive(
                updated.then,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
        )
    if isinstance(updated, ForallNode | ExistsNode):
        return replace(
            updated,
            body=_with_metadata_recursive(
                updated.body,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
        )
    if isinstance(updated, CompareNode):
        return replace(
            updated,
            left=_with_metadata_numeric_expr(
                updated.left,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
            right=_with_metadata_numeric_expr(
                updated.right,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
        )
    if isinstance(updated, ArithNode):
        return replace(
            updated,
            operands=[
                _with_metadata_numeric_expr(
                    item,
                    source_id=source_id,
                    source_text=source_text,
                    premise_id=premise_id,
                    candidate_label=candidate_label,
                )
                for item in updated.operands
            ],
        )
    if isinstance(updated, NumRefNode):
        return updated
    return updated


def _with_metadata_numeric_expr(
    expression: NumericExpression,
    *,
    source_id: str,
    source_text: str,
    premise_id: int | None,
    candidate_label: str | None,
) -> NumericExpression:
    if isinstance(expression, NumRefNode | ArithNode):
        return _with_metadata_recursive(
            expression,
            source_id=source_id,
            source_text=source_text,
            premise_id=premise_id,
            candidate_label=candidate_label,
        )
    return expression
