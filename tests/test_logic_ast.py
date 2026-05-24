import unittest

from app.logic.ast import (
    AndNode,
    ArithNode,
    CompareNode,
    ConstTerm,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    NotNode,
    NumRefNode,
    NumberTerm,
    OrNode,
    PredNode,
    QuantifiedVariable,
    VarTerm,
)
from app.logic.normalization import normalize_logic_ast
from app.logic.validation import validate_logic_ast


class LogicAstValidationTests(unittest.TestCase):
    def test_validates_ast_covering_all_required_node_types(self):
        var_x = VarTerm(kind="var", name="x")
        var_y = VarTerm(kind="var", name="y")

        precondition = PredNode(type="pred", name="enrolled", args=[var_x])
        eligibility = PredNode(type="pred", name="eligible", args=[var_x])
        numeric_ref = NumRefNode(type="num_ref", name="gpa", args=[var_x], unit="gpa")
        numeric_calc = ArithNode(
            type="arith",
            op="average",
            operands=[numeric_ref, NumberTerm(kind="number", value=7.0, unit="gpa")],
        )
        threshold_check = CompareNode(
            type="compare",
            op=">=",
            left=numeric_calc,
            right=NumberTerm(kind="number", value=7.0, unit="gpa"),
        )
        disjunction = OrNode(
            type="or",
            operands=[
                eligibility,
                ExistsNode(
                    type="exists",
                    vars=[QuantifiedVariable(name="y", domain="course")],
                    body=PredNode(type="pred", name="takes_course", args=[var_x, var_y]),
                ),
            ],
        )
        implication = ImpliesNode(
            type="implies",
            if_node=AndNode(type="and", operands=[precondition, threshold_check]),
            then=NotNode(type="not", body=disjunction),
        )
        root = ForallNode(
            type="forall",
            vars=[QuantifiedVariable(name="x", domain="student")],
            body=implication,
            source_id="premise_0010",
            source_text="Students enrolled with enough GPA are eligible or taking a course.",
            premise_id=10,
        )

        validate_logic_ast(root, root_context="premise")

    def test_unbound_variable_fails_validation(self):
        root = PredNode(
            type="pred",
            name="eligible",
            args=[VarTerm(kind="var", name="x")],
            source_id="question",
            source_text="Is x eligible?",
            candidate_label="claim",
        )

        with self.assertRaisesRegex(ValueError, "Unbound variable"):
            validate_logic_ast(root, root_context="candidate")

    def test_predicate_arity_mismatch_fails_validation(self):
        root = ForallNode(
            type="forall",
            vars=[QuantifiedVariable(name="x"), QuantifiedVariable(name="y")],
            body=AndNode(
                type="and",
                operands=[
                    PredNode(type="pred", name="qualified", args=[VarTerm(kind="var", name="x")]),
                    PredNode(
                        type="pred",
                        name="qualified",
                        args=[VarTerm(kind="var", name="x"), VarTerm(kind="var", name="y")],
                    ),
                ],
            ),
            source_id="premise_0011",
            source_text="Qualified appears with mixed arity.",
            premise_id=11,
        )

        with self.assertRaisesRegex(ValueError, "Predicate arity mismatch"):
            validate_logic_ast(root, root_context="premise")

    def test_malformed_numeric_expression_fails_clearly(self):
        root = CompareNode(
            type="compare",
            op=">=",
            left=ArithNode(type="arith", op="add", operands=[]),
            right=NumberTerm(kind="number", value=1),
            source_id="question",
            source_text="What is the sum?",
            candidate_label="claim",
        )

        with self.assertRaisesRegex(ValueError, "at least one operand"):
            validate_logic_ast(root, root_context="candidate")

    def test_normalization_preserves_metadata_and_removes_double_negation(self):
        root = NotNode(
            type="not",
            body=NotNode(
                type="not",
                body=PredNode(
                    type="pred",
                    name="Can Graduate",
                    args=[ConstTerm(kind="const", name="Mai Student", surface="Mai Student")],
                ),
            ),
            source_id="question",
            source_text="Can Mai graduate?",
            candidate_label="claim",
        )

        normalized = normalize_logic_ast(root)

        self.assertIsInstance(normalized, PredNode)
        self.assertEqual(normalized.name, "can_graduate")
        self.assertEqual(normalized.args[0].name, "mai_student")
        self.assertEqual(normalized.source_id, "question")
        self.assertEqual(normalized.source_text, "Can Mai graduate?")
        self.assertEqual(normalized.candidate_label, "claim")

    def test_normalization_flattens_associative_nodes_and_keeps_nested_implications(self):
        nested_implication = ImpliesNode(
            type="implies",
            if_node=PredNode(type="pred", name="Condition A", args=[]),
            then=ImpliesNode(
                type="implies",
                if_node=PredNode(type="pred", name="Condition B", args=[]),
                then=PredNode(type="pred", name="Condition C", args=[]),
            ),
            source_id="premise_0012",
            source_text="If A then (if B then C).",
            premise_id=12,
        )
        and_root = AndNode(
            type="and",
            operands=[
                AndNode(
                    type="and",
                    operands=[
                        PredNode(type="pred", name="First Predicate", args=[]),
                        PredNode(type="pred", name="Second Predicate", args=[]),
                    ],
                ),
                nested_implication,
            ],
            source_id="premise_0013",
            source_text="Conjunction with nested implication.",
            premise_id=13,
        )

        normalized = normalize_logic_ast(and_root)

        self.assertIsInstance(normalized, AndNode)
        self.assertEqual(len(normalized.operands), 3)
        implication = normalized.operands[2]
        self.assertIsInstance(implication, ImpliesNode)
        self.assertIsInstance(implication.then, ImpliesNode)
        self.assertEqual(implication.if_node.name, "condition_a")
        self.assertEqual(implication.then.if_node.name, "condition_b")
        self.assertEqual(implication.then.then.name, "condition_c")


if __name__ == "__main__":
    unittest.main()
