"""Bounded quantifier utilities for Batch 8 symbolic reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Iterable, Mapping, Sequence

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
    OrNode,
    PredNode,
    QuantifiedVariable,
    VarTerm,
)


@dataclass(frozen=True)
class QuantifierInstantiationResult:
    instances: list[LogicNode]
    used_constants: list[ConstTerm]
    status: str = "ok"
    warnings: list[str] | None = None


def collect_constants(nodes: Sequence[LogicNode]) -> list[ConstTerm]:
    seen: dict[tuple[str, str | None], ConstTerm] = {}
    for node in nodes:
        for term in _iter_const_terms(node):
            key = (term.name, term.domain)
            seen.setdefault(key, term)
    return list(seen.values())


def instantiate_forall(node: ForallNode, constants: Sequence[ConstTerm]) -> QuantifierInstantiationResult:
    if _contains_alternating_quantifier(node.body):
        return QuantifierInstantiationResult(
            instances=[],
            used_constants=[],
            status="solver_capability_gap",
            warnings=["unsupported_alternating_quantifier_pattern"],
        )

    domain_choices: list[list[ConstTerm]] = []
    for quantified_var in node.vars:
        choices = _matching_constants(constants, quantified_var)
        if not choices:
            return QuantifierInstantiationResult(instances=[], used_constants=[], status="ok", warnings=["no_matching_constants_for_domain"])
        domain_choices.append(choices)

    instances: list[LogicNode] = []
    used: dict[tuple[str, str | None], ConstTerm] = {}
    for combo in product(*domain_choices):
        substitution = {var.name: const for var, const in zip(node.vars, combo, strict=True)}
        instantiated = _substitute_node(node.body, substitution)
        instances.append(instantiated)
        for const in combo:
            used[(const.name, const.domain)] = const
    return QuantifierInstantiationResult(instances=instances, used_constants=list(used.values()), status="ok", warnings=[])


def schema_matches_universal(candidate: ForallNode, premises: Sequence[LogicNode]) -> bool:
    candidate_shape = _canonical_formula(candidate)
    for premise in premises:
        if isinstance(premise, ForallNode) and _canonical_formula(premise) == candidate_shape:
            return True
    return False


def instantiate_exists(node: ExistsNode, constants: Sequence[ConstTerm]) -> QuantifierInstantiationResult:
    if _contains_alternating_quantifier(node.body):
        return QuantifierInstantiationResult(
            instances=[],
            used_constants=[],
            status="solver_capability_gap",
            warnings=["unsupported_alternating_quantifier_pattern"],
        )
    domain_choices: list[list[ConstTerm]] = []
    for quantified_var in node.vars:
        choices = _matching_constants(constants, quantified_var)
        if not choices:
            return QuantifierInstantiationResult(
                instances=[],
                used_constants=[],
                status="solver_capability_gap",
                warnings=["no_grounded_witness_for_existential"],
            )
        domain_choices.append(choices)
    instances: list[LogicNode] = []
    used: dict[tuple[str, str | None], ConstTerm] = {}
    for combo in product(*domain_choices):
        substitution = {var.name: const for var, const in zip(node.vars, combo, strict=True)}
        instances.append(_substitute_node(node.body, substitution))
        for const in combo:
            used[(const.name, const.domain)] = const
    return QuantifierInstantiationResult(instances=instances, used_constants=list(used.values()), status="ok", warnings=[])


def _matching_constants(constants: Sequence[ConstTerm], quantified_var: QuantifiedVariable) -> list[ConstTerm]:
    if quantified_var.domain is None:
        return [ConstTerm(kind="const", name=item.name, surface=item.surface, domain=item.domain) for item in constants]
    matches: list[ConstTerm] = []
    for item in constants:
        if item.domain is None or item.domain == quantified_var.domain:
            matches.append(ConstTerm(kind="const", name=item.name, surface=item.surface, domain=item.domain))
    return matches


def _contains_alternating_quantifier(node: LogicNode) -> bool:
    if isinstance(node, ForallNode | ExistsNode):
        return True
    if isinstance(node, NotNode):
        return _contains_alternating_quantifier(node.body)
    if isinstance(node, AndNode | OrNode):
        return any(_contains_alternating_quantifier(item) for item in node.operands)
    if isinstance(node, ImpliesNode):
        return _contains_alternating_quantifier(node.if_node) or _contains_alternating_quantifier(node.then)
    return False


def _iter_const_terms(node: LogicNode) -> Iterable[ConstTerm]:
    if isinstance(node, PredNode):
        for term in node.args:
            if isinstance(term, ConstTerm):
                yield term
        return
    if isinstance(node, NotNode):
        yield from _iter_const_terms(node.body)
        return
    if isinstance(node, AndNode | OrNode):
        for operand in node.operands:
            yield from _iter_const_terms(operand)
        return
    if isinstance(node, ImpliesNode):
        yield from _iter_const_terms(node.if_node)
        yield from _iter_const_terms(node.then)
        return
    if isinstance(node, ForallNode | ExistsNode):
        yield from _iter_const_terms(node.body)
        return
    if isinstance(node, CompareNode):
        yield from _iter_consts_in_numeric(node.left)
        yield from _iter_consts_in_numeric(node.right)
        return
    if isinstance(node, ArithNode):
        for operand in node.operands:
            yield from _iter_consts_in_numeric(operand)
        return
    if isinstance(node, NumRefNode):
        for arg in node.args:
            if isinstance(arg, ConstTerm):
                yield arg


def _iter_consts_in_numeric(expr: Any) -> Iterable[ConstTerm]:
    if isinstance(expr, ConstTerm):
        yield expr
        return
    if isinstance(expr, NumberTerm | VarTerm):
        return
    if isinstance(expr, NumRefNode):
        for arg in expr.args:
            if isinstance(arg, ConstTerm):
                yield arg
        return
    if isinstance(expr, ArithNode):
        for operand in expr.operands:
            yield from _iter_consts_in_numeric(operand)


def _substitute_node(node: LogicNode, substitution: Mapping[str, ConstTerm]) -> LogicNode:
    if isinstance(node, PredNode):
        new_args = [_substitute_term(item, substitution) for item in node.args]
        return PredNode(
            type="pred",
            name=node.name,
            args=new_args,
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, NotNode):
        return NotNode(
            type="not",
            body=_substitute_node(node.body, substitution),
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, AndNode):
        return AndNode(
            type="and",
            operands=[_substitute_node(item, substitution) for item in node.operands],
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, OrNode):
        return OrNode(
            type="or",
            operands=[_substitute_node(item, substitution) for item in node.operands],
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, ImpliesNode):
        return ImpliesNode(
            type="implies",
            if_node=_substitute_node(node.if_node, substitution),
            then=_substitute_node(node.then, substitution),
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, ForallNode):
        inner_sub = dict(substitution)
        for quantified_var in node.vars:
            inner_sub.pop(quantified_var.name, None)
        return ForallNode(
            type="forall",
            vars=node.vars,
            body=_substitute_node(node.body, inner_sub),
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, ExistsNode):
        inner_sub = dict(substitution)
        for quantified_var in node.vars:
            inner_sub.pop(quantified_var.name, None)
        return ExistsNode(
            type="exists",
            vars=node.vars,
            body=_substitute_node(node.body, inner_sub),
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, CompareNode):
        return CompareNode(
            type="compare",
            op=node.op,
            left=_substitute_numeric(node.left, substitution),
            right=_substitute_numeric(node.right, substitution),
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, ArithNode):
        return ArithNode(
            type="arith",
            op=node.op,
            operands=[_substitute_numeric(item, substitution) for item in node.operands],
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    if isinstance(node, NumRefNode):
        return NumRefNode(
            type="num_ref",
            name=node.name,
            args=[_substitute_term(item, substitution) for item in node.args],
            unit=node.unit,
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
            confidence=node.confidence,
        )
    return node


def _substitute_numeric(expr: Any, substitution: Mapping[str, ConstTerm]) -> Any:
    if isinstance(expr, VarTerm):
        replacement = substitution.get(expr.name)
        if replacement is None:
            return expr
        return ConstTerm(kind="const", name=replacement.name, surface=replacement.surface, domain=replacement.domain)
    if isinstance(expr, ConstTerm | NumberTerm):
        return expr
    if isinstance(expr, NumRefNode):
        return NumRefNode(
            type="num_ref",
            name=expr.name,
            args=[_substitute_term(item, substitution) for item in expr.args],
            unit=expr.unit,
            source_id=expr.source_id,
            source_text=expr.source_text,
            premise_id=expr.premise_id,
            candidate_label=expr.candidate_label,
            confidence=expr.confidence,
        )
    if isinstance(expr, ArithNode):
        return ArithNode(
            type="arith",
            op=expr.op,
            operands=[_substitute_numeric(item, substitution) for item in expr.operands],
            source_id=expr.source_id,
            source_text=expr.source_text,
            premise_id=expr.premise_id,
            candidate_label=expr.candidate_label,
            confidence=expr.confidence,
        )
    return expr


def _substitute_term(term: Any, substitution: Mapping[str, ConstTerm]) -> Any:
    if isinstance(term, VarTerm):
        replacement = substitution.get(term.name)
        if replacement is None:
            return term
        return ConstTerm(kind="const", name=replacement.name, surface=replacement.surface, domain=replacement.domain)
    return term


def _canonical_formula(node: LogicNode) -> str:
    token_index = 0
    env: dict[str, str] = {}

    def canonical_term(term: Any) -> str:
        nonlocal token_index
        if isinstance(term, VarTerm):
            token = env.get(term.name)
            if token is None:
                token_index += 1
                token = f"v{token_index}"
                env[term.name] = token
            return token
        if isinstance(term, ConstTerm):
            return f"c:{term.name}"
        if isinstance(term, NumberTerm):
            return f"n:{term.value}"
        return repr(term)

    def canonical_numeric(expr: Any) -> str:
        if isinstance(expr, NumRefNode):
            args = ",".join(canonical_term(item) for item in expr.args)
            return f"num_ref({expr.name}|{args}|{expr.unit})"
        if isinstance(expr, ArithNode):
            inner = ",".join(canonical_numeric(item) for item in expr.operands)
            return f"arith({expr.op}|{inner})"
        return canonical_term(expr)

    def canonical(node_value: LogicNode) -> str:
        nonlocal token_index
        if isinstance(node_value, PredNode):
            args = ",".join(canonical_term(item) for item in node_value.args)
            return f"pred({node_value.name}|{args})"
        if isinstance(node_value, NotNode):
            return f"not({canonical(node_value.body)})"
        if isinstance(node_value, AndNode):
            return "and(" + ",".join(canonical(item) for item in node_value.operands) + ")"
        if isinstance(node_value, OrNode):
            return "or(" + ",".join(canonical(item) for item in node_value.operands) + ")"
        if isinstance(node_value, ImpliesNode):
            return f"implies({canonical(node_value.if_node)}->{canonical(node_value.then)})"
        if isinstance(node_value, ForallNode):
            original = dict(env)
            local_vars: list[str] = []
            for quantified_var in node_value.vars:
                token_index += 1
                token = f"v{token_index}"
                env[quantified_var.name] = token
                local_vars.append(token)
            rendered = f"forall({','.join(local_vars)}:{canonical(node_value.body)})"
            env.clear()
            env.update(original)
            return rendered
        if isinstance(node_value, ExistsNode):
            original = dict(env)
            local_vars: list[str] = []
            for quantified_var in node_value.vars:
                token_index += 1
                token = f"v{token_index}"
                env[quantified_var.name] = token
                local_vars.append(token)
            rendered = f"exists({','.join(local_vars)}:{canonical(node_value.body)})"
            env.clear()
            env.update(original)
            return rendered
        if isinstance(node_value, CompareNode):
            left = canonical_numeric(node_value.left)
            right = canonical_numeric(node_value.right)
            return f"compare({node_value.op}|{left}|{right})"
        if isinstance(node_value, ArithNode):
            return canonical_numeric(node_value)
        if isinstance(node_value, NumRefNode):
            return canonical_numeric(node_value)
        return repr(node_value)

    return canonical(node)


__all__ = [
    "QuantifierInstantiationResult",
    "collect_constants",
    "instantiate_exists",
    "instantiate_forall",
    "schema_matches_universal",
]
