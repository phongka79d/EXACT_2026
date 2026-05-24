"""Validation helpers for typed logic AST nodes."""

from __future__ import annotations

from app.logic.ast.nodes import (
    ARITHMETIC_OPERATORS,
    COMPARE_OPERATORS,
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


def validate_logic_ast(node: LogicNode, *, root_context: str) -> None:
    if root_context not in {"premise", "candidate", "runtime"}:
        raise ValueError(f"Unsupported root context: {root_context}")
    _validate_root_metadata(node, root_context)
    arity_map: dict[str, int] = {}
    _validate_node(node, bound_variables=set(), arity_map=arity_map)


def _validate_root_metadata(node: LogicNode, root_context: str) -> None:
    source_id = getattr(node, "source_id", None)
    source_text = getattr(node, "source_text", None)
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("Root AST node must include non-empty source_id")
    if not isinstance(source_text, str) or not source_text.strip():
        raise ValueError("Root AST node must include non-empty source_text")
    if root_context == "premise" and not isinstance(getattr(node, "premise_id", None), int):
        raise ValueError("Premise root must include integer premise_id")
    if root_context == "candidate":
        candidate_label = getattr(node, "candidate_label", None)
        if not isinstance(candidate_label, str) or not candidate_label.strip():
            raise ValueError("Candidate root must include non-empty candidate_label")


def _validate_node(node: LogicNode, *, bound_variables: set[str], arity_map: dict[str, int]) -> None:
    _validate_optional_confidence(node)

    if isinstance(node, PredNode):
        if not node.name.strip():
            raise ValueError("pred.name must be non-empty")
        arity = len(node.args)
        existing_arity = arity_map.get(node.name)
        if existing_arity is not None and existing_arity != arity:
            raise ValueError(f"Predicate arity mismatch for `{node.name}`: expected {existing_arity}, got {arity}")
        arity_map[node.name] = arity
        for term in node.args:
            _validate_term(term, bound_variables=bound_variables)
        return

    if isinstance(node, NotNode):
        _validate_node(node.body, bound_variables=bound_variables, arity_map=arity_map)
        return

    if isinstance(node, AndNode | OrNode):
        if len(node.operands) < 2:
            raise ValueError(f"{node.type} requires at least two operands")
        for operand in node.operands:
            _validate_node(operand, bound_variables=bound_variables, arity_map=arity_map)
        return

    if isinstance(node, ImpliesNode):
        _validate_node(node.if_node, bound_variables=bound_variables, arity_map=arity_map)
        _validate_node(node.then, bound_variables=bound_variables, arity_map=arity_map)
        return

    if isinstance(node, ForallNode | ExistsNode):
        if not node.vars:
            raise ValueError(f"{node.type} must declare at least one variable")
        scoped = set(bound_variables)
        for var in node.vars:
            if not var.name.strip():
                raise ValueError(f"{node.type} variable name must be non-empty")
            if var.name in scoped:
                raise ValueError(f"{node.type} variable `{var.name}` is duplicated in scope")
            scoped.add(var.name)
        _validate_node(node.body, bound_variables=scoped, arity_map=arity_map)
        return

    if isinstance(node, CompareNode):
        if node.op not in COMPARE_OPERATORS:
            raise ValueError(f"Unsupported compare operator: {node.op}")
        _validate_numeric_expression(node.left, bound_variables=bound_variables, arity_map=arity_map)
        _validate_numeric_expression(node.right, bound_variables=bound_variables, arity_map=arity_map)
        return

    if isinstance(node, ArithNode):
        if node.op not in ARITHMETIC_OPERATORS:
            raise ValueError(f"Unsupported arithmetic operator: {node.op}")
        if len(node.operands) < 1:
            raise ValueError("arith node must contain at least one operand")
        for operand in node.operands:
            _validate_numeric_expression(operand, bound_variables=bound_variables, arity_map=arity_map)
        return

    if isinstance(node, NumRefNode):
        if not node.name.strip():
            raise ValueError("num_ref.name must be non-empty")
        for arg in node.args:
            _validate_term(arg, bound_variables=bound_variables)
        return

    raise ValueError(f"Unsupported logic node: {type(node)!r}")


def _validate_numeric_expression(
    expression: NumericExpression,
    *,
    bound_variables: set[str],
    arity_map: dict[str, int],
) -> None:
    if isinstance(expression, NumberTerm):
        return
    if isinstance(expression, NumRefNode):
        _validate_node(expression, bound_variables=bound_variables, arity_map=arity_map)
        return
    if isinstance(expression, ArithNode):
        _validate_node(expression, bound_variables=bound_variables, arity_map=arity_map)
        return
    if isinstance(expression, ConstTerm | VarTerm):
        _validate_term(expression, bound_variables=bound_variables)
        return
    raise ValueError(f"Invalid numeric expression operand: {type(expression)!r}")


def _validate_term(term: Term, *, bound_variables: set[str]) -> None:
    if isinstance(term, VarTerm):
        if term.name not in bound_variables:
            raise ValueError(f"Unbound variable: {term.name}")
        return
    if isinstance(term, ConstTerm):
        if not term.name.strip():
            raise ValueError("const.name must be non-empty")
        return
    if isinstance(term, NumberTerm):
        return
    raise ValueError(f"Unsupported term type: {type(term)!r}")


def _validate_optional_confidence(node: LogicNode) -> None:
    confidence = getattr(node, "confidence", None)
    if confidence is None:
        return
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("confidence must be numeric when provided")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be in [0.0, 1.0]")
