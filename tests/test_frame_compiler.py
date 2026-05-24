import unittest

from app.logic.ast import CompareNode, ForallNode, ImpliesNode, NotNode, PredNode
from app.logic.compiler import compile_frame_to_ast
from app.logic.frames import parse_frame
from app.logic.validation import validate_parse_frame


class FrameCompilerTests(unittest.TestCase):
    def test_rule_frame_compiles_to_forall_implies(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "students",
                "if": [{"type": "predicate", "entity": "student", "name": "meets_requirements"}],
                "then": [{"type": "predicate", "entity": "student", "name": "can_graduate"}],
                "source_id": "premise_0001",
                "source_text": "If a student meets requirements, they can graduate.",
                "premise_id": 1,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)

        self.assertIsInstance(ast, ForallNode)
        self.assertIsInstance(ast.body, ImpliesNode)
        self.assertEqual(ast.source_id, "premise_0001")
        self.assertEqual(ast.source_text, "If a student meets requirements, they can graduate.")
        self.assertEqual(ast.premise_id, 1)

    def test_fact_numeric_value_compiles_to_compare(self):
        frame = parse_frame(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [{"type": "numeric_value", "attribute": "cumulative_gpa", "value": 7.2}],
                "source_id": "premise_0002",
                "source_text": "Mai has a cumulative GPA of 7.2.",
                "premise_id": 2,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)

        self.assertIsInstance(ast, CompareNode)
        self.assertEqual(ast.op, "=")
        self.assertEqual(ast.source_id, "premise_0002")
        self.assertEqual(ast.premise_id, 2)

    def test_claim_with_negative_polarity_compiles_to_not_pred(self):
        frame = parse_frame(
            {
                "kind": "claim",
                "answer_type": "yes_no_unknown",
                "claim": {"type": "predicate", "entity": "Mai", "name": "eligible", "polarity": False},
                "source_id": "question",
                "source_text": "Is Mai not eligible?",
                "candidate_label": "claim",
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)

        self.assertIsInstance(ast, NotNode)
        self.assertIsInstance(ast.body, PredNode)
        self.assertEqual(ast.candidate_label, "claim")
        self.assertEqual(ast.source_id, "question")

    def test_ambiguous_frame_is_not_compilable(self):
        frame = parse_frame(
            {
                "kind": "ambiguous",
                "reason": "Insufficient context.",
                "source_id": "question",
                "source_text": "Could this be true?",
                "warnings": ["Unknown referent."],
                "options": ["entity_a", "entity_b"],
            }
        )
        validate_parse_frame(frame)

        with self.assertRaisesRegex(ValueError, "cannot be compiled"):
            compile_frame_to_ast(frame)


if __name__ == "__main__":
    unittest.main()
