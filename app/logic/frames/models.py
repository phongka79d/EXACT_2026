"""Compact parse-frame models and parsers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias

NUMERIC_OPERATORS = frozenset({"<", "<=", "=", "!=", ">=", ">"})
ARITHMETIC_OPERATORS = frozenset(
    {"add", "sub", "mul", "div", "percentage_of", "average", "weighted_average", "date_add", "time_add"}
)
COMPOUND_OPERATORS = frozenset({"and", "or"})


@dataclass(frozen=True)
class PredicateSlot:
    type: Literal["predicate"]
    entity: str
    name: str
    polarity: bool = True


@dataclass(frozen=True)
class NumericConditionSlot:
    type: Literal["numeric_condition"]
    entity: str
    attribute: str
    op: str
    value: float | int | None = None
    unit: str | None = None
    expression: "ArithmeticExpressionSlot" | None = None


@dataclass(frozen=True)
class NumericValueSlot:
    type: Literal["numeric_value"]
    attribute: str
    value: float | int
    entity: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class ArithmeticExpressionSlot:
    type: Literal["arithmetic_expression"]
    op: str
    operands: list[Any]


@dataclass(frozen=True)
class EntityRelationSlot:
    type: Literal["entity_relation"]
    subject: str
    relation: str
    object: str
    polarity: bool = True


FrameSlot: TypeAlias = (
    PredicateSlot
    | NumericConditionSlot
    | NumericValueSlot
    | ArithmeticExpressionSlot
    | EntityRelationSlot
)


@dataclass(frozen=True)
class RuleFrame:
    kind: Literal["rule"]
    scope: str
    if_slots: list[FrameSlot]
    then_slots: list[FrameSlot]
    source_id: str
    source_text: str
    premise_id: int
    warnings: list[str]


@dataclass(frozen=True)
class FactFrame:
    kind: Literal["fact"]
    facts: list[FrameSlot]
    source_id: str
    source_text: str
    premise_id: int
    warnings: list[str]
    entity: str | None = None


@dataclass(frozen=True)
class ClaimFrame:
    kind: Literal["claim"]
    answer_type: str
    claim: FrameSlot
    source_id: str
    source_text: str
    candidate_label: str
    warnings: list[str]


@dataclass(frozen=True)
class CompoundFrame:
    kind: Literal["compound"]
    operator: str
    parts: list[FrameSlot]
    source_id: str
    source_text: str
    premise_id: int | None
    candidate_label: str | None
    warnings: list[str]


@dataclass(frozen=True)
class AmbiguousFrame:
    kind: Literal["ambiguous"]
    reason: str
    source_id: str
    source_text: str
    warnings: list[str]
    options: list[str]
    premise_id: int | None = None
    candidate_label: str | None = None


ParseFrame: TypeAlias = RuleFrame | FactFrame | ClaimFrame | CompoundFrame | AmbiguousFrame


def parse_slot(payload: Mapping[str, Any]) -> FrameSlot:
    slot_type = _require_string(payload, "type")

    if slot_type == "predicate":
        return PredicateSlot(
            type="predicate",
            entity=_require_string(payload, "entity"),
            name=_require_string(payload, "name"),
            polarity=_require_bool(payload, "polarity", default=True),
        )
    if slot_type == "numeric_condition":
        expression_payload = payload.get("expression")
        expression = parse_slot(expression_payload) if isinstance(expression_payload, Mapping) else None
        if expression is not None and not isinstance(expression, ArithmeticExpressionSlot):
            raise ValueError("`numeric_condition.expression` must be an arithmetic_expression slot")
        return NumericConditionSlot(
            type="numeric_condition",
            entity=_require_string(payload, "entity"),
            attribute=_require_string(payload, "attribute"),
            op=_require_string(payload, "op"),
            value=_optional_number(payload.get("value")),
            unit=_optional_string(payload.get("unit")),
            expression=expression,
        )
    if slot_type == "numeric_value":
        return NumericValueSlot(
            type="numeric_value",
            attribute=_require_string(payload, "attribute"),
            value=_require_number(payload, "value"),
            entity=_optional_string(payload.get("entity")),
            unit=_optional_string(payload.get("unit")),
        )
    if slot_type == "arithmetic_expression":
        operands = payload.get("operands")
        if not isinstance(operands, list):
            raise ValueError("`arithmetic_expression.operands` must be a list")
        return ArithmeticExpressionSlot(
            type="arithmetic_expression",
            op=_require_string(payload, "op"),
            operands=list(operands),
        )
    if slot_type == "entity_relation":
        return EntityRelationSlot(
            type="entity_relation",
            subject=_require_string(payload, "subject"),
            relation=_require_string(payload, "relation"),
            object=_require_string(payload, "object"),
            polarity=_require_bool(payload, "polarity", default=True),
        )

    raise ValueError(f"Unsupported frame slot type: {slot_type}")


def parse_frame(payload: Mapping[str, Any]) -> ParseFrame:
    kind = _require_string(payload, "kind")

    if kind == "rule":
        return RuleFrame(
            kind="rule",
            scope=_require_string(payload, "scope"),
            if_slots=_require_slot_list(payload, "if"),
            then_slots=_require_slot_list(payload, "then"),
            source_id=_require_string(payload, "source_id"),
            source_text=_require_string(payload, "source_text"),
            premise_id=_require_int(payload, "premise_id"),
            warnings=_require_string_list(payload.get("warnings"), "warnings"),
        )
    if kind == "fact":
        return FactFrame(
            kind="fact",
            entity=_optional_string(payload.get("entity")),
            facts=_require_slot_list(payload, "facts"),
            source_id=_require_string(payload, "source_id"),
            source_text=_require_string(payload, "source_text"),
            premise_id=_require_int(payload, "premise_id"),
            warnings=_require_string_list(payload.get("warnings"), "warnings"),
        )
    if kind == "claim":
        claim_payload = payload.get("claim")
        if not isinstance(claim_payload, Mapping):
            raise ValueError("`claim.claim` must be a frame slot object")
        return ClaimFrame(
            kind="claim",
            answer_type=_require_string(payload, "answer_type"),
            claim=parse_slot(claim_payload),
            source_id=_require_string(payload, "source_id"),
            source_text=_require_string(payload, "source_text"),
            candidate_label=_require_string(payload, "candidate_label"),
            warnings=_require_string_list(payload.get("warnings"), "warnings"),
        )
    if kind == "compound":
        return CompoundFrame(
            kind="compound",
            operator=_require_string(payload, "operator"),
            parts=_require_slot_list(payload, "parts"),
            source_id=_require_string(payload, "source_id"),
            source_text=_require_string(payload, "source_text"),
            premise_id=_optional_int(payload.get("premise_id")),
            candidate_label=_optional_string(payload.get("candidate_label")),
            warnings=_require_string_list(payload.get("warnings"), "warnings"),
        )
    if kind == "ambiguous":
        return AmbiguousFrame(
            kind="ambiguous",
            reason=_require_string(payload, "reason"),
            source_id=_require_string(payload, "source_id"),
            source_text=_require_string(payload, "source_text"),
            warnings=_require_string_list(payload.get("warnings"), "warnings"),
            options=_require_string_list(payload.get("options"), "options"),
            premise_id=_optional_int(payload.get("premise_id")),
            candidate_label=_optional_string(payload.get("candidate_label")),
        )

    raise ValueError(f"Unsupported frame kind: {kind}")


def _require_slot_list(payload: Mapping[str, Any], key: str) -> list[FrameSlot]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"`{key}` must be a list of frame slots")
    return [parse_slot(_require_mapping(item, key)) for item in value]


def _require_mapping(value: Any, key: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"`{key}` entries must be objects")
    return value


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{key}` must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Optional string value must be a non-empty string when provided")
    return value.strip()


def _require_number(payload: Mapping[str, Any], key: str) -> float | int:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"`{key}` must be numeric")
    return value


def _optional_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Optional numeric value must be numeric when provided")
    return value


def _require_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"`{key}` must be an integer")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError("Optional integer value must be an integer when provided")
    return value


def _require_bool(payload: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"`{key}` must be a boolean")
    return value


def _require_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"`{field_name}` must be a list of strings")
    return list(value)
