import unittest

from app.logic.ast import AndNode, ConstTerm, ImpliesNode, NotNode, PredNode
from app.solver.horn import prove_entailment


def _fact(name: str, entity: str, *, negated: bool = False, premise_id: int = 1) -> PredNode | NotNode:
    node = PredNode(
        type="pred",
        name=name,
        args=[ConstTerm(kind="const", name=entity, surface=entity.capitalize())],
        source_id=f"premise_{premise_id}",
        source_text=f"{entity} {name}",
        premise_id=premise_id,
    )
    if negated:
        return NotNode(type="not", body=node, source_id=node.source_id, source_text=node.source_text, premise_id=node.premise_id)
    return node


def _rule(antecedent, consequent, premise_id: int) -> ImpliesNode:
    return ImpliesNode(
        type="implies",
        if_node=antecedent,
        then=consequent,
        source_id=f"premise_{premise_id}",
        source_text=f"rule_{premise_id}",
        premise_id=premise_id,
    )


class HornSolverTests(unittest.TestCase):
    def test_forward_chaining_proves_supported_horn_case(self):
        premises = [
            _fact("eligible", "mai", premise_id=1),
            _rule(_fact("eligible", "mai", premise_id=2), _fact("approved", "mai", premise_id=2), premise_id=2),
            _rule(_fact("approved", "mai", premise_id=3), _fact("can_change_major", "mai", premise_id=3), premise_id=3),
        ]
        claim = PredNode(
            type="pred",
            name="can_change_major",
            args=[ConstTerm(kind="const", name="mai", surface="Mai")],
            source_id="question",
            source_text="Can Mai change majors?",
            candidate_label="claim",
        )

        result = prove_entailment(premises, claim)

        self.assertTrue(result.entailed)
        self.assertEqual(result.status, "ok")
        self.assertTrue(any(item.method == "forward_chaining" for item in result.derived_facts))

    def test_safe_contraposition_supports_negated_entailment(self):
        premises = [
            _rule(_fact("eligible", "mai", premise_id=10), _fact("approved", "mai", premise_id=10), premise_id=10),
            _fact("approved", "mai", negated=True, premise_id=11),
        ]
        claim = NotNode(
            type="not",
            body=PredNode(
                type="pred",
                name="eligible",
                args=[ConstTerm(kind="const", name="mai", surface="Mai")],
                source_id="question",
                source_text="Is Mai ineligible?",
                candidate_label="claim",
            ),
            source_id="question",
            source_text="Is Mai ineligible?",
            candidate_label="claim",
        )

        result = prove_entailment(premises, claim)

        self.assertTrue(result.entailed)
        self.assertTrue(any(item.method == "contraposition" for item in result.derived_facts))

    def test_unsafe_contraposition_is_rejected(self):
        premise_rule = _rule(
            AndNode(
                type="and",
                operands=[_fact("eligible", "mai", premise_id=20), _fact("passing", "mai", premise_id=20)],
            ),
            _fact("approved", "mai", premise_id=20),
            premise_id=20,
        )
        premises = [premise_rule, _fact("approved", "mai", negated=True, premise_id=21)]
        claim = NotNode(
            type="not",
            body=PredNode(
                type="pred",
                name="eligible",
                args=[ConstTerm(kind="const", name="mai", surface="Mai")],
                source_id="question",
                source_text="Is Mai not eligible?",
                candidate_label="claim",
            ),
            source_id="question",
            source_text="Is Mai not eligible?",
            candidate_label="claim",
        )

        result = prove_entailment(premises, claim)

        self.assertFalse(result.entailed)
        self.assertEqual(result.status, "solver_capability_gap")
        self.assertIn("unsafe_contraposition_non_literal_antecedent", result.unsupported_features)


if __name__ == "__main__":
    unittest.main()

