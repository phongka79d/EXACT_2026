"""Typed models for Horn-style symbolic reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class HornTerm:
    name: str
    is_variable: bool = False
    domain: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("HornTerm.name must be non-empty")


@dataclass(frozen=True)
class HornLiteral:
    predicate: str
    arguments: tuple[HornTerm, ...]
    negated: bool = False
    source_id: str | None = field(default=None, compare=False)
    source_text: str | None = field(default=None, compare=False)
    premise_id: int | None = field(default=None, compare=False)
    candidate_label: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.predicate.strip():
            raise ValueError("HornLiteral.predicate must be non-empty")

    def render(self) -> str:
        args = ", ".join(term.name for term in self.arguments)
        core = f"{self.predicate}({args})" if args else self.predicate
        return f"not {core}" if self.negated else core

    @property
    def is_ground(self) -> bool:
        return all(not term.is_variable for term in self.arguments)


@dataclass(frozen=True)
class HornRule:
    antecedents: tuple[HornLiteral, ...]
    consequent: HornLiteral
    source_id: str | None = None
    premise_id: int | None = None
    derived_from_contraposition: bool = False

    def __post_init__(self) -> None:
        if not self.antecedents:
            raise ValueError("HornRule.antecedents must be non-empty")

    def render(self) -> str:
        left = " and ".join(item.render() for item in self.antecedents)
        return f"{left} -> {self.consequent.render()}"

    @property
    def is_ground(self) -> bool:
        if not self.consequent.is_ground:
            return False
        return all(item.is_ground for item in self.antecedents)


@dataclass(frozen=True)
class HornDerivation:
    literal: HornLiteral
    method: Literal["premise_fact", "forward_chaining", "contraposition", "schema_match", "existential_witness"]
    source_premise_ids: list[int] = field(default_factory=list)
    supporting_literals: list[HornLiteral] = field(default_factory=list)
    rule_text: str | None = None


@dataclass(frozen=True)
class HornEntailmentResult:
    entailed: bool
    status: Literal["ok", "solver_capability_gap"] = "ok"
    used_premise_ids: list[int] = field(default_factory=list)
    derived_facts: list[HornDerivation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported_features: list[str] = field(default_factory=list)
    route: str = "horn"
    confidence: float = 1.0
    confidence_penalty: float = 0.0
    solver_metadata: dict[str, object] = field(default_factory=dict)
