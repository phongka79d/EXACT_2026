import unittest

from app.logic.ast import (
    ConstTerm,
    ExistsNode,
    ForallNode,
    ImpliesNode,
    PredNode,
    QuantifiedVariable,
    VarTerm,
)
from app.solver.horn import prove_entailment
from app.solver.quantifiers import instantiate_forall, schema_matches_universal


def _generic_rule(*, source_id: str, premise_id: int, var_name: str = "x", domain: str = "student") -> ForallNode:
    return ForallNode(
        type="forall",
        vars=[QuantifiedVariable(name=var_name, domain=domain)],
        body=ImpliesNode(
            type="implies",
            if_node=PredNode(type="pred", name="eligible", args=[VarTerm(kind="var", name=var_name)]),
            then=PredNode(type="pred", name="can_change_major", args=[VarTerm(kind="var", name=var_name)]),
        ),
        source_id=source_id,
        source_text="If a student is eligible, they can change majors.",
        premise_id=premise_id,
    )


class QuantifierTests(unittest.TestCase):
    def test_universal_instantiation_uses_discovered_constants(self):
        rule = _generic_rule(source_id="premise_1", premise_id=1)
        constants = [
            ConstTerm(kind="const", name="mai", surface="Mai", domain="student"),
            ConstTerm(kind="const", name="chem101", surface="Chem101", domain="course"),
        ]

        result = instantiate_forall(rule, constants)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.instances), 1)
        instance = result.instances[0]
        assert isinstance(instance, ImpliesNode)
        premise_pred = instance.if_node
        assert isinstance(premise_pred, PredNode)
        self.assertEqual(premise_pred.args[0].name, "mai")

    def test_schema_level_universal_matching(self):
        premise_rule = _generic_rule(source_id="premise_2", premise_id=2, var_name="x")
        candidate_rule = _generic_rule(source_id="candidate", premise_id=0, var_name="learner")

        self.assertTrue(schema_matches_universal(candidate_rule, [premise_rule]))

    def test_domain_mismatch_blocks_instantiation(self):
        rule = _generic_rule(source_id="premise_3", premise_id=3, domain="student")
        constants = [ConstTerm(kind="const", name="chem101", surface="Chem101", domain="course")]

        result = instantiate_forall(rule, constants)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.instances, [])
        self.assertIn("no_matching_constants_for_domain", result.warnings or [])

    def test_existing_fact_satisfies_bounded_existential_candidate(self):
        premise_fact = PredNode(
            type="pred",
            name="eligible",
            args=[ConstTerm(kind="const", name="mai", surface="Mai", domain="student")],
            source_id="premise_4",
            source_text="Mai is eligible.",
            premise_id=4,
        )
        candidate = ExistsNode(
            type="exists",
            vars=[QuantifiedVariable(name="x", domain="student")],
            body=PredNode(
                type="pred",
                name="eligible",
                args=[VarTerm(kind="var", name="x")],
                source_id="question",
                source_text="Is there a student who is eligible?",
                candidate_label="claim",
            ),
            source_id="question",
            source_text="Is there a student who is eligible?",
            candidate_label="claim",
        )

        result = prove_entailment([premise_fact], candidate)

        self.assertTrue(result.entailed)
        self.assertEqual(result.status, "ok")

    def test_unsupported_alternating_quantifier_returns_gap(self):
        premise = ForallNode(
            type="forall",
            vars=[QuantifiedVariable(name="x", domain="student")],
            body=ExistsNode(
                type="exists",
                vars=[QuantifiedVariable(name="y", domain="course")],
                body=PredNode(
                    type="pred",
                    name="takes",
                    args=[VarTerm(kind="var", name="x"), VarTerm(kind="var", name="y")],
                ),
            ),
            source_id="premise_5",
            source_text="Every student takes some course.",
            premise_id=5,
        )
        claim = PredNode(
            type="pred",
            name="takes",
            args=[
                ConstTerm(kind="const", name="mai", surface="Mai", domain="student"),
                ConstTerm(kind="const", name="chem101", surface="Chem101", domain="course"),
            ],
            source_id="question",
            source_text="Does Mai take Chem101?",
            candidate_label="claim",
        )

        result = prove_entailment([premise], claim)

        self.assertFalse(result.entailed)
        self.assertEqual(result.status, "solver_capability_gap")
        self.assertIn("unsupported_alternating_quantifier_pattern", result.unsupported_features)


if __name__ == "__main__":
    unittest.main()

