import unittest

from app.logic.compiler import compile_frame_to_ast
from app.logic.frames import parse_frame
from app.numeric import build_numeric_layer


def _compile_premise_frame(payload: dict) -> tuple[object, object]:
    frame = parse_frame(payload)
    ast = compile_frame_to_ast(frame)
    return frame, ast


class NumericLayerTests(unittest.TestCase):
    def test_extracts_numeric_from_frames_and_ast_with_provenance(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "cumulative_gpa", "value": 7.2, "unit": "gpa"}],
                "source_id": "premise_0001",
                "source_text": "Mai has a cumulative GPA of 7.2.",
                "premise_id": 1,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertEqual(len(result.frame_quantities), 1)
        self.assertEqual(len(result.ast_quantities), 1)
        self.assertEqual(result.ast_quantities[0].attribute, "cumulative_gpa")
        self.assertEqual(result.ast_quantities[0].value, 7.2)
        self.assertEqual(result.ast_quantities[0].provenance.source_id, "premise_0001")
        self.assertEqual(result.ast_quantities[0].provenance.premise_id, 1)
        self.assertIn("numeric_facts", result.solver_context)
        self.assertGreaterEqual(len(result.solver_context["numeric_facts"]), 1)

    def test_evaluates_percentage_average_weighted_and_time_arithmetic(self):
        frames = []
        asts = []

        for payload in [
            {
                "kind": "fact",
                "entity": "exam",
                "facts": [{"type": "numeric_value", "attribute": "standard_score", "value": 80}],
                "source_id": "premise_0001",
                "source_text": "The standard score is 80.",
                "premise_id": 1,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "exam_score", "value": 60, "unit": "percent"}],
                "source_id": "premise_0002",
                "source_text": "Mai's exam score is 60%.",
                "premise_id": 2,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [
                    {
                        "type": "numeric_condition",
                        "entity": "Mai",
                        "attribute": "exam_score",
                        "op": ">=",
                        "expression": {
                            "type": "arithmetic_expression",
                            "op": "percentage_of",
                            "operands": [75, {"attribute": "standard_score", "entity": "exam"}],
                        },
                    }
                ],
                "source_id": "premise_0003",
                "source_text": "Mai must score at least 75% of the standard score.",
                "premise_id": 3,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "average_score", "value": 80}],
                "source_id": "premise_0004",
                "source_text": "Mai's average score is 80.",
                "premise_id": 4,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [
                    {
                        "type": "numeric_condition",
                        "entity": "Mai",
                        "attribute": "average_score",
                        "op": ">=",
                        "expression": {"type": "arithmetic_expression", "op": "average", "operands": [70, 80, 90]},
                    }
                ],
                "source_id": "premise_0005",
                "source_text": "Mai's average score must be at least the average of 70, 80, and 90.",
                "premise_id": 5,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "weighted_score", "value": 82.4}],
                "source_id": "premise_0006",
                "source_text": "Mai's weighted score is 82.4.",
                "premise_id": 6,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [
                    {
                        "type": "numeric_condition",
                        "entity": "Mai",
                        "attribute": "weighted_score",
                        "op": ">=",
                        "expression": {
                            "type": "arithmetic_expression",
                            "op": "weighted_average",
                            "operands": [80, 0.4, 84, 0.6],
                        },
                    }
                ],
                "source_id": "premise_0007",
                "source_text": "Mai's weighted score must be at least the weighted average.",
                "premise_id": 7,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "total_days", "value": 14, "unit": "days"}],
                "source_id": "premise_0008",
                "source_text": "Total allowed days are 14.",
                "premise_id": 8,
                "warnings": [],
            },
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [
                    {
                        "type": "numeric_condition",
                        "entity": "Mai",
                        "attribute": "total_days",
                        "op": "=",
                        "expression": {"type": "arithmetic_expression", "op": "time_add", "operands": [7, 7]},
                    }
                ],
                "source_id": "premise_0009",
                "source_text": "Total days equal 7 + 7.",
                "premise_id": 9,
                "warnings": [],
            },
        ]:
            frame, ast = _compile_premise_frame(payload)
            frames.append(frame)
            asts.append(ast)

        result = build_numeric_layer(premise_frames=frames, premise_asts=asts, candidate_asts=[])
        expressions = [fact.expression for fact in result.derived_facts]

        self.assertTrue(any("percentage_of" in expression for expression in expressions))
        self.assertTrue(any("average(70, 80, 90)" in expression for expression in expressions))
        self.assertTrue(any("weighted_average(80, 0.4, 84, 0.6)" in expression for expression in expressions))
        self.assertTrue(any("time_add(7, 7)" in expression for expression in expressions))
        self.assertEqual(result.z3_constraints, [])

    def test_source_text_supplement_and_duration_phrase(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "predicate", "entity": "Mai", "name": "eligible"}],
                "source_id": "premise_0101",
                "source_text": "Mai must submit within 30 days and has GPA 7.2.",
                "premise_id": 101,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertGreaterEqual(len(result.supplemental_quantities), 1)
        self.assertTrue(any(comparison.op == "<=" and comparison.right_value == 30.0 for comparison in result.comparisons))
        self.assertTrue(
            any(quantity.provenance.span_start is not None and quantity.provenance.span_end is not None for quantity in result.supplemental_quantities)
        )

    def test_source_text_comparison_does_not_duplicate_validated_frame_or_ast_constraint(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_condition", "entity": "Mai", "attribute": "total_days", "op": "<=", "value": 30, "unit": "days"}],
                "source_id": "premise_0102",
                "source_text": "Mai must submit within 30 days.",
                "premise_id": 102,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertGreaterEqual(len([comparison for comparison in result.comparisons if comparison.origin in {"ast", "frame"}]), 1)
        self.assertEqual([], [comparison for comparison in result.comparisons if comparison.origin == "source_text"])

    def test_ast_wins_conflicts_against_source_text(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "gpa", "value": 7.2}],
                "source_id": "premise_0201",
                "source_text": "Mai has cumulative GPA 6.5.",
                "premise_id": 201,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertGreaterEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].preferred_origin, "ast")
        self.assertTrue(any("kept over source-text value" in warning for warning in result.warnings))

    def test_unresolved_numeric_constraint_routes_to_z3(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [
                    {
                        "type": "numeric_condition",
                        "entity": "Mai",
                        "attribute": "exam_score",
                        "op": ">=",
                        "expression": {"type": "arithmetic_expression", "op": "percentage_of", "operands": [75, {"attribute": "standard_score"}]},
                    }
                ],
                "source_id": "premise_0301",
                "source_text": "Mai must score at least 75% of the standard score.",
                "premise_id": 301,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertGreaterEqual(len(result.z3_constraints), 1)
        self.assertTrue(any("percentage_of" in item.expression for item in result.z3_constraints))

    def test_numeric_routing_is_independent_of_record_like_ids(self):
        payload_a = {
            "kind": "fact",
            "entity": "Mai",
            "facts": [
                {
                    "type": "numeric_condition",
                    "entity": "Mai",
                    "attribute": "exam_score",
                    "op": ">=",
                    "expression": {"type": "arithmetic_expression", "op": "percentage_of", "operands": [75, {"attribute": "standard_score"}]},
                }
            ],
            "source_id": "record_0034_question_0000",
            "source_text": "Mai must score at least 75% of the standard score.",
            "premise_id": 401,
            "warnings": [],
        }
        payload_b = dict(payload_a)
        payload_b["source_id"] = "record_9999_question_1111"
        payload_b["premise_id"] = 402

        frame_a, ast_a = _compile_premise_frame(payload_a)
        frame_b, ast_b = _compile_premise_frame(payload_b)

        result_a = build_numeric_layer(premise_frames=[frame_a], premise_asts=[ast_a], candidate_asts=[])
        result_b = build_numeric_layer(premise_frames=[frame_b], premise_asts=[ast_b], candidate_asts=[])

        self.assertEqual([item.expression for item in result_a.z3_constraints], [item.expression for item in result_b.z3_constraints])
        self.assertEqual([item.reason for item in result_a.z3_constraints], [item.reason for item in result_b.z3_constraints])

    def test_numeric_parse_failures_emit_traceable_warnings(self):
        frame, ast = _compile_premise_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "predicate", "entity": "Mai", "name": "eligible"}],
                "source_id": "premise_0501",
                "source_text": "GPA requirement applies.",
                "premise_id": 501,
                "warnings": [],
            }
        )

        result = build_numeric_layer(premise_frames=[frame], premise_asts=[ast], candidate_asts=[])

        self.assertTrue(any("Numeric parse warning for premise_0501" in warning for warning in result.warnings))


if __name__ == "__main__":
    unittest.main()
