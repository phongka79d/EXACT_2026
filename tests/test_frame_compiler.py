import unittest

from app.logic.ast import AndNode, CompareNode, ForallNode, ImpliesNode, NotNode, PredNode, VarTerm
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

    def test_rule_scope_alignment_treats_singular_plural_class_entities_as_variables(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "python projects",
                "if": [{"type": "predicate", "entity": "python project", "name": "well tested"}],
                "then": [{"type": "predicate", "entity": "python projects", "name": "optimized"}],
                "source_id": "premise_0100",
                "source_text": "If a Python project is well tested, then Python projects are optimized.",
                "premise_id": 100,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)

        self.assertIsInstance(ast, ForallNode)
        self.assertIsInstance(ast.body, ImpliesNode)
        antecedent = ast.body.if_node
        consequent = ast.body.then
        self.assertIsInstance(antecedent, PredNode)
        self.assertIsInstance(consequent, PredNode)
        self.assertIsInstance(antecedent.args[0], VarTerm)
        self.assertIsInstance(consequent.args[0], VarTerm)
        self.assertEqual(antecedent.args[0].name, "x")
        self.assertEqual(consequent.args[0].name, "x")

    def test_rule_compilation_propagates_source_metadata_to_nested_predicates(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "students",
                "if": [
                    {"type": "predicate", "entity": "students", "name": "eligible_for_international_program"},
                    {"type": "predicate", "entity": "students", "name": "completed_capstone_project"},
                ],
                "then": [
                    {"type": "predicate", "entity": "students", "name": "awarded_honors_diploma"},
                ],
                "source_id": "premise_0200",
                "source_text": "Students who are eligible for the international program and completed a capstone project are awarded an honors diploma.",
                "premise_id": 200,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)

        self.assertIsInstance(ast, ForallNode)
        self.assertIsInstance(ast.body, ImpliesNode)
        antecedent = ast.body.if_node
        consequent = ast.body.then
        self.assertIsInstance(antecedent, AndNode)
        for node in [*antecedent.operands, consequent]:
            self.assertIsInstance(node, PredNode)
            self.assertEqual(node.source_id, "premise_0200")
            self.assertEqual(node.source_text, frame.source_text)
            self.assertEqual(node.premise_id, 200)

    def test_entity_relation_complement_is_preserved_as_third_argument(self):
        frame = parse_frame(
            {
                "kind": "fact",
                "facts": [
                    {
                        "type": "entity_relation",
                        "subject": "Mai",
                        "relation": "qualified_for",
                        "object": "scholarship",
                        "complement": "merit",
                    }
                ],
                "source_id": "premise_0300",
                "source_text": "Mai is qualified for merit scholarship.",
                "premise_id": 300,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)

        ast = compile_frame_to_ast(frame)
        self.assertIsInstance(ast, PredNode)
        self.assertEqual(ast.name, "qualified_for")
        self.assertEqual(len(ast.args), 3)


if __name__ == "__main__":
    unittest.main()
