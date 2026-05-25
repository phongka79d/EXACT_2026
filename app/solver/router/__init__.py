"""Solver router for Horn, Z3-compatible fragments, and semantic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.logic.ast import AndNode, ArithNode, CompareNode, ForallNode, ImpliesNode, LogicNode, NotNode, NumRefNode, OrNode, PredNode, VarTerm
from app.solver.horn import prove_entailment as prove_horn_entailment
from app.solver.horn.models import HornEntailmentResult
from app.solver.semantic_fallback import SemanticFallbackInput, run_semantic_fallback
from app.solver.z3_adapter import Z3AdapterInput, prove_with_z3_compatible_adapter


@dataclass(frozen=True)
class SolverRequest:
    premise_asts: Sequence[LogicNode]
    claim_ast: LogicNode
    numeric_context: dict[str, object] | None = None
    premises_nl: Sequence[str] = ()
    candidate_text: str = ""


def prove_entailment(request: SolverRequest) -> HornEntailmentResult:
    route = _select_route(request)

    if route == "horn":
        result = prove_horn_entailment(request.premise_asts, request.claim_ast)
        return _with_metadata(result, solver_route="horn", z3_status="not_run", fallback_used=False)

    if route == "z3":
        z3_result = prove_with_z3_compatible_adapter(
            Z3AdapterInput(
                premise_asts=request.premise_asts,
                claim_ast=request.claim_ast,
                numeric_context=request.numeric_context,
            )
        )
        if z3_result.status == "ok":
            return _with_metadata(z3_result, solver_route="z3", z3_status=str(z3_result.solver_metadata.get("z3_status", "ok")), fallback_used=False)
        return _fallback_from_gap(request, symbolic_result=z3_result)

    gap_result = HornEntailmentResult(
        entailed=False,
        status="solver_capability_gap",
        warnings=["unsupported_nested_or_meta_logic"],
        unsupported_features=["unsupported_nested_or_meta_logic"],
        route="z3",
        confidence=0.0,
        solver_metadata={"z3_status": "unsupported"},
    )
    return _fallback_from_gap(request, symbolic_result=gap_result)


def _fallback_from_gap(request: SolverRequest, *, symbolic_result: HornEntailmentResult) -> HornEntailmentResult:
    fallback = run_semantic_fallback(
        SemanticFallbackInput(
            premises_nl=request.premises_nl,
            candidate_text=request.candidate_text,
            symbolic_reason=(symbolic_result.unsupported_features[0] if symbolic_result.unsupported_features else "solver_capability_gap"),
            claim_ast=request.claim_ast,
        )
    )
    return HornEntailmentResult(
        entailed=fallback.entailed,
        status="solver_capability_gap",
        used_premise_ids=sorted(
            set(symbolic_result.used_premise_ids)
            | {
                item.premise_id
                for item in request.premise_asts
                if isinstance(getattr(item, "premise_id", None), int)
            }
        ),
        derived_facts=symbolic_result.derived_facts,
        warnings=_unique([*symbolic_result.warnings, *symbolic_result.unsupported_features, *fallback.warnings]),
        unsupported_features=_unique([*symbolic_result.unsupported_features, *fallback.unsupported_features]),
        route="semantic_fallback",
        confidence=fallback.confidence,
        confidence_penalty=fallback.confidence_penalty,
        solver_metadata={
            **dict(symbolic_result.solver_metadata),
            **dict(fallback.solver_metadata),
            "original_route": symbolic_result.route,
            "z3_status": symbolic_result.solver_metadata.get("z3_status", "unsupported"),
        },
    )


def _select_route(request: SolverRequest) -> str:
    nodes = [*request.premise_asts, request.claim_ast]
    has_numeric = any(_contains_numeric(node) for node in nodes) or bool(
        (request.numeric_context or {}).get("z3_constraints")
    )
    has_nested_implication = any(_contains_nested_implication(node) for node in nodes)
    has_non_horn_boolean = any(_contains_non_horn_boolean(node) for node in nodes)

    if has_numeric:
        return "z3"
    if has_nested_implication:
        if all(_is_ground_boolean_formula(node) for node in nodes):
            return "z3"
        return "fallback"
    if has_non_horn_boolean and all(_is_ground_boolean_formula(node) for node in nodes):
        return "z3"
    return "horn"


def _contains_numeric(node: LogicNode) -> bool:
    if isinstance(node, CompareNode | ArithNode | NumRefNode):
        return True
    if isinstance(node, NotNode):
        return _contains_numeric(node.body)
    if isinstance(node, AndNode | OrNode):
        return any(_contains_numeric(item) for item in node.operands)
    if isinstance(node, ImpliesNode):
        return _contains_numeric(node.if_node) or _contains_numeric(node.then)
    if isinstance(node, ForallNode):
        return _contains_numeric(node.body)
    return False


def _contains_nested_implication(node: LogicNode) -> bool:
    if isinstance(node, ImpliesNode):
        return isinstance(node.if_node, ImpliesNode) or isinstance(node.then, ImpliesNode) or _contains_nested_implication(node.if_node) or _contains_nested_implication(node.then)
    if isinstance(node, NotNode):
        return _contains_nested_implication(node.body)
    if isinstance(node, AndNode | OrNode):
        return any(_contains_nested_implication(item) for item in node.operands)
    if isinstance(node, ForallNode):
        return _contains_nested_implication(node.body)
    return False


def _contains_non_horn_boolean(node: LogicNode) -> bool:
    if isinstance(node, OrNode):
        return True
    if isinstance(node, ImpliesNode):
        if isinstance(node.then, AndNode | OrNode | ImpliesNode):
            return True
        return _contains_non_horn_boolean(node.if_node) or _contains_non_horn_boolean(node.then)
    if isinstance(node, NotNode):
        return _contains_non_horn_boolean(node.body)
    if isinstance(node, AndNode):
        return any(_contains_non_horn_boolean(item) for item in node.operands)
    if isinstance(node, ForallNode):
        return _contains_non_horn_boolean(node.body)
    return False


def _is_ground_boolean_formula(node: LogicNode) -> bool:
    if isinstance(node, PredNode):
        return all(not isinstance(term, VarTerm) for term in node.args)
    if isinstance(node, NotNode):
        return _is_ground_boolean_formula(node.body)
    if isinstance(node, AndNode | OrNode):
        return all(_is_ground_boolean_formula(item) for item in node.operands)
    if isinstance(node, ImpliesNode):
        return _is_ground_boolean_formula(node.if_node) and _is_ground_boolean_formula(node.then)
    return False


def _with_metadata(result: HornEntailmentResult, *, solver_route: str, z3_status: str, fallback_used: bool) -> HornEntailmentResult:
    metadata = dict(result.solver_metadata)
    metadata.setdefault("z3_status", z3_status)
    metadata.setdefault("fallback_used", fallback_used)
    return HornEntailmentResult(
        entailed=result.entailed,
        status=result.status,
        used_premise_ids=list(result.used_premise_ids),
        derived_facts=list(result.derived_facts),
        warnings=list(result.warnings),
        unsupported_features=list(result.unsupported_features),
        route=solver_route,
        confidence=result.confidence,
        confidence_penalty=result.confidence_penalty,
        solver_metadata=metadata,
    )


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
