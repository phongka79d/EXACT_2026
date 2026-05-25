import unittest

from app.output.decision import CandidateEntailment, decide_answer
from app.solver.horn import HornEntailmentResult


def _result(*, entailed: bool, status: str = "ok", used: list[int] | None = None) -> HornEntailmentResult:
    return HornEntailmentResult(
        entailed=entailed,
        status=status,  # type: ignore[arg-type]
        used_premise_ids=list(used or []),
        derived_facts=[],
        warnings=[],
        unsupported_features=[],
    )


class AnswerDecisionTests(unittest.TestCase):
    def test_yes_no_unknown_decision_yes(self):
        entailment = CandidateEntailment(
            label="claim",
            question_type="yes_no_unknown",
            claim_result=_result(entailed=True, used=[1]),
            negated_claim_result=_result(entailed=False),
        )

        decision = decide_answer("yes_no_unknown", [entailment])

        self.assertEqual(decision.answer, "Yes")
        self.assertEqual(decision.status, "ok")
        self.assertEqual(decision.used_premise_ids, [1])

    def test_yes_no_unknown_decision_no(self):
        entailment = CandidateEntailment(
            label="claim",
            question_type="yes_no_unknown",
            claim_result=_result(entailed=False),
            negated_claim_result=_result(entailed=True, used=[3]),
        )

        decision = decide_answer("yes_no_unknown", [entailment])

        self.assertEqual(decision.answer, "No")
        self.assertEqual(decision.used_premise_ids, [3])

    def test_yes_no_unknown_decision_unknown(self):
        entailment = CandidateEntailment(
            label="claim",
            question_type="yes_no_unknown",
            claim_result=_result(entailed=False),
            negated_claim_result=_result(entailed=False),
        )

        decision = decide_answer("yes_no_unknown", [entailment])

        self.assertEqual(decision.answer, "Unknown")

    def test_mcq_decision_unique_option(self):
        decision = decide_answer(
            "mcq",
            [
                CandidateEntailment(
                    label="A",
                    question_type="mcq",
                    claim_result=_result(entailed=True, used=[1, 2]),
                    negated_claim_result=_result(entailed=False),
                ),
                CandidateEntailment(
                    label="B",
                    question_type="mcq",
                    claim_result=_result(entailed=False),
                    negated_claim_result=_result(entailed=False),
                ),
            ],
        )

        self.assertEqual(decision.answer, "A")
        self.assertEqual(decision.status, "ok")

    def test_mcq_decision_unknown_on_tie(self):
        decision = decide_answer(
            "mcq",
            [
                CandidateEntailment(
                    label="A",
                    question_type="mcq",
                    claim_result=_result(entailed=True),
                    negated_claim_result=_result(entailed=False),
                ),
                CandidateEntailment(
                    label="B",
                    question_type="mcq",
                    claim_result=_result(entailed=True),
                    negated_claim_result=_result(entailed=False),
                ),
            ],
        )

        self.assertEqual(decision.answer, "Unknown")
        self.assertIn("mcq_multiple_provable_options", decision.warnings)


if __name__ == "__main__":
    unittest.main()

