"""Typed logic AST node models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .terms import Term

COMPARE_OPERATORS = frozenset({"<", "<=", "=", "!=", ">=", ">"})
ARITHMETIC_OPERATORS = frozenset(
    {"add", "sub", "mul", "div", "percentage_of", "average", "weighted_average", "date_add", "time_add"}
)


@dataclass(frozen=True)
class QuantifiedVariable:
    name: str
    domain: str | None = None


@dataclass(frozen=True)
class PredNode:
    type: Literal["pred"]
    name: str
    args: list[Term]
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class NotNode:
    type: Literal["not"]
    body: "LogicNode"
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class AndNode:
    type: Literal["and"]
    operands: list["LogicNode"]
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class OrNode:
    type: Literal["or"]
    operands: list["LogicNode"]
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ImpliesNode:
    type: Literal["implies"]
    if_node: "LogicNode"
    then: "LogicNode"
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ForallNode:
    type: Literal["forall"]
    vars: list[QuantifiedVariable]
    body: "LogicNode"
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ExistsNode:
    type: Literal["exists"]
    vars: list[QuantifiedVariable]
    body: "LogicNode"
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class NumRefNode:
    type: Literal["num_ref"]
    name: str
    args: list[Term]
    unit: str | None = None
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ArithNode:
    type: Literal["arith"]
    op: str
    operands: list["NumericExpression"]
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


NumericExpression: TypeAlias = Term | NumRefNode | ArithNode


@dataclass(frozen=True)
class CompareNode:
    type: Literal["compare"]
    op: str
    left: NumericExpression
    right: NumericExpression
    source_id: str | None = None
    source_text: str | None = None
    premise_id: int | None = None
    candidate_label: str | None = None
    confidence: float | None = None


LogicNode: TypeAlias = (
    PredNode
    | NotNode
    | AndNode
    | OrNode
    | ImpliesNode
    | ForallNode
    | ExistsNode
    | CompareNode
    | ArithNode
    | NumRefNode
)
