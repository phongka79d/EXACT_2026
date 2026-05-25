import unittest

from app.logic.ast import ConstTerm, PredNode
from app.solver.semantic_fallback import FALLBACK_MAX_CONFIDENCE, SemanticFallbackInput, run_semantic_fallback


def _claim(text: str) -> PredNode:
    return PredNode(
        type="pred",
        name="eligible",
        args=[ConstTerm(kind="const", name="mai", surface="Mai")],
        source_id="question",
        source_text=text,
        candidate_label="claim",
    )


class SemanticFallbackTests(unittest.TestCase):
    def test_confidence_is_capped_and_route_is_explicit(self):
        result = run_semantic_fallback(
            SemanticFallbackInput(
                premises_nl=["Mai is eligible for scholarship."],
                candidate_text="Mai eligible scholarship",
                symbolic_reason="solver_capability_gap",
                claim_ast=_claim("Is Mai eligible?"),
            )
        )

        self.assertEqual(result.route, "semantic_fallback")
        self.assertEqual(result.status, "solver_capability_gap")
        self.assertLessEqual(result.confidence, FALLBACK_MAX_CONFIDENCE)
        self.assertGreater(result.confidence_penalty, 0.0)
        self.assertTrue(result.solver_metadata.get("fallback_used"))

    def test_overlap_drives_low_confidence_guess(self):
        high_overlap = run_semantic_fallback(
            SemanticFallbackInput(
                premises_nl=["Mai is eligible and has completed required credits."],
                candidate_text="eligible required credits",
                symbolic_reason="unsupported_nested_or_meta_logic",
                claim_ast=_claim("Is Mai eligible?"),
            )
        )
        low_overlap = run_semantic_fallback(
            SemanticFallbackInput(
                premises_nl=["Campus library closes at 5 PM."],
                candidate_text="eligible required credits",
                symbolic_reason="unsupported_nested_or_meta_logic",
                claim_ast=_claim("Is Mai eligible?"),
            )
        )

        self.assertTrue(high_overlap.entailed)
        self.assertFalse(low_overlap.entailed)
        self.assertGreaterEqual(high_overlap.confidence, low_overlap.confidence)


if __name__ == "__main__":
    unittest.main()
