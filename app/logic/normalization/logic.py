"""Normalization utilities for typed logic AST nodes."""

from __future__ import annotations

from dataclasses import replace

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
)
from app.logic.ast.terms import ConstTerm, NumberTerm, Term, VarTerm


def normalize_logic_ast(node: LogicNode) -> LogicNode:
    if isinstance(node, PredNode):
        normalized_args = [_normalize_term(argument) for argument in node.args]
        return replace(node, name=_to_snake_case(node.name), args=normalized_args)

    if isinstance(node, NotNode):
        normalized_body = normalize_logic_ast(node.body)
        if isinstance(normalized_body, NotNode):
            return _merge_metadata(node, normalized_body.body)
        return replace(node, body=normalized_body)

    if isinstance(node, AndNode):
        return _normalize_associative(node, connective_type="and")

    if isinstance(node, OrNode):
        return _normalize_associative(node, connective_type="or")

    if isinstance(node, ImpliesNode):
        return replace(
            node,
            if_node=normalize_logic_ast(node.if_node),
            then=normalize_logic_ast(node.then),
        )

    if isinstance(node, ForallNode | ExistsNode):
        return replace(node, body=normalize_logic_ast(node.body))

    if isinstance(node, CompareNode):
        return replace(
            node,
            left=_normalize_numeric_expression(node.left),
            right=_normalize_numeric_expression(node.right),
        )

    if isinstance(node, ArithNode):
        normalized_operands = [_normalize_numeric_expression(operand) for operand in node.operands]
        return replace(node, op=_to_snake_case(node.op), operands=normalized_operands)

    if isinstance(node, NumRefNode):
        normalized_args = [_normalize_term(argument) for argument in node.args]
        return replace(node, name=_to_snake_case(node.name), args=normalized_args)

    raise ValueError(f"Unsupported logic node: {type(node)!r}")


def _normalize_associative(node: AndNode | OrNode, *, connective_type: str) -> LogicNode:
    flattened: list[LogicNode] = []
    for operand in node.operands:
        normalized_operand = normalize_logic_ast(operand)
        if connective_type == "and" and isinstance(normalized_operand, AndNode):
            flattened.extend(normalized_operand.operands)
        elif connective_type == "or" and isinstance(normalized_operand, OrNode):
            flattened.extend(normalized_operand.operands)
        else:
            flattened.append(normalized_operand)
    if len(flattened) == 1:
        return _merge_metadata(node, flattened[0])
    return replace(node, operands=flattened)


def _normalize_numeric_expression(expression: NumericExpression) -> NumericExpression:
    if isinstance(expression, NumberTerm):
        return expression
    if isinstance(expression, ConstTerm | VarTerm):
        return _normalize_term(expression)
    if isinstance(expression, NumRefNode):
        return normalize_logic_ast(expression)
    if isinstance(expression, ArithNode):
        return normalize_logic_ast(expression)
    raise ValueError(f"Unsupported numeric expression: {type(expression)!r}")


def _normalize_term(term: Term) -> Term:
    if isinstance(term, VarTerm | NumberTerm):
        return term
    if isinstance(term, ConstTerm):
        return replace(term, name=_to_snake_case(term.name))
    raise ValueError(f"Unsupported term type: {type(term)!r}")


def _merge_metadata(metadata_source: LogicNode, node: LogicNode) -> LogicNode:
    return replace(
        node,
        source_id=getattr(node, "source_id", None) or getattr(metadata_source, "source_id", None),
        source_text=getattr(node, "source_text", None) or getattr(metadata_source, "source_text", None),
        premise_id=getattr(node, "premise_id", None) if getattr(node, "premise_id", None) is not None else getattr(metadata_source, "premise_id", None),
        candidate_label=getattr(node, "candidate_label", None)
        if getattr(node, "candidate_label", None) is not None
        else getattr(metadata_source, "candidate_label", None),
        confidence=getattr(node, "confidence", None) if getattr(node, "confidence", None) is not None else getattr(metadata_source, "confidence", None),
    )


def _to_snake_case(text: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "_" for char in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    if not collapsed:
        raise ValueError("Cannot normalize empty text to snake_case")
    return collapsed
