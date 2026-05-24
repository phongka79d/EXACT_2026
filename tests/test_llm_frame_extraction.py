import asyncio
import json
import unittest
from typing import Any

from app.llm import FrameExtractionInput, LLMFrameExtractor, MockFrameExtractor
from app.llm.errors import LLMTransientError


class _ScriptedClient:
    def __init__(self, outcomes: list[Any]):
        self._outcomes = list(outcomes)
        self.calls: list[list[dict[str, str]]] = []
        self.model = "qwen2.5-7b-instruct"
        self.sanitized_endpoint = "https://example.invalid/v1/chat/completions"
        self.api_key_for_redaction = "sk-test"

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        _ = temperature, max_tokens
        self.calls.append(messages)
        if not self._outcomes:
            raise AssertionError("No scripted client outcomes left")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if not isinstance(outcome, str):
            raise AssertionError("Scripted outcome must be str or Exception")
        return outcome


def _valid_fact_frame_payload(source_id: str = "premise_0001", premise_id: int = 1) -> dict[str, Any]:
    return {
        "kind": "fact",
        "entity": "Mai",
        "facts": [{"type": "numeric_value", "entity": "Mai", "attribute": "gpa", "value": 7.2}],
        "source_id": source_id,
        "source_text": "Mai has GPA 7.2.",
        "premise_id": premise_id,
        "warnings": [],
    }


class MockFrameExtractorTests(unittest.IsolatedAsyncioTestCase):
    async def test_mocked_valid_frame_succeeds(self):
        mock_extractor = MockFrameExtractor(default_response=_valid_fact_frame_payload())

        result = await mock_extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Mai has GPA 7.2.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.diagnostics["model"], "mock")
        self.assertFalse(result.diagnostics["cache_hit"])


class LLMFrameExtractorTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_first_pass_triggers_repair(self):
        invalid_first_pass = json.dumps(
            {
                "kind": "fact",
                "entity": "Mai",
                "facts": [],
                "source_id": "premise_0001",
                "source_text": "Mai has GPA 7.2.",
                "premise_id": 1,
                "warnings": [],
            }
        )
        valid_repair = json.dumps(_valid_fact_frame_payload())
        client = _ScriptedClient([invalid_first_pass, valid_repair])
        extractor = LLMFrameExtractor(client=client, max_attempts=2, max_repairs=1, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Mai has GPA 7.2.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.diagnostics["repair_count"], 1)
        self.assertEqual(result.diagnostics["attempts"], 2)
        self.assertEqual(len(client.calls), 2)
        repair_prompt = client.calls[1][1]["content"]
        self.assertIn("validation_error", repair_prompt)
        self.assertIn("source_text", repair_prompt)

    async def test_transient_failure_retries_with_backoff(self):
        client = _ScriptedClient([LLMTransientError("temporary outage"), json.dumps(_valid_fact_frame_payload())])
        sleep_calls: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            await asyncio.sleep(0)

        extractor = LLMFrameExtractor(
            client=client,
            max_attempts=3,
            max_repairs=0,
            base_backoff_seconds=0.01,
            jitter_seconds=0.0,
            sleep_func=fake_sleep,
        )

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Mai has GPA 7.2.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.diagnostics["retry_count"], 1)
        self.assertEqual(result.diagnostics["attempts"], 2)
        self.assertEqual(sleep_calls, [0.01])
        self.assertEqual(len(client.calls), 2)

    async def test_cache_hit_reuses_prior_parse_result(self):
        client = _ScriptedClient([json.dumps(_valid_fact_frame_payload())])
        extractor = LLMFrameExtractor(client=client, max_attempts=2, max_repairs=0, jitter_seconds=0.0)

        request = FrameExtractionInput(
            mode="premise",
            source_id="premise_0001",
            premise_id=1,
            source_text="Mai has GPA 7.2.",
        )
        first = await extractor.extract_frame(request)
        second = await extractor.extract_frame(request)

        self.assertFalse(first.diagnostics["cache_hit"])
        self.assertTrue(second.diagnostics["cache_hit"])
        self.assertEqual(len(client.calls), 1)

    def test_reference_only_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "reference-only"):
            FrameExtractionInput(
                mode="candidate",
                source_id="question",
                candidate_label="claim",
                source_text="Can Mai change majors?",
                metadata={"answer": "Yes"},
            )

        with self.assertRaisesRegex(ValueError, "reference-only"):
            FrameExtractionInput(
                mode="candidate",
                source_id="question",
                candidate_label="claim",
                source_text="Can Mai change majors?",
                metadata={"nested": {"premises-FOL": ["ForAll(x, p(x))"]}},
            )


if __name__ == "__main__":
    unittest.main()

