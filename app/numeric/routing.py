"""Numeric routing helpers for downstream Z3 constraint candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import NumericProvenance, Z3ConstraintCandidate


@dataclass(frozen=True)
class NumericRoutingRequest:
    expression: str
    reason: str
    source: NumericProvenance


def build_z3_constraint_candidates(requests: Sequence[NumericRoutingRequest]) -> list[Z3ConstraintCandidate]:
    return [
        Z3ConstraintCandidate(
            expression=request.expression,
            reason=request.reason,
            sources=[request.source],
        )
        for request in requests
    ]
