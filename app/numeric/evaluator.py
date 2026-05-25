"""Deterministic numeric evaluation helpers."""

from __future__ import annotations

from typing import Mapping, Sequence

from app.logic.ast import ArithNode, ConstTerm, NumRefNode, NumberTerm, NumericExpression, VarTerm

from .extractors import render_number, term_to_entity
from .models import DerivedNumericFact, NumericComparison, NumericQuantity
from .routing import NumericRoutingRequest


def evaluate_comparisons(
    comparisons: Sequence[NumericComparison],
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
) -> tuple[list[DerivedNumericFact], list[NumericRoutingRequest], list[str]]:
    derived: list[DerivedNumericFact] = []
    routing_requests: list[NumericRoutingRequest] = []
    warnings: list[str] = []
    seen_expressions: set[str] = set()

    for comparison in comparisons:
        if (
            comparison.origin == "frame"
            and comparison.left_expression is None
            and comparison.right_expression is None
            and comparison.right_value is None
            and comparison.right_expression_text is not None
        ):
            # Frame-level arithmetic slots are extracted for traceability, while
            # deterministic arithmetic evaluation runs on compiled AST comparisons.
            continue

        expression_text = _comparison_expression_text(comparison)
        if expression_text in seen_expressions:
            continue
        seen_expressions.add(expression_text)

        notes: list[tuple[str, float, str | None]] = []
        try:
            left_value = _resolve_left_value(comparison, quantities, notes)
            right_value = _resolve_right_value(comparison, quantities, notes)
            comparison_result = _apply_compare(comparison.op, left_value, right_value)
        except (LookupError, ValueError, ZeroDivisionError) as exc:
            reason = _constraint_reason(exc)
            warnings.append(
                f"Numeric comparison {expression_text!r} from {comparison.provenance.source_id} was routed to Z3 constraints: {reason}."
            )
            routing_requests.append(
                NumericRoutingRequest(
                    expression=expression_text,
                    reason=reason,
                    source=comparison.provenance,
                )
            )
            continue

        for note_text, note_value, note_unit in notes:
            derived.append(
                DerivedNumericFact(
                    name="numeric_expression",
                    value=note_value,
                    expression=f"{note_text} = {render_number(note_value)}",
                    unit=note_unit,
                    sources=[comparison.provenance],
                )
            )

        derived.append(
            DerivedNumericFact(
                name="numeric_comparison",
                value=comparison_result,
                expression=f"{expression_text} -> {str(comparison_result).lower()}",
                sources=[comparison.provenance],
            )
        )

    return derived, routing_requests, warnings


def quantity_as_fact(quantity: NumericQuantity) -> DerivedNumericFact:
    entity_text = quantity.entity if quantity.entity else "*"
    unit_text = f" {quantity.unit}" if quantity.unit else ""
    return DerivedNumericFact(
        name="numeric_quantity",
        value=quantity.value,
        expression=f"{quantity.attribute}({entity_text}) = {render_number(quantity.value)}{unit_text}",
        unit=quantity.unit,
        sources=[quantity.provenance],
    )


def _resolve_left_value(
    comparison: NumericComparison,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if comparison.left_expression is not None:
        return _evaluate_numeric_expression(comparison.left_expression, quantities, notes)

    if comparison.left_attribute is None:
        raise LookupError("left_attribute_missing")

    quantity = _lookup_quantity(
        quantities,
        attribute=comparison.left_attribute,
        entity=comparison.left_entity,
        unit=None,
    )
    if quantity is None:
        raise LookupError("left_numeric_reference_missing")
    return quantity.value


def _resolve_right_value(
    comparison: NumericComparison,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if comparison.right_expression is not None:
        return _evaluate_numeric_expression(comparison.right_expression, quantities, notes)
    if comparison.right_value is not None:
        return comparison.right_value
    raise LookupError("right_expression_missing")


def _evaluate_numeric_expression(
    expression: NumericExpression,
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    notes: list[tuple[str, float, str | None]],
) -> float:
    if isinstance(expression, NumberTerm):
        return float(expression.value)

    if isinstance(expression, NumRefNode):
        entity = term_to_entity(expression.args[0]) if expression.args else None
        quantity = _lookup_quantity(quantities, attribute=expression.name, entity=entity, unit=expression.unit)
        if quantity is None:
            raise LookupError(f"num_ref_missing:{expression.name}")
        return quantity.value

    if isinstance(expression, ArithNode):
        operand_values = [_evaluate_numeric_expression(operand, quantities, notes) for operand in expression.operands]
        result = _evaluate_arithmetic(expression.op, operand_values)
        notes.append((_numeric_expression_to_text(expression), result, None))
        return result

    if isinstance(expression, ConstTerm | VarTerm):
        raise LookupError("symbolic_term_requires_z3")

    raise ValueError(f"Unsupported numeric expression type: {type(expression)!r}")


def _evaluate_arithmetic(op: str, operand_values: Sequence[float]) -> float:
    if not operand_values:
        raise ValueError("numeric_operation_missing_operands")

    if op == "add":
        return float(sum(operand_values))
    if op == "sub":
        head, *rest = operand_values
        return float(head - sum(rest))
    if op == "mul":
        value = 1.0
        for operand in operand_values:
            value *= operand
        return float(value)
    if op == "div":
        head, *rest = operand_values
        value = float(head)
        for operand in rest:
            if operand == 0:
                raise ZeroDivisionError("numeric_division_by_zero")
            value /= operand
        return value
    if op == "percentage_of":
        if len(operand_values) != 2:
            raise ValueError("percentage_of_requires_two_operands")
        return float((operand_values[0] / 100.0) * operand_values[1])
    if op == "average":
        return float(sum(operand_values) / len(operand_values))
    if op == "weighted_average":
        if len(operand_values) < 2 or len(operand_values) % 2 != 0:
            raise ValueError("weighted_average_requires_value_weight_pairs")
        weighted_sum = 0.0
        weight_total = 0.0
        for index in range(0, len(operand_values), 2):
            value = operand_values[index]
            weight = operand_values[index + 1]
            weighted_sum += value * weight
            weight_total += weight
        if weight_total == 0:
            raise ValueError("weighted_average_requires_nonzero_total_weight")
        return float(weighted_sum / weight_total)
    if op in {"date_add", "time_add"}:
        return float(sum(operand_values))

    raise ValueError(f"unsupported_numeric_operator:{op}")


def _lookup_quantity(
    quantities: Mapping[tuple[str, str, str], NumericQuantity],
    *,
    attribute: str,
    entity: str | None,
    unit: str | None,
) -> NumericQuantity | None:
    normalized_attribute = _normalize_name(attribute)
    normalized_entity = (entity or "").strip().lower()
    normalized_unit = (unit or "").strip().lower()
    candidates = [
        (normalized_attribute, normalized_entity, normalized_unit),
        (normalized_attribute, normalized_entity, ""),
        (normalized_attribute, "", normalized_unit),
        (normalized_attribute, "", ""),
    ]
    for key in candidates:
        quantity = quantities.get(key)
        if quantity is not None:
            return quantity

    if normalized_unit == "":
        for key, quantity in quantities.items():
            if key[0] == normalized_attribute and key[1] == normalized_entity:
                return quantity
        if normalized_entity:
            for key, quantity in quantities.items():
                if key[0] == normalized_attribute and key[1] == "":
                    return quantity
    return None


def _numeric_expression_to_text(expression: NumericExpression) -> str:
    if isinstance(expression, NumberTerm):
        if expression.unit:
            return f"{render_number(float(expression.value))} {expression.unit}"
        return render_number(float(expression.value))
    if isinstance(expression, NumRefNode):
        if expression.args:
            args = ", ".join(_term_to_text(item) for item in expression.args)
            return f"{expression.name}({args})"
        return expression.name
    if isinstance(expression, ArithNode):
        args = ", ".join(_numeric_expression_to_text(item) for item in expression.operands)
        return f"{expression.op}({args})"
    if isinstance(expression, ConstTerm | VarTerm):
        return _term_to_text(expression)
    return "expr"


def _term_to_text(term: ConstTerm | VarTerm | NumberTerm) -> str:
    if isinstance(term, ConstTerm | VarTerm):
        return term.name
    if isinstance(term, NumberTerm):
        return render_number(float(term.value))
    return "term"


def _comparison_expression_text(comparison: NumericComparison) -> str:
    left = comparison.left_attribute
    if left is None and comparison.left_expression is not None:
        left = _numeric_expression_to_text(comparison.left_expression)
    if left is None:
        left = "value"
    right = comparison.right_expression_text
    if right is None and comparison.right_expression is not None:
        right = _numeric_expression_to_text(comparison.right_expression)
    if right is None and comparison.right_value is not None:
        right = render_number(comparison.right_value)
    if right is None:
        right = "expr"
    return f"{left} {comparison.op} {right}"


def _apply_compare(op: str, left: float, right: float) -> bool:
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == "=":
        return _numeric_equal(left, right)
    if op == "!=":
        return not _numeric_equal(left, right)
    if op == ">=":
        return left >= right
    if op == ">":
        return left > right
    raise ValueError(f"Unsupported comparison operator: {op}")


def _constraint_reason(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return "numeric_constraint_requires_z3"
    return message


def _normalize_name(text: str) -> str:
    lowered = "".join(character.lower() if character.isalnum() else "_" for character in text)
    collapsed = "_".join(part for part in lowered.split("_") if part)
    return collapsed or "value"


def _numeric_equal(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-9
