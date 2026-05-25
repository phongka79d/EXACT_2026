import unittest

from app.output import build_explanation_ready_trace
from app.tracing import DebugTrace, NumericDerivation, ProofTraceStep, SourceCitation


class ProofTraceReadinessTests(unittest.TestCase):
    def test_builds_explanation_ready_view_with_ordered_sections(self):
        trace = DebugTrace(
            sample_id="sample-1",
            record_id=10,
            question_id=2,
            status="partial",
            proof_trace=[
                ProofTraceStep(
                    step_id="numeric_layer",
                    action="extract_evaluate_numeric_facts",
                    solver_route="numeric",
                    status="ok",
                    used_premise_ids=[1],
                    derived_facts=["gpa(mai) >= 7.0"],
                    numeric_derivations=[
                        NumericDerivation(
                            name="gpa_threshold",
                            value=7.0,
                            unit="gpa",
                            expression="gpa(mai) >= 7.0",
                            sources=[
                                SourceCitation(
                                    source_id="premise_0001",
                                    source_text="Mai has GPA 7.0.",
                                    premise_id=1,
                                )
                            ],
                        )
                    ],
                    citations=[SourceCitation(source_id="premise_0001", source_text="Mai has GPA 7.0.", premise_id=1)],
                    metadata={
                        "computed_values": [
                            {
                                "name": "gpa_threshold",
                                "value": 7.0,
                                "unit": "gpa",
                                "expression": "gpa(mai) >= 7.0",
                                "sources": [
                                    {
                                        "source_id": "premise_0001",
                                        "source_text": "Mai has GPA 7.0.",
                                        "premise_id": 1,
                                    }
                                ],
                            }
                        ]
                    },
                ),
                ProofTraceStep(
                    step_id="solver_claim_A",
                    action="prove_claim",
                    solver_route="horn",
                    status="ok",
                    used_premise_ids=[1],
                    derived_facts=["eligible(mai)", "allowed(mai) [eligible(mai) -> allowed(mai)]"],
                    citations=[SourceCitation(source_id="premise_0001", source_text="Mai is eligible.", premise_id=1)],
                    metadata={
                        "candidate_label": "A",
                        "confidence": 1.0,
                        "confidence_penalty": 0.0,
                        "premise_facts": ["eligible(mai)"],
                        "route_details": {
                            "route_label": "horn",
                            "status": "ok",
                            "used_contraposition": False,
                            "used_quantifier_instantiation": True,
                        },
                    },
                ),
                ProofTraceStep(
                    step_id="solver_claim_B",
                    action="prove_claim",
                    solver_route="z3",
                    status="ok",
                    used_premise_ids=[1, 2],
                    derived_facts=["credits(mai) >= 120"],
                    metadata={
                        "confidence": 0.95,
                        "route_details": {"route_label": "z3", "status": "ok", "z3_status": "unsat_negated_claim"},
                    },
                ),
                ProofTraceStep(
                    step_id="solver_claim_C",
                    action="prove_claim",
                    solver_route="semantic_fallback",
                    status="partial",
                    used_premise_ids=[3],
                    derived_facts=["overlap_score=0.5"],
                    warnings=["semantic_fallback_used"],
                    metadata={
                        "confidence": 0.49,
                        "confidence_penalty": 0.51,
                        "route_details": {
                            "route_label": "semantic_fallback",
                            "status": "solver_capability_gap",
                            "fallback_used": True,
                            "fallback_overlap": 0.5,
                            "fallback_reason": "unsupported_nested_or_meta_logic",
                            "original_route": "z3",
                            "capability_gaps": ["unsupported_nested_or_meta_logic"],
                        },
                    },
                ),
                ProofTraceStep(
                    step_id="answer_decision",
                    action="select_public_answer",
                    solver_route="decision",
                    status="partial",
                    used_premise_ids=[1, 2, 3],
                    derived_facts=["answer=Unknown", "unknown_reason=mcq_multiple_provable_options"],
                    metadata={
                        "decision_details": {
                            "question_type": "mcq",
                            "selected_answer": "Unknown",
                            "unknown_reason": "mcq_multiple_provable_options",
                            "candidate_outcomes": [
                                {"label": "A", "claim_result": {"entailed": True}, "negated_claim_result": {"entailed": False}},
                                {"label": "B", "claim_result": {"entailed": True}, "negated_claim_result": {"entailed": False}},
                            ],
                        }
                    },
                ),
            ],
        )

        view = build_explanation_ready_trace(trace)

        self.assertEqual(view.ordered_step_ids[0], "trace_step_0001_numeric_layer")
        self.assertEqual(view.ordered_step_ids[-1], "trace_step_0005_answer_decision")
        self.assertEqual([item.route_label for item in view.solver_steps], ["horn", "z3", "semantic_fallback"])
        self.assertEqual(view.premise_facts[0].text, "eligible(mai)")
        self.assertEqual(view.numeric_computations[0].expression, "gpa(mai) >= 7.0")
        self.assertEqual(view.numeric_computations[0].sources[0].source_text, "Mai has GPA 7.0.")
        self.assertEqual(view.final_decision.decision_details["unknown_reason"], "mcq_multiple_provable_options")

    def test_runtime_safety_guard_rejects_reference_only_fields(self):
        trace = DebugTrace(
            sample_id="sample-unsafe",
            record_id=1,
            question_id=1,
            status="ok",
            proof_trace=[
                ProofTraceStep(
                    step_id="answer_decision",
                    action="select_public_answer",
                    solver_route="decision",
                    metadata={"decision_details": {"answer": "Yes"}},
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "reference-only"):
            build_explanation_ready_trace(trace)


if __name__ == "__main__":
    unittest.main()
