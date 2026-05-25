import unittest

from app.logic.ast import ConstTerm, PredNode
from app.tracing import build_source_registry


def _pred(
    *,
    name: str,
    entity: str,
    source_id: str | None,
    source_text: str | None,
    premise_id: int | None = None,
    candidate_label: str | None = None,
) -> PredNode:
    return PredNode(
        type="pred",
        name=name,
        args=[ConstTerm(kind="const", name=entity, surface=entity.capitalize())],
        source_id=source_id,
        source_text=source_text,
        premise_id=premise_id,
        candidate_label=candidate_label,
    )


class SolverCitationRegistryTests(unittest.TestCase):
    def test_registry_resolves_premise_and_candidate_source_text(self):
        premise = _pred(
            name="eligible",
            entity="mai",
            source_id="premise_0001",
            source_text="Mai is eligible.",
            premise_id=1,
        )
        candidate = _pred(
            name="eligible",
            entity="mai",
            source_id="question",
            source_text="Is Mai eligible?",
            candidate_label="claim",
        )
        registry = build_source_registry([premise], [candidate])

        premise_resolution = registry.resolve(premise_id=1)
        self.assertIsNotNone(premise_resolution.citation)
        self.assertEqual(premise_resolution.citation.source_text, "Mai is eligible.")
        self.assertEqual(premise_resolution.citation.premise_id, 1)
        self.assertEqual([], premise_resolution.warnings)

        candidate_resolution = registry.resolve(candidate_label="claim")
        self.assertIsNotNone(candidate_resolution.citation)
        self.assertEqual(candidate_resolution.citation.source_text, "Is Mai eligible?")
        self.assertEqual(candidate_resolution.citation.candidate_label, "claim")
        self.assertEqual([], candidate_resolution.warnings)

    def test_missing_source_metadata_emits_traceable_warnings(self):
        premise_missing_text = _pred(
            name="eligible",
            entity="mai",
            source_id="premise_0002",
            source_text=None,
            premise_id=2,
        )
        registry = build_source_registry([premise_missing_text], [])

        missing_text_resolution = registry.resolve(premise_id=2)
        self.assertIsNotNone(missing_text_resolution.citation)
        self.assertIn("citation_missing_source_text:premise_0002", missing_text_resolution.warnings)

        unresolved_resolution = registry.resolve(source_id="unknown_source")
        self.assertIsNotNone(unresolved_resolution.citation)
        self.assertEqual("unknown_source", unresolved_resolution.citation.source_id)
        self.assertIn("citation_unresolved_source:unknown_source", unresolved_resolution.warnings)
        self.assertIn("citation_missing_source_text:unknown_source", unresolved_resolution.warnings)


if __name__ == "__main__":
    unittest.main()
