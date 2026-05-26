"""Deterministic answer selection for Yes/No/Unknown and local MCQ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.output.decision.models import AnswerDecisionResult, CandidateEntailment


def decide_answer(
    question_type: str,
    entailments: list[CandidateEntailment],
    *,
    question_text: str | None = None,
) -> AnswerDecisionResult:
    if not entailments:
        return AnswerDecisionResult(
            answer="Unknown",
            explanation="No candidate claim is available for symbolic verification.",
            status="partial",
            used_premise_ids=[],
            warnings=["no_candidates"],
        )

    if question_type == "mcq":
        return _decide_mcq(entailments, question_text=question_text)
    if question_type in {"yes_no_unknown", "numeric", "open_ended", "ambiguous"}:
        return _decide_yes_no_unknown(entailments[0])
    return _decide_yes_no_unknown(entailments[0])


def _decide_yes_no_unknown(entailment: CandidateEntailment) -> AnswerDecisionResult:
    claim_entailed = entailment.claim_result.entailed
    negated_entailed = entailment.negated_claim_result.entailed
    used = sorted(set(entailment.claim_result.used_premise_ids) | set(entailment.negated_claim_result.used_premise_ids))
    warnings = _merge_warnings(entailment)

    if claim_entailed and not negated_entailed:
        return AnswerDecisionResult(
            answer="Yes",
            explanation="The claim is entailed by the available premises.",
            status=_decision_status(entailment),
            used_premise_ids=used,
            warnings=warnings,
        )
    if negated_entailed and not claim_entailed:
        return AnswerDecisionResult(
            answer="No",
            explanation="The negated claim is entailed by the available premises.",
            status=_decision_status(entailment),
            used_premise_ids=used,
            warnings=warnings,
        )
    return AnswerDecisionResult(
        answer="Unknown",
        explanation="Neither the claim nor its negation is uniquely entailed.",
        status=_decision_status(entailment),
        used_premise_ids=used,
        warnings=warnings,
    )


@dataclass(frozen=True)
class _ProofProfile:
    label: str
    depth: int
    premise_count: int
    derived_count: int


def _decide_mcq(entailments: list[CandidateEntailment], *, question_text: str | None = None) -> AnswerDecisionResult:
    provable = [item for item in entailments if item.claim_result.entailed and not item.negated_claim_result.entailed]
    warnings: list[str] = []
    used_premise_ids: set[int] = set()
    status = "ok"
    for item in entailments:
        used_premise_ids.update(item.claim_result.used_premise_ids)
        used_premise_ids.update(item.negated_claim_result.used_premise_ids)
        warnings.extend(_merge_warnings(item))
        if item.claim_result.status != "ok" or item.negated_claim_result.status != "ok":
            status = "partial"

    if len(provable) == 1:
        winner = provable[0]
        return AnswerDecisionResult(
            answer=winner.label,
            explanation=f"Exactly one option ({winner.label}) is entailed by the premises.",
            status=status,
            used_premise_ids=sorted(used_premise_ids),
            warnings=_unique(warnings),
        )
    if len(provable) > 1:
        policy = _mcq_policy_from_question(question_text)
        if policy == "strongest_conclusion":
            decision = _choose_strongest_conclusion(provable)
            if decision is not None:
                warnings.append("mcq_policy_applied:strongest_conclusion")
                return AnswerDecisionResult(
                    answer=decision.label,
                    explanation=f"Multiple options are provable; selected {decision.label} as the strongest supported conclusion.",
                    status=status,
                    used_premise_ids=sorted(used_premise_ids),
                    warnings=_unique(warnings),
                    decision_metadata={
                        "policy": "strongest_conclusion",
                        "scores": [_serialize_profile(_proof_profile(item)) for item in provable],
                    },
                )
        if policy == "fewest_premises":
            decision = _choose_fewest_premises(provable)
            if decision is not None:
                warnings.append("mcq_policy_applied:fewest_premises")
                return AnswerDecisionResult(
                    answer=decision.label,
                    explanation=f"Multiple options are provable; selected {decision.label} because it uses the fewest premises.",
                    status=status,
                    used_premise_ids=sorted(used_premise_ids),
                    warnings=_unique(warnings),
                    decision_metadata={
                        "policy": "fewest_premises",
                        "scores": [_serialize_profile(_proof_profile(item)) for item in provable],
                    },
                )
    if len(provable) == 0:
        warnings.append("mcq_no_unique_provable_option")
    else:
        warnings.append("mcq_multiple_provable_options")
    return AnswerDecisionResult(
        answer="Unknown",
        explanation="No unique MCQ option is provable from the current symbolic evidence.",
        status=status,
        used_premise_ids=sorted(used_premise_ids),
        warnings=_unique(warnings),
    )


def _decision_status(entailment: CandidateEntailment):
    if entailment.claim_result.status != "ok" or entailment.negated_claim_result.status != "ok":
        return "partial"
    return "ok"


def _merge_warnings(entailment: CandidateEntailment) -> list[str]:
    return _unique(
        [
            *entailment.claim_result.warnings,
            *entailment.negated_claim_result.warnings,
            *entailment.claim_result.unsupported_features,
            *entailment.negated_claim_result.unsupported_features,
        ]
    )


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _mcq_policy_from_question(question_text: str | None) -> Literal["strongest_conclusion", "fewest_premises"] | None:
    lowered = (question_text or "").lower()
    if not lowered:
        return None
    if "strongest conclusion" in lowered or "most strongly supported conclusion" in lowered:
        return "strongest_conclusion"
    if "fewest premises" in lowered or "least premises" in lowered or "minimum premises" in lowered:
        return "fewest_premises"
    return None


def _proof_profile(entailment: CandidateEntailment) -> _ProofProfile:
    claim = entailment.claim_result
    depth = sum(1 for step in claim.derived_facts if step.method in {"forward_chaining", "contraposition"})
    return _ProofProfile(
        label=entailment.label,
        depth=depth,
        premise_count=len(set(claim.used_premise_ids)),
        derived_count=len(claim.derived_facts),
    )


def _serialize_profile(profile: _ProofProfile) -> dict[str, int | str]:
    return {
        "label": profile.label,
        "depth": profile.depth,
        "premise_count": profile.premise_count,
        "derived_count": profile.derived_count,
    }


def _choose_strongest_conclusion(provable: list[CandidateEntailment]) -> CandidateEntailment | None:
    scored = [(item, _proof_profile(item)) for item in provable]
    max_depth = max(profile.depth for _, profile in scored)
    top_by_depth = [(item, profile) for item, profile in scored if profile.depth == max_depth]
    if len(top_by_depth) == 1 and max_depth > 0:
        return top_by_depth[0][0]
    max_derived = max(profile.derived_count for _, profile in top_by_depth)
    top_by_derived = [(item, profile) for item, profile in top_by_depth if profile.derived_count == max_derived]
    if len(top_by_derived) == 1 and max_derived > 0:
        return top_by_derived[0][0]
    max_premises = max(profile.premise_count for _, profile in top_by_derived)
    finalists = [item for item, profile in top_by_derived if profile.premise_count == max_premises]
    if len(finalists) == 1 and max_premises > 0:
        return finalists[0]
    return None


def _choose_fewest_premises(provable: list[CandidateEntailment]) -> CandidateEntailment | None:
    scored = [(item, _proof_profile(item)) for item in provable]
    min_premises = min(profile.premise_count for _, profile in scored)
    finalists = [(item, profile) for item, profile in scored if profile.premise_count == min_premises]
    if len(finalists) == 1:
        return finalists[0][0]
    min_depth = min(profile.depth for _, profile in finalists)
    depth_finalists = [item for item, profile in finalists if profile.depth == min_depth]
    if len(depth_finalists) == 1:
        return depth_finalists[0]
    return None
