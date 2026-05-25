"""Z3-compatible deterministic adapter for grounded Boolean and numeric fragments."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

from app.logic.ast import AndNode, ArithNode, CompareNode, ConstTerm, ImpliesNode, LogicNode, NotNode, NumRefNode, NumberTerm, OrNode, PredNode
from app.solver.horn.models import HornEntailmentResult


@dataclass(frozen=True)
class Z3AdapterInput:
    premise_asts: Sequence[LogicNode]
    claim_ast: LogicNode
    numeric_context: dict[str, object] | None = None


@dataclass(frozen=True)
class _NumericFacts:
    by_key: dict[tuple[str, str], float]


def prove_with_z3_compatible_adapter(request: Z3AdapterInput) -> HornEntailmentResult:
    if not _is_supported_grounded_formula(request.claim_ast):
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            warnings=["z3_adapter_claim_not_grounded"],
            unsupported_features=["z3_adapter_claim_not_grounded"],
            route="z3",
            confidence=0.0,
            solver_metadata={"z3_status": "unsupported"},
        )

    unsupported_premise = [node for node in request.premise_asts if not _is_supported_grounded_formula(node)]
    if unsupported_premise:
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            warnings=["z3_adapter_premise_not_grounded"],
            unsupported_features=["z3_adapter_premise_not_grounded"],
            route="z3",
            confidence=0.0,
            solver_metadata={"z3_status": "unsupported"},
        )

    numeric_facts = _extract_numeric_facts(request.numeric_context)
    symbols = sorted(_collect_symbols([*request.premise_asts, request.claim_ast]))
    assignments = list(product((False, True), repeat=len(symbols))) if symbols else [tuple()]
    has_satisfying_model = False

    for values in assignments:
        valuation = {symbol: value for symbol, value in zip(symbols, values, strict=True)}
        if not all(_eval_boolean(node, valuation, numeric_facts) is True for node in request.premise_asts):
            continue
        has_satisfying_model = True
        if _eval_boolean(request.claim_ast, valuation, numeric_facts) is not True:
            return HornEntailmentResult(
                entailed=False,
                status="ok",
                warnings=[],
                unsupported_features=[],
                route="z3",
                confidence=0.9,
                solver_metadata={"z3_status": "sat_counterexample"},
            )

    if not has_satisfying_model:
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            warnings=["z3_adapter_inconsistent_or_unknown_premises"],
            unsupported_features=["z3_adapter_inconsistent_or_unknown_premises"],
            route="z3",
            confidence=0.0,
            solver_metadata={"z3_status": "unknown"},
        )

    return HornEntailmentResult(
        entailed=True,
        status="ok",
        used_premise_ids=sorted(_collect_premise_ids(request.premise_asts)),
        warnings=[],
        unsupported_features=[],
        route="z3",
        confidence=0.95,
        solver_metadata={"z3_status": "unsat_negated_claim"},
    )


def _is_supported_grounded_formula(node: LogicNode) -> bool:
    if isinstance(node, PredNode):
        return all(isinstance(term, ConstTerm) for term in node.args)
    if isinstance(node, NotNode):
        return _is_supported_grounded_formula(node.body)
    if isinstance(node, AndNode | OrNode):
        return all(_is_supported_grounded_formula(item) for item in node.operands)
    if isinstance(node, ImpliesNode):
        return _is_supported_grounded_formula(node.if_node) and _is_supported_grounded_formula(node.then)
    if isinstance(node, CompareNode):
        return _is_supported_numeric_expr(node.left) and _is_supported_numeric_expr(node.right)
    return False


def _is_supported_numeric_expr(value: object) -> bool:
    if isinstance(value, NumberTerm):
        return True
    if isinstance(value, NumRefNode):
        return all(isinstance(term, ConstTerm) for term in value.args)
    if isinstance(value, ArithNode):
        return all(_is_supported_numeric_expr(item) for item in value.operands)
    return False


def _collect_symbols(nodes: Sequence[LogicNode]) -> set[str]:
    symbols: set[str] = set()
    for node in nodes:
        _collect_symbols_from_node(node, symbols)
    return symbols


def _collect_symbols_from_node(node: LogicNode, sink: set[str]) -> None:
    if isinstance(node, PredNode):
        sink.add(_pred_symbol(node))
        return
    if isinstance(node, NotNode):
        _collect_symbols_from_node(node.body, sink)
        return
    if isinstance(node, AndNode | OrNode):
        for item in node.operands:
            _collect_symbols_from_node(item, sink)
        return
    if isinstance(node, ImpliesNode):
        _collect_symbols_from_node(node.if_node, sink)
        _collect_symbols_from_node(node.then, sink)


def _eval_boolean(node: LogicNode, valuation: dict[str, bool], numeric_facts: _NumericFacts) -> bool | None:
    if isinstance(node, PredNode):
        return valuation.get(_pred_symbol(node))
    if isinstance(node, NotNode):
        child = _eval_boolean(node.body, valuation, numeric_facts)
        return None if child is None else not child
    if isinstance(node, AndNode):
        values = [_eval_boolean(item, valuation, numeric_facts) for item in node.operands]
        if any(value is None for value in values):
            return None
        return all(bool(value) for value in values)
    if isinstance(node, OrNode):
        values = [_eval_boolean(item, valuation, numeric_facts) for item in node.operands]
        if any(value is None for value in values):
            return None
        return any(bool(value) for value in values)
    if isinstance(node, ImpliesNode):
        left = _eval_boolean(node.if_node, valuation, numeric_facts)
        right = _eval_boolean(node.then, valuation, numeric_facts)
        if left is None or right is None:
            return None
        return (not left) or right
    if isinstance(node, CompareNode):
        left = _eval_numeric_expr(node.left, numeric_facts)
        right = _eval_numeric_expr(node.right, numeric_facts)
        if left is None or right is None:
            return None
        return _compare_values(left, right, node.op)
    return None


def _eval_numeric_expr(value: object, numeric_facts: _NumericFacts) -> float | None:
    if isinstance(value, NumberTerm):
        return float(value.value)
    if isinstance(value, NumRefNode):
        key = _numeric_key(value.name, value.args)
        return numeric_facts.by_key.get(key)
    if isinstance(value, ArithNode):
        operands = [_eval_numeric_expr(item, numeric_facts) for item in value.operands]
        if any(item is None for item in operands):
            return None
        resolved = [float(item) for item in operands if item is not None]
        if value.op == "add":
            return sum(resolved)
        if value.op == "sub" and len(resolved) == 2:
            return resolved[0] - resolved[1]
        if value.op == "mul":
            result = 1.0
            for item in resolved:
                result *= item
            return result
        if value.op == "div" and len(resolved) == 2 and resolved[1] != 0:
            return resolved[0] / resolved[1]
        if value.op == "percentage_of" and len(resolved) == 2:
            return (resolved[0] / 100.0) * resolved[1]
        if value.op == "average" and resolved:
            return sum(resolved) / len(resolved)
        if value.op == "weighted_average" and len(resolved) >= 2 and len(resolved) % 2 == 0:
            pairs = list(zip(resolved[0::2], resolved[1::2], strict=True))
            total_weight = sum(weight for _, weight in pairs)
            if total_weight == 0:
                return None
            return sum(score * weight for score, weight in pairs) / total_weight
        if value.op in {"date_add", "time_add"} and resolved:
            return sum(resolved)
    return None


def _compare_values(left: float, right: float, op: str) -> bool:
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">=":
        return left >= right
    if op == ">":
        return left > right
    return False


def _pred_symbol(node: PredNode) -> str:
    args = ",".join(term.name for term in node.args if isinstance(term, ConstTerm))
    return f"{node.name}({args})"


def _numeric_key(name: str, args: Sequence[object]) -> tuple[str, str]:
    entity = ""
    if args and isinstance(args[0], ConstTerm):
        entity = args[0].name
    return (name.strip().lower(), entity.strip().lower())


def _extract_numeric_facts(numeric_context: dict[str, object] | None) -> _NumericFacts:
    values: dict[tuple[str, str], float] = {}
    if not numeric_context:
        return _NumericFacts(by_key=values)
    facts = numeric_context.get("numeric_facts")
    if not isinstance(facts, list):
        return _NumericFacts(by_key=values)
    for item in facts:
        if not isinstance(item, dict):
            continue
        attribute = str(item.get("attribute", "")).strip().lower()
        entity = str(item.get("entity", "")).strip().lower()
        value = item.get("value")
        if not attribute or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        values[(attribute, entity)] = float(value)
    return _NumericFacts(by_key=values)


def _collect_premise_ids(nodes: Iterable[LogicNode]) -> set[int]:
    ids: set[int] = set()
    for node in nodes:
        premise_id = getattr(node, "premise_id", None)
        if isinstance(premise_id, int):
            ids.add(premise_id)
    return ids

