import unittest

from app.solver.contraposition import derive_contrapositive
from app.solver.horn import HornLiteral, HornRule, HornTerm


def _literal(name: str, arg: str, *, negated: bool = False) -> HornLiteral:
    return HornLiteral(predicate=name, arguments=(HornTerm(name=arg, is_variable=False),), negated=negated)


class ContrapositionTests(unittest.TestCase):
    def test_derives_contrapositive_for_positive_literals(self):
        rule = HornRule(
            antecedents=(_literal("eligible", "mai"),),
            consequent=_literal("approved", "mai"),
            source_id="premise_1",
            premise_id=1,
        )

        derived, reason = derive_contrapositive(rule)

        self.assertIsNone(reason)
        self.assertIsNotNone(derived)
        assert derived is not None
        self.assertTrue(derived.derived_from_contraposition)
        self.assertTrue(derived.antecedents[0].negated)
        self.assertEqual(derived.antecedents[0].predicate, "approved")
        self.assertTrue(derived.consequent.negated)
        self.assertEqual(derived.consequent.predicate, "eligible")

    def test_derives_contrapositive_for_negative_literals(self):
        rule = HornRule(
            antecedents=(_literal("eligible", "mai", negated=True),),
            consequent=_literal("approved", "mai", negated=True),
            source_id="premise_2",
            premise_id=2,
        )

        derived, reason = derive_contrapositive(rule)

        self.assertIsNone(reason)
        self.assertIsNotNone(derived)
        assert derived is not None
        self.assertFalse(derived.antecedents[0].negated)
        self.assertEqual(derived.antecedents[0].predicate, "approved")
        self.assertFalse(derived.consequent.negated)
        self.assertEqual(derived.consequent.predicate, "eligible")

    def test_rejects_unsafe_non_literal_antecedent(self):
        rule = HornRule(
            antecedents=(_literal("eligible", "mai"), _literal("passing", "mai")),
            consequent=_literal("approved", "mai"),
            source_id="premise_3",
            premise_id=3,
        )

        derived, reason = derive_contrapositive(rule)

        self.assertIsNone(derived)
        self.assertEqual(reason, "unsafe_contraposition_non_literal_antecedent")


if __name__ == "__main__":
    unittest.main()

