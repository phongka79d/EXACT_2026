"""Answer decision result contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.solver.horn import HornEntailmentResult


@dataclass(frozen=True)
class CandidateEntailment:
    label: str
    question_type: str
    claim_result: HornEntailmentResult
    negated_claim_result: HornEntailmentResult


@dataclass(frozen=True)
class AnswerDecisionResult:
    answer: str
    explanation: str
    status: Literal["ok", "partial"]
    used_premise_ids: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

