"""Deterministic answer selection for Yes/No/Unknown and local MCQ."""

from __future__ import annotations

from app.output.decision.models import AnswerDecisionResult, CandidateEntailment


def decide_answer(question_type: str, entailments: list[CandidateEntailment]) -> AnswerDecisionResult:
    if not entailments:
        return AnswerDecisionResult(
            answer="Unknown",
            explanation="No candidate claim is available for symbolic verification.",
            status="partial",
            used_premise_ids=[],
            warnings=["no_candidates"],
        )

    if question_type == "mcq":
        return _decide_mcq(entailments)
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


def _decide_mcq(entailments: list[CandidateEntailment]) -> AnswerDecisionResult:
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

