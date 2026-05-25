import unittest

from app.logic.ast import AndNode, CompareNode, ConstTerm, ImpliesNode, NumRefNode, PredNode, VarTerm
from app.logic.ast.terms import NumberTerm
from app.solver.z3_adapter import Z3AdapterInput, prove_with_z3_compatible_adapter


def _pred(name: str, *args: str, premise_id: int | None = None):
    return PredNode(
        type="pred",
        name=name,
        args=[ConstTerm(kind="const", name=item, surface=item.capitalize()) for item in args],
        premise_id=premise_id,
        source_id=f"premise_{premise_id}" if premise_id is not None else None,
    )


class Z3AdapterTests(unittest.TestCase):
    def test_grounded_nested_implication_is_supported(self):
        premises = [
            ImpliesNode(
                type="implies",
                if_node=_pred("eligible", "mai", premise_id=1),
                then=ImpliesNode(
                    type="implies",
                    if_node=_pred("passed_exam", "mai", premise_id=1),
                    then=_pred("can_graduate", "mai", premise_id=1),
                    premise_id=1,
                    source_id="premise_1",
                ),
                premise_id=1,
                source_id="premise_1",
            ),
            _pred("eligible", "mai", premise_id=2),
            _pred("passed_exam", "mai", premise_id=3),
        ]
        claim = _pred("can_graduate", "mai")

        result = prove_with_z3_compatible_adapter(Z3AdapterInput(premise_asts=premises, claim_ast=claim))

        self.assertEqual(result.route, "z3")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.entailed)
        self.assertEqual(result.solver_metadata.get("z3_status"), "unsat_negated_claim")

    def test_numeric_comparison_uses_numeric_context(self):
        premise = CompareNode(
            type="compare",
            op=">=",
            left=NumRefNode(type="num_ref", name="exam_score", args=[ConstTerm(kind="const", name="mai")]),
            right=NumberTerm(kind="number", value=70),
            premise_id=11,
            source_id="premise_11",
        )
        claim = CompareNode(
            type="compare",
            op=">=",
            left=NumRefNode(type="num_ref", name="exam_score", args=[ConstTerm(kind="const", name="mai")]),
            right=NumberTerm(kind="number", value=75),
        )

        result = prove_with_z3_compatible_adapter(
            Z3AdapterInput(
                premise_asts=[premise],
                claim_ast=claim,
                numeric_context={"numeric_facts": [{"attribute": "exam_score", "entity": "mai", "value": 80}]},
            )
        )

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.entailed)
        self.assertEqual(result.route, "z3")

    def test_ungrounded_formula_returns_capability_gap(self):
        premise = ImpliesNode(
            type="implies",
            if_node=_pred("eligible", "mai", premise_id=20),
            then=AndNode(
                type="and",
                operands=[
                    PredNode(type="pred", name="can_graduate", args=[VarTerm(kind="var", name="x")], premise_id=20),
                ],
            ),
            premise_id=20,
            source_id="premise_20",
        )
        claim = PredNode(type="pred", name="can_graduate", args=[VarTerm(kind="var", name="x")])

        result = prove_with_z3_compatible_adapter(Z3AdapterInput(premise_asts=[premise], claim_ast=claim))

        self.assertEqual(result.status, "solver_capability_gap")
        self.assertFalse(result.entailed)
        self.assertEqual(result.solver_metadata.get("z3_status"), "unsupported")


if __name__ == "__main__":
    unittest.main()
