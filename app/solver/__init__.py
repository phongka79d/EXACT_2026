"""Symbolic solver interfaces for deterministic entailment checks."""

from .horn import HornEntailmentResult, HornLiteral, prove_entailment

__all__ = [
    "HornEntailmentResult",
    "HornLiteral",
    "prove_entailment",
]

