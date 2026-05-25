"""Deterministic semantic fallback with confidence caps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from app.logic.ast import LogicNode
from app.solver.horn.models import HornEntailmentResult

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({"the", "a", "an", "is", "are", "to", "of", "for", "and", "or", "if", "then", "when"})

FALLBACK_MAX_CONFIDENCE = 0.49
FALLBACK_CONFIDENCE_PENALTY = 0.51


@dataclass(frozen=True)
class SemanticFallbackInput:
    premises_nl: Sequence[str]
    candidate_text: str
    symbolic_reason: str
    claim_ast: LogicNode


def run_semantic_fallback(request: SemanticFallbackInput) -> HornEntailmentResult:
    candidate_tokens = _tokenize(request.candidate_text)
    premise_tokens = _tokenize(" ".join(request.premises_nl))
    overlap = _token_overlap(candidate_tokens, premise_tokens)
    entailed = overlap >= 0.45 and bool(candidate_tokens)

    return HornEntailmentResult(
        entailed=entailed,
        status="solver_capability_gap",
        warnings=["semantic_fallback_used", f"semantic_fallback_overlap={overlap:.3f}", request.symbolic_reason],
        unsupported_features=[request.symbolic_reason],
        route="semantic_fallback",
        confidence=min(FALLBACK_MAX_CONFIDENCE, overlap),
        confidence_penalty=FALLBACK_CONFIDENCE_PENALTY,
        solver_metadata={
            "fallback_used": True,
            "fallback_overlap": overlap,
            "fallback_reason": request.symbolic_reason,
            "z3_status": "not_run",
        },
    )


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.lower()) if token and token not in _STOPWORDS}


def _token_overlap(a: set[str], b: set[str]) -> float:
    if not a:
        return 0.0
    return len(a & b) / len(a)

