"""Symbolic solver interfaces for deterministic entailment checks."""

from .horn import HornEntailmentResult, HornLiteral
from .router import SolverRequest, prove_entailment

__all__ = [
    "HornEntailmentResult",
    "HornLiteral",
    "SolverRequest",
    "prove_entailment",
]
