"""Safe contraposition helpers for literal-to-literal Horn rules."""

from __future__ import annotations

from dataclasses import replace

from app.solver.horn.models import HornLiteral, HornRule


def derive_contrapositive(rule: HornRule) -> tuple[HornRule | None, str | None]:
    """Derive a safe contrapositive rule or return a rejection reason."""

    if len(rule.antecedents) != 1:
        return None, "unsafe_contraposition_non_literal_antecedent"

    antecedent = rule.antecedents[0]
    consequent = rule.consequent

    if not antecedent.arguments or not consequent.arguments:
        return None, "unsafe_contraposition_empty_arguments"
    if len(antecedent.arguments) != len(consequent.arguments):
        return None, "unsafe_contraposition_arity_mismatch"
    if not antecedent.is_ground or not consequent.is_ground:
        return None, "unsafe_contraposition_ungrounded_terms"

    for left, right in zip(antecedent.arguments, consequent.arguments, strict=True):
        if left.name != right.name:
            return None, "unsafe_contraposition_argument_position_mismatch"

    contra = HornRule(
        antecedents=(replace(consequent, negated=not consequent.negated),),
        consequent=replace(antecedent, negated=not antecedent.negated),
        source_id=rule.source_id,
        premise_id=rule.premise_id,
        derived_from_contraposition=True,
    )
    return contra, None


__all__ = ["derive_contrapositive"]

