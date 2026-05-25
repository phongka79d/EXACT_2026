import unittest

from app.logic.ast import ConstTerm, ImpliesNode, PredNode, VarTerm
from app.solver import SolverRequest, prove_entailment
from app.solver.semantic_fallback import FALLBACK_MAX_CONFIDENCE


def _pred(name: str, entity: str, premise_id: int | None = None) -> PredNode:
    return PredNode(
        type="pred",
        name=name,
        args=[ConstTerm(kind="const", name=entity, surface=entity.capitalize())],
        premise_id=premise_id,
        source_id=f"premise_{premise_id}" if premise_id is not None else None,
    )


class SolverRoutingTests(unittest.TestCase):
    def test_horn_route_is_used_for_horn_compatible_claims(self):
        premises = [_pred("eligible", "mai", premise_id=1)]
        claim = _pred("eligible", "mai")

        result = prove_entailment(
            SolverRequest(
                premise_asts=premises,
                claim_ast=claim,
                premises_nl=["Mai is eligible."],
                candidate_text="Mai is eligible.",
            )
        )

        self.assertEqual(result.route, "horn")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.entailed)
        self.assertEqual(result.solver_metadata.get("z3_status"), "not_run")
        self.assertFalse(result.solver_metadata.get("fallback_used"))

    def test_numeric_route_uses_z3_adapter(self):
        premise = _pred("eligible", "mai", premise_id=10)
        claim = _pred("eligible", "mai")

        result = prove_entailment(
            SolverRequest(
                premise_asts=[premise],
                claim_ast=claim,
                numeric_context={"z3_constraints": [{"expression": "exam_score>=75"}]},
                premises_nl=["Mai is eligible."],
                candidate_text="Mai is eligible.",
            )
        )

        self.assertEqual(result.route, "z3")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.entailed)

    def test_unsupported_nested_logic_uses_semantic_fallback(self):
        nested_with_variable = ImpliesNode(
            type="implies",
            if_node=_pred("eligible", "mai", premise_id=20),
            then=ImpliesNode(
                type="implies",
                if_node=PredNode(type="pred", name="passed", args=[VarTerm(kind="var", name="x")], premise_id=20),
                then=_pred("can_graduate", "mai", premise_id=20),
                premise_id=20,
                source_id="premise_20",
            ),
            premise_id=20,
            source_id="premise_20",
        )
        claim = _pred("can_graduate", "mai")

        result = prove_entailment(
            SolverRequest(
                premise_asts=[nested_with_variable],
                claim_ast=claim,
                premises_nl=["If Mai is eligible then if x passed then Mai can graduate."],
                candidate_text="Mai can graduate",
            )
        )

        self.assertEqual(result.route, "semantic_fallback")
        self.assertEqual(result.status, "solver_capability_gap")
        self.assertLessEqual(result.confidence, FALLBACK_MAX_CONFIDENCE)
        self.assertTrue(result.solver_metadata.get("fallback_used"))
        self.assertEqual(result.solver_metadata.get("original_route"), "z3")

    def test_fallback_does_not_override_successful_symbolic_proof(self):
        premises = [
            _pred("eligible", "mai", premise_id=30),
            ImpliesNode(
                type="implies",
                if_node=_pred("eligible", "mai", premise_id=31),
                then=_pred("approved", "mai", premise_id=31),
                premise_id=31,
                source_id="premise_31",
            ),
        ]
        claim = _pred("approved", "mai")

        result = prove_entailment(
            SolverRequest(
                premise_asts=premises,
                claim_ast=claim,
                premises_nl=["Mai is eligible.", "If Mai is eligible then Mai is approved."],
                candidate_text="Mai is approved.",
            )
        )

        self.assertEqual(result.route, "horn")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.entailed)
        self.assertFalse(result.solver_metadata.get("fallback_used"))


if __name__ == "__main__":
    unittest.main()
