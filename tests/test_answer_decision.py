import unittest

from app.output.decision import CandidateEntailment, decide_answer
from app.solver.horn import HornDerivation, HornEntailmentResult, HornLiteral, HornTerm


def _derivation(method: str) -> HornDerivation:
    return HornDerivation(
        literal=HornLiteral(predicate="derived", arguments=(HornTerm(name="mai"),), negated=False),
        method=method,  # type: ignore[arg-type]
        source_premise_ids=[],
        supporting_literals=[],
    )


def _result(
    *,
    entailed: bool,
    status: str = "ok",
    used: list[int] | None = None,
    methods: list[str] | None = None,
) -> HornEntailmentResult:
    return HornEntailmentResult(
        entailed=entailed,
        status=status,  # type: ignore[arg-type]
        used_premise_ids=list(used or []),
        derived_facts=[_derivation(method) for method in (methods or [])],
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

    def test_mcq_strongest_conclusion_policy_prefers_deeper_proof(self):
        decision = decide_answer(
            "mcq",
            [
                CandidateEntailment(
                    label="A",
                    question_type="mcq",
                    claim_result=_result(entailed=True, used=[1, 2, 3], methods=["forward_chaining", "forward_chaining", "forward_chaining"]),
                    negated_claim_result=_result(entailed=False),
                ),
                CandidateEntailment(
                    label="C",
                    question_type="mcq",
                    claim_result=_result(entailed=True, used=[1, 2], methods=["forward_chaining"]),
                    negated_claim_result=_result(entailed=False),
                ),
            ],
            question_text="Which is the strongest conclusion?",
        )

        self.assertEqual(decision.answer, "A")
        self.assertIn("mcq_policy_applied:strongest_conclusion", decision.warnings)
        self.assertEqual(decision.decision_metadata.get("policy"), "strongest_conclusion")

    def test_mcq_fewest_premises_policy_prefers_unique_minimum_support(self):
        decision = decide_answer(
            "mcq",
            [
                CandidateEntailment(
                    label="A",
                    question_type="mcq",
                    claim_result=_result(entailed=True, used=[1, 2, 3], methods=["forward_chaining", "forward_chaining"]),
                    negated_claim_result=_result(entailed=False),
                ),
                CandidateEntailment(
                    label="B",
                    question_type="mcq",
                    claim_result=_result(entailed=True, used=[1], methods=["forward_chaining"]),
                    negated_claim_result=_result(entailed=False),
                ),
            ],
            question_text="Which conclusion follows with the fewest premises?",
        )

        self.assertEqual(decision.answer, "B")
        self.assertIn("mcq_policy_applied:fewest_premises", decision.warnings)
        self.assertEqual(decision.decision_metadata.get("policy"), "fewest_premises")


if __name__ == "__main__":
    unittest.main()
