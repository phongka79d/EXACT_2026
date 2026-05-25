"""Numeric precedence, conflict handling, and supplemental selection."""

from __future__ import annotations

from typing import Sequence

from .extractors import normalize_name
from .models import NumericComparison, NumericConflict, NumericProvenance, NumericQuantity


def resolve_quantities(
    *,
    ast_quantities: Sequence[NumericQuantity],
    frame_quantities: Sequence[NumericQuantity],
    supplemental_quantities: Sequence[NumericQuantity],
) -> tuple[dict[tuple[str, str, str], NumericQuantity], list[NumericQuantity], list[NumericConflict], list[str]]:
    warnings: list[str] = []
    conflicts: list[NumericConflict] = []
    resolved: dict[tuple[str, str, str], NumericQuantity] = {}

    for quantity in ast_quantities:
        resolved[quantity.key] = quantity

    for quantity in frame_quantities:
        existing = resolved.get(quantity.key)
        if existing is None:
            resolved[quantity.key] = quantity
            continue
        if not _numeric_equal(existing.value, quantity.value):
            conflicts.append(
                NumericConflict(
                    key=_stringify_key(quantity.key),
                    preferred_value=existing.value,
                    rejected_value=quantity.value,
                    preferred_origin=existing.origin,
                    rejected_origin=quantity.origin,
                    preferred_source_id=existing.provenance.source_id,
                    rejected_source_id=quantity.provenance.source_id,
                )
            )
            warnings.append(
                f"Numeric conflict detected for {quantity.attribute}: AST value {existing.value} was kept over frame value {quantity.value}."
            )

    supplemental_selected: list[NumericQuantity] = []
    for quantity in supplemental_quantities:
        existing = resolved.get(quantity.key)
        if existing is None:
            resolved[quantity.key] = quantity
            supplemental_selected.append(quantity)
            continue
        if _numeric_equal(existing.value, quantity.value):
            continue
        conflicts.append(
            NumericConflict(
                key=_stringify_key(quantity.key),
                preferred_value=existing.value,
                rejected_value=quantity.value,
                preferred_origin=existing.origin,
                rejected_origin=quantity.origin,
                preferred_source_id=existing.provenance.source_id,
                rejected_source_id=quantity.provenance.source_id,
            )
        )
        warnings.append(
            f"Numeric conflict detected for {quantity.attribute}: {existing.origin} value {existing.value} was kept over source-text value {quantity.value}."
        )

    return resolved, supplemental_selected, conflicts, warnings


def select_supplemental_comparisons(
    *,
    authoritative_comparisons: Sequence[NumericComparison],
    supplemental_comparisons: Sequence[NumericComparison],
) -> list[NumericComparison]:
    selected: list[NumericComparison] = []
    for supplemental in supplemental_comparisons:
        if any(
            _is_covered_by_authoritative_comparison(supplemental, authoritative)
            for authoritative in authoritative_comparisons
        ):
            continue
        selected.append(supplemental)
    return selected


def _is_covered_by_authoritative_comparison(
    supplemental: NumericComparison,
    authoritative: NumericComparison,
) -> bool:
    if not _same_provenance_target(supplemental.provenance, authoritative.provenance):
        return False
    if supplemental.op != authoritative.op:
        return False

    supplemental_value = _comparison_numeric_right_value(supplemental)
    authoritative_value = _comparison_numeric_right_value(authoritative)
    if supplemental_value is None or authoritative_value is None:
        return False
    if not _numeric_equal(supplemental_value, authoritative_value):
        return False

    return _attributes_compatible(authoritative.left_attribute, supplemental.left_attribute)


def _same_provenance_target(left: NumericProvenance, right: NumericProvenance) -> bool:
    return (
        left.source_id == right.source_id
        and left.premise_id == right.premise_id
        and left.candidate_label == right.candidate_label
    )


def _comparison_numeric_right_value(comparison: NumericComparison) -> float | None:
    if comparison.right_value is not None:
        return comparison.right_value
    if comparison.right_expression_text is None:
        return None
    try:
        return float(comparison.right_expression_text)
    except ValueError:
        return None


def _attributes_compatible(authoritative_attribute: str | None, supplemental_attribute: str | None) -> bool:
    if authoritative_attribute is None or supplemental_attribute is None:
        return True

    authoritative = normalize_name(authoritative_attribute)
    supplemental = normalize_name(supplemental_attribute)
    if authoritative == supplemental:
        return True
    if supplemental == "value":
        return True
    return supplemental in authoritative or authoritative in supplemental


def _numeric_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9


def _stringify_key(key: tuple[str, str, str]) -> str:
    attribute, entity, unit = key
    return f"{attribute}|{entity or '*'}|{unit or '*'}"
