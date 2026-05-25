"""Deterministic Horn-style entailment with bounded quantifier support."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from app.logic.ast import (
    AndNode,
    ConstTerm,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    LogicNode,
    NotNode,
    PredNode,
    VarTerm,
)
from app.solver.contraposition import derive_contrapositive
from app.solver.horn.models import HornDerivation, HornEntailmentResult, HornLiteral, HornRule, HornTerm
from app.solver.quantifiers import collect_constants, instantiate_exists, instantiate_forall, schema_matches_universal


def prove_entailment(
    premise_asts: Sequence[LogicNode],
    claim: LogicNode,
    *,
    enable_contraposition: bool = True,
) -> HornEntailmentResult:
    constants = collect_constants([*premise_asts, claim])
    facts: dict[HornLiteral, set[int]] = {}
    rules: list[HornRule] = []
    derivations: list[HornDerivation] = []
    warnings: list[str] = []
    unsupported_features: list[str] = []

    for premise in premise_asts:
        extracted = _extract_from_premise(premise, constants)
        warnings.extend(extracted[0])
        unsupported_features.extend(extracted[1])
        rules.extend(extracted[2])
        for literal, premise_id in extracted[3]:
            support = facts.setdefault(literal, set())
            if premise_id is not None:
                support.add(premise_id)
            derivations.append(
                HornDerivation(
                    literal=literal,
                    method="premise_fact",
                    source_premise_ids=sorted(support),
                    supporting_literals=[],
                )
            )

    if enable_contraposition:
        contraposed_rules: list[HornRule] = []
        for rule in rules:
            derived_rule, rejection = derive_contrapositive(rule)
            if derived_rule is None:
                if rejection is not None:
                    unsupported_features.append(rejection)
                continue
            contraposed_rules.append(derived_rule)
        rules.extend(contraposed_rules)

    forward = _forward_chain(facts, rules)
    known_facts = forward[0]
    derivations.extend(forward[1])

    if isinstance(claim, ForallNode):
        if schema_matches_universal(claim, premise_asts):
            matched_premise_ids = sorted(
                {
                    item.premise_id
                    for item in premise_asts
                    if isinstance(item, ForallNode) and schema_matches_universal(claim, [item])
                    if item.premise_id is not None
                }
            )
            derivations.append(
                HornDerivation(
                    literal=HornLiteral(predicate="schema_match", arguments=tuple(), negated=False),
                    method="schema_match",
                    source_premise_ids=matched_premise_ids,
                    supporting_literals=[],
                    rule_text="schema_level_universal_match",
                )
            )
            return HornEntailmentResult(
                entailed=True,
                status="ok",
                used_premise_ids=matched_premise_ids,
                derived_facts=derivations,
                warnings=_unique_strings(warnings),
                unsupported_features=_unique_strings(unsupported_features),
            )
        gap_message = "unsupported_quantifier_no_schema_match"
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            used_premise_ids=[],
            derived_facts=derivations,
            warnings=_unique_strings([*warnings, gap_message]),
            unsupported_features=_unique_strings([*unsupported_features, gap_message]),
        )

    if isinstance(claim, ExistsNode):
        existential_result = instantiate_exists(claim, constants)
        if existential_result.status != "ok":
            return HornEntailmentResult(
                entailed=False,
                status="solver_capability_gap",
                used_premise_ids=[],
                derived_facts=derivations,
                warnings=_unique_strings([*warnings, *(existential_result.warnings or [])]),
                unsupported_features=_unique_strings([*unsupported_features, *(existential_result.warnings or [])]),
            )
        for instantiated_claim in existential_result.instances:
            literal = _literal_from_node(instantiated_claim)
            if literal is None:
                continue
            if literal in known_facts:
                used = sorted(known_facts[literal])
                derivations.append(
                    HornDerivation(
                        literal=literal,
                        method="existential_witness",
                        source_premise_ids=used,
                        supporting_literals=[],
                    )
                )
                return HornEntailmentResult(
                    entailed=True,
                    status="ok",
                    used_premise_ids=used,
                    derived_facts=derivations,
                    warnings=_unique_strings(warnings),
                    unsupported_features=_unique_strings(unsupported_features),
                )
        return HornEntailmentResult(
            entailed=False,
            status="ok",
            used_premise_ids=[],
            derived_facts=derivations,
            warnings=_unique_strings(warnings),
            unsupported_features=_unique_strings(unsupported_features),
        )

    claim_literal = _literal_from_node(claim)
    if claim_literal is None:
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            used_premise_ids=[],
            derived_facts=derivations,
            warnings=_unique_strings([*warnings, "unsupported_non_horn_claim"]),
            unsupported_features=_unique_strings([*unsupported_features, "unsupported_non_horn_claim"]),
        )

    if not claim_literal.is_ground:
        return HornEntailmentResult(
            entailed=False,
            status="solver_capability_gap",
            used_premise_ids=[],
            derived_facts=derivations,
            warnings=_unique_strings([*warnings, "unsupported_unbounded_claim_variable"]),
            unsupported_features=_unique_strings([*unsupported_features, "unsupported_unbounded_claim_variable"]),
        )

    entailed = claim_literal in known_facts
    used_premise_ids = sorted(known_facts.get(claim_literal, set()))
    status = "ok"
    if not entailed and unsupported_features:
        status = "solver_capability_gap"
    return HornEntailmentResult(
        entailed=entailed,
        status=status,
        used_premise_ids=used_premise_ids,
        derived_facts=derivations,
        warnings=_unique_strings(warnings),
        unsupported_features=_unique_strings(unsupported_features),
    )


def _extract_from_premise(
    premise: LogicNode,
    constants: Sequence[ConstTerm],
) -> tuple[list[str], list[str], list[HornRule], list[tuple[HornLiteral, int | None]]]:
    warnings: list[str] = []
    unsupported_features: list[str] = []
    rules: list[HornRule] = []
    facts: list[tuple[HornLiteral, int | None]] = []
    source_id = getattr(premise, "source_id", None)
    source_text = getattr(premise, "source_text", None)
    premise_id = getattr(premise, "premise_id", None)
    candidate_label = getattr(premise, "candidate_label", None)

    def add_fact(node: LogicNode) -> None:
        literal = _literal_from_node(node)
        if literal is None:
            unsupported_features.append("unsupported_non_literal_fact")
            return
        facts.append(
            (
                replace(
                    literal,
                    source_id=source_id,
                    source_text=source_text,
                    premise_id=premise_id,
                    candidate_label=candidate_label,
                ),
                premise_id,
            )
        )

    def add_rule(node: ImpliesNode) -> None:
        antecedents = _literals_from_antecedent(node.if_node)
        consequent = _literal_from_node(node.then)
        if antecedents is None or consequent is None:
            unsupported_features.append("unsupported_non_horn_rule")
            return
        rule = HornRule(
            antecedents=tuple(
                replace(
                    item,
                    source_id=source_id,
                    source_text=source_text,
                    premise_id=premise_id,
                    candidate_label=candidate_label,
                )
                for item in antecedents
            ),
            consequent=replace(
                consequent,
                source_id=source_id,
                source_text=source_text,
                premise_id=premise_id,
                candidate_label=candidate_label,
            ),
            source_id=source_id,
            premise_id=premise_id,
            derived_from_contraposition=False,
        )
        rules.append(rule)

    if isinstance(premise, ForallNode):
        instantiation = instantiate_forall(premise, constants)
        if instantiation.status != "ok":
            unsupported_features.extend(instantiation.warnings or [])
            return warnings, unsupported_features, rules, facts
        if not instantiation.instances:
            warnings.extend(instantiation.warnings or [])
            return warnings, unsupported_features, rules, facts
        for instance in instantiation.instances:
            if isinstance(instance, ImpliesNode):
                add_rule(instance)
            elif isinstance(instance, AndNode):
                for operand in instance.operands:
                    add_fact(operand)
            else:
                add_fact(instance)
        return warnings, unsupported_features, rules, facts

    if isinstance(premise, ExistsNode):
        unsupported_features.append("unsupported_existential_premise_witness_creation")
        return warnings, unsupported_features, rules, facts

    if isinstance(premise, ImpliesNode):
        add_rule(premise)
        return warnings, unsupported_features, rules, facts

    if isinstance(premise, AndNode):
        for operand in premise.operands:
            add_fact(operand)
        return warnings, unsupported_features, rules, facts

    if isinstance(premise, PredNode | NotNode):
        add_fact(premise)
        return warnings, unsupported_features, rules, facts

    unsupported_features.append("unsupported_premise_node_for_horn")
    return warnings, unsupported_features, rules, facts


def _literals_from_antecedent(node: LogicNode) -> list[HornLiteral] | None:
    if isinstance(node, AndNode):
        items: list[HornLiteral] = []
        for operand in node.operands:
            literal = _literal_from_node(operand)
            if literal is None:
                return None
            items.append(literal)
        return items
    literal = _literal_from_node(node)
    if literal is None:
        return None
    return [literal]


def _literal_from_node(node: LogicNode) -> HornLiteral | None:
    if isinstance(node, PredNode):
        arguments: list[HornTerm] = []
        for term in node.args:
            if isinstance(term, ConstTerm):
                arguments.append(HornTerm(name=term.name, is_variable=False, domain=term.domain))
            elif isinstance(term, VarTerm):
                arguments.append(HornTerm(name=term.name, is_variable=True, domain=None))
            else:
                return None
        return HornLiteral(
            predicate=node.name,
            arguments=tuple(arguments),
            negated=False,
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
        )
    if isinstance(node, NotNode) and isinstance(node.body, PredNode):
        base = _literal_from_node(node.body)
        if base is None:
            return None
        return replace(
            base,
            negated=True,
            source_id=node.source_id,
            source_text=node.source_text,
            premise_id=node.premise_id,
            candidate_label=node.candidate_label,
        )
    return None


def _forward_chain(
    facts: dict[HornLiteral, set[int]],
    rules: Sequence[HornRule],
) -> tuple[dict[HornLiteral, set[int]], list[HornDerivation]]:
    known = {literal: set(support) for literal, support in facts.items()}
    derivations: list[HornDerivation] = []
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if not rule.is_ground:
                continue
            if any(antecedent not in known for antecedent in rule.antecedents):
                continue
            if rule.consequent in known:
                continue
            support: set[int] = set()
            for antecedent in rule.antecedents:
                support.update(known.get(antecedent, set()))
            if rule.premise_id is not None:
                support.add(rule.premise_id)
            known[rule.consequent] = support
            derivations.append(
                HornDerivation(
                    literal=rule.consequent,
                    method="contraposition" if rule.derived_from_contraposition else "forward_chaining",
                    source_premise_ids=sorted(support),
                    supporting_literals=list(rule.antecedents),
                    rule_text=rule.render(),
                )
            )
            changed = True
    return known, derivations


def _unique_strings(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
