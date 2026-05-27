import asyncio
import json
import unittest
from pathlib import Path
from typing import Any

from app.llm import FrameExtractionInput, LLMFrameExtractor, MockFrameExtractor, build_frame_cache_key
from app.llm.errors import LLMTransientError
from app.llm.prompts import (
    EXTRACTOR_VERSION,
    PROMPT_VERSION,
    build_candidate_frame_messages,
    build_premise_frame_messages,
)


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


class PromptContractTests(unittest.TestCase):
    def test_premise_prompt_covers_schema_numeric_nested_and_safety_rules(self):
        messages = build_premise_frame_messages(
            source_text="Applications must be submitted at least 30 days before the review meeting.",
            source_id="premise_1001",
            premise_id=1001,
        )

        self.assertEqual(len(messages), 2)
        combined = "\n".join(message["content"] for message in messages).lower()

        for frame_kind in ("rule", "fact", "claim", "compound", "ambiguous"):
            self.assertIn(frame_kind, combined)
        for slot_type in ("predicate", "numeric_condition", "numeric_value", "arithmetic_expression", "entity_relation"):
            self.assertIn(slot_type, combined)
        for numeric_phrase in ("at least", "higher than", "lower than", "no more than", "within", "before", "after", "between"):
            self.assertIn(numeric_phrase, combined)
        for numeric_topic in ("gpa", "deadline", "duration", "fee", "threshold"):
            self.assertIn(numeric_topic, combined)

        self.assertIn("do not answer", combined)
        self.assertIn("premises-fol", combined)
        self.assertIn("explanation", combined)
        self.assertIn("idx", combined)

    def test_candidate_prompt_covers_claim_types_and_no_answering_rules(self):
        messages = build_candidate_frame_messages(
            source_text="Option A: The learner's GPA is at least 7.0.",
            source_id="question",
            candidate_label="A",
        )

        self.assertEqual(len(messages), 2)
        combined = "\n".join(message["content"] for message in messages).lower()

        self.assertIn("mcq", combined)
        self.assertIn("yes_no_unknown", combined)
        self.assertIn("numeric", combined)
        self.assertIn("open_ended", combined)
        self.assertIn("do not choose an option", combined)
        self.assertIn("do not return yes/no", combined)

    def test_repair_prompt_contains_rule_template_for_missing_if_then_errors(self):
        from app.llm.prompts import build_repair_frame_messages

        messages = build_repair_frame_messages(
            source_text="If a Python code is well-tested, then the project is optimized.",
            source_id="premise_0001",
            premise_id=1,
            candidate_label=None,
            frame_mode="premise",
            validation_error="Rule frame must contain at least one `if` slot",
        )

        combined = "\n".join(message["content"] for message in messages).lower()

        self.assertIn("if direct rule", combined)
        self.assertIn('"if":[', combined)
        self.assertIn('"then":[', combined)
        self.assertIn("every slot object must include", combined)

    def test_prompt_version_changes_cache_key(self):
        request = FrameExtractionInput(
            mode="premise",
            source_id="premise_1002",
            premise_id=1002,
            source_text="Learners must have at least 20 credits.",
        )
        current_key = build_frame_cache_key(
            request,
            model="qwen2.5-7b-instruct",
            prompt_version=PROMPT_VERSION,
            extractor_version=EXTRACTOR_VERSION,
        )
        previous_prompt_key = build_frame_cache_key(
            request,
            model="qwen2.5-7b-instruct",
            prompt_version="batch8_6_v1",
            extractor_version=EXTRACTOR_VERSION,
        )

        self.assertRegex(PROMPT_VERSION, r"batch8_7_v\d+")
        self.assertNotEqual(current_key, previous_prompt_key)


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

    async def test_mocked_nested_numeric_rule_frame_succeeds(self):
        mock_extractor = MockFrameExtractor(
            responses={
                "premise_2001": {
                    "kind": "rule",
                    "scope": "students",
                    "if": [
                        {
                            "type": "numeric_condition",
                            "entity": "student",
                            "attribute": "entrance_score",
                            "op": ">=",
                            "expression": {
                                "type": "arithmetic_expression",
                                "op": "percentage_of",
                                "operands": [{"value": 75, "unit": "percent"}, {"attribute": "standard_score"}],
                            },
                        }
                    ],
                    "then": [{"type": "predicate", "entity": "student", "name": "eligible_for_scholarship"}],
                    "source_id": "premise_2001",
                    "source_text": "If a student scores at least 75% of the standard score, then the student is eligible for the scholarship.",
                    "premise_id": 2001,
                    "warnings": [],
                }
            }
        )

        result = await mock_extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_2001",
                premise_id=2001,
                source_text="If a student scores at least 75% of the standard score, then the student is eligible for the scholarship.",
            )
        )

        self.assertEqual(result.frame.kind, "rule")
        self.assertEqual(result.frame.if_slots[0].type, "numeric_condition")
        self.assertEqual(result.frame.then_slots[0].type, "predicate")

    async def test_mocked_candidate_numeric_claim_succeeds(self):
        mock_extractor = MockFrameExtractor(
            responses={
                "candidate_A": {
                    "kind": "claim",
                    "answer_type": "numeric",
                    "claim": {
                        "type": "numeric_condition",
                        "entity": "student",
                        "attribute": "cumulative_gpa",
                        "op": ">=",
                        "value": 7.0,
                    },
                    "source_id": "candidate_A",
                    "source_text": "Option A: The student has a cumulative GPA of at least 7.0.",
                    "candidate_label": "A",
                    "warnings": [],
                }
            }
        )

        result = await mock_extractor.extract_frame(
            FrameExtractionInput(
                mode="candidate",
                source_id="candidate_A",
                candidate_label="A",
                source_text="Option A: The student has a cumulative GPA of at least 7.0.",
            )
        )

        self.assertEqual(result.frame.kind, "claim")
        self.assertEqual(result.frame.answer_type, "numeric")
        self.assertEqual(result.frame.claim.type, "numeric_condition")


class LLMFrameExtractorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.frame_events_path = Path("artifacts/frame_events.jsonl")
        if self.frame_events_path.exists():
            self.frame_events_path.unlink()
        for replay in Path("artifacts").glob("parser_replay_*.jsonl"):
            replay.unlink()

    def tearDown(self):
        if self.frame_events_path.exists():
            self.frame_events_path.unlink()
        for replay in Path("artifacts").glob("parser_replay_*.jsonl"):
            replay.unlink()

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
        events = [json.loads(line) for line in self.frame_events_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["event"] for event in events], ["raw_response", "raw_response"])

    async def test_malformed_payload_enters_repair_loop(self):
        malformed_first_pass = "{'kind':'fact','source_text':'unterminated}"
        valid_repair = json.dumps(_valid_fact_frame_payload())
        client = _ScriptedClient([malformed_first_pass, valid_repair])
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

    async def test_failed_extraction_writes_parser_replay_fixture(self):
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
        client = _ScriptedClient([invalid_first_pass])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)
        request = FrameExtractionInput(
            mode="premise",
            source_id="premise_0001",
            premise_id=1,
            source_text="Mai has GPA 7.2.",
        )

        with self.assertRaisesRegex(Exception, "Frame extraction failed after repair attempts"):
            await extractor.extract_frame(request)

        replay_files = list(Path("artifacts").glob("parser_replay_*.jsonl"))
        self.assertEqual(len(replay_files), 1)
        replay_lines = replay_files[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(replay_lines), 1)
        replay_payload = json.loads(replay_lines[0])
        self.assertEqual(replay_payload["source_id"], "premise_0001")
        self.assertEqual(replay_payload["failure_type"], "frame_validation_error")
        self.assertIn("errors", replay_payload)

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

    async def test_model_payload_normalization_is_reported_in_diagnostics(self):
        underspecified_payload = {
            "kind": "fact",
            "entity": "Alex",
            "facts": [{"attribute": "gpa", "value": 7.2}],
            "source_id": "premise_0001",
            "source_text": "Student Alex has a cumulative GPA of 7.2.",
            "premise_id": 1,
        }
        client = _ScriptedClient([json.dumps(underspecified_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Student Alex has a cumulative GPA of 7.2.",
            )
        )

        self.assertTrue(result.diagnostics["normalization_applied"])
        self.assertIn("normalization_warnings", result.diagnostics)
        self.assertIn("warnings_defaulted", result.diagnostics["normalization_warnings"])
        self.assertIn("slot_type_inferred:numeric_value", result.diagnostics["normalization_warnings"])

    async def test_rule_aliases_and_predicate_slots_are_normalized(self):
        aliased_rule_payload = {
            "kind": "rule",
            "scope": "Python code",
            "conditions": [{"entity": "Python code", "predicate": "well_tested"}],
            "consequences": [{"entity": "project", "predicate": "optimized"}],
            "source_id": "premise_0001",
            "source_text": "If a Python code is well-tested, then the project is optimized.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(aliased_rule_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="If a Python code is well-tested, then the project is optimized.",
            )
        )

        self.assertEqual(result.frame.kind, "rule")
        self.assertEqual(result.frame.if_slots[0].type, "predicate")
        self.assertEqual(result.frame.then_slots[0].type, "predicate")
        self.assertIn("rule_if_alias:conditions", result.diagnostics["normalization_warnings"])
        self.assertIn("rule_then_alias:consequences", result.diagnostics["normalization_warnings"])
        self.assertIn("slot_type_inferred:predicate", result.diagnostics["normalization_warnings"])

    async def test_numeric_attribute_aliases_are_normalized(self):
        numeric_payload = {
            "kind": "fact",
            "entity": "Alex",
            "facts": [{"type": "numeric_value", "entity": "Alex", "name": "cumulative_gpa", "value": 7.2}],
            "source_id": "premise_0001",
            "source_text": "Student Alex has a cumulative GPA of 7.2.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(numeric_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Student Alex has a cumulative GPA of 7.2.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.frame.facts[0].type, "numeric_value")
        self.assertEqual(result.frame.facts[0].attribute, "cumulative_gpa")
        self.assertIn("numeric_attribute_alias:name", result.diagnostics["normalization_warnings"])

    async def test_rule_slot_entities_default_from_scope(self):
        scoped_rule_payload = {
            "kind": "rule",
            "scope": "students",
            "if": [{"type": "predicate", "name": "completed_core_curriculum"}],
            "then": [{"type": "entity_relation", "relation": "qualified_for", "object": "advanced_courses"}],
            "source_id": "premise_0001",
            "source_text": "Students who have completed the core curriculum are qualified for advanced courses.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(scoped_rule_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Students who have completed the core curriculum are qualified for advanced courses.",
            )
        )

        self.assertEqual(result.frame.kind, "rule")
        self.assertEqual(result.frame.if_slots[0].entity, "students")
        self.assertEqual(result.frame.then_slots[0].subject, "students")
        self.assertIn("slot_entity_defaulted", result.diagnostics["normalization_warnings"])
        self.assertIn("relation_subject_defaulted", result.diagnostics["normalization_warnings"])

    async def test_nonnumeric_numeric_value_is_retyped_to_predicate(self):
        mislabeled_payload = {
            "kind": "fact",
            "entity": "students",
            "facts": [{"type": "numeric_value", "entity": "students", "attribute": "completed_core_curriculum", "value": "completed"}],
            "source_id": "premise_0001",
            "source_text": "Students have completed the core curriculum.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(mislabeled_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Students have completed the core curriculum.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.frame.facts[0].type, "predicate")
        self.assertEqual(result.frame.facts[0].name, "completed_core_curriculum")
        self.assertIn("numeric_value_retyped:predicate_non_numeric_value", result.diagnostics["normalization_warnings"])

    async def test_numeric_string_values_are_coerced_to_numbers(self):
        numeric_string_payload = {
            "kind": "fact",
            "entity": "Alex",
            "facts": [{"type": "numeric_value", "entity": "Alex", "attribute": "cumulative_gpa", "value": "7.2"}],
            "source_id": "premise_0001",
            "source_text": "Student Alex has a cumulative GPA of 7.2.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(numeric_string_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Student Alex has a cumulative GPA of 7.2.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.frame.facts[0].type, "numeric_value")
        self.assertEqual(result.frame.facts[0].value, 7.2)
        self.assertIn("numeric_string_value_coerced", result.diagnostics["normalization_warnings"])

    async def test_numeric_value_alias_string_is_coerced_to_number(self):
        numeric_alias_payload = {
            "kind": "fact",
            "entity": "Alex",
            "facts": [{"entity": "Alex", "attribute": "cumulative_gpa", "numeric_value": "7.2"}],
            "source_id": "premise_0001",
            "source_text": "Student Alex has a cumulative GPA of 7.2.",
            "premise_id": 1,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(numeric_alias_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Student Alex has a cumulative GPA of 7.2.",
            )
        )

        self.assertEqual(result.frame.facts[0].type, "numeric_value")
        self.assertEqual(result.frame.facts[0].value, 7.2)
        self.assertIn("numeric_value_alias:numeric_value", result.diagnostics["normalization_warnings"])
        self.assertIn("numeric_string_value_coerced", result.diagnostics["normalization_warnings"])

    async def test_python_literal_dict_payload_is_parsed(self):
        python_literal_payload = (
            "{'kind':'fact','entity':'Alex','facts':[{'type':'predicate','entity':'Alex','name':'eligible'}],"
            "'source_id':'premise_0001','source_text':'Alex is eligible.','premise_id':1,'warnings':[]}"
        )
        client = _ScriptedClient([python_literal_payload])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0001",
                premise_id=1,
                source_text="Alex is eligible.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.frame.facts[0].name, "eligible")

    async def test_empty_rule_scope_and_relation_aliases_are_normalized(self):
        rule_payload = {
            "kind": "rule",
            "scope": "",
            "if": [{"type": "predicate", "entity": "students", "attribute": "awarded_honors_diploma"}],
            "then": [{"type": "entity_relation", "subject": "students", "name": "qualifies_for", "object": "scholarship"}],
            "source_id": "premise_0005",
            "source_text": "Students who have been awarded an honors diploma qualify for the university scholarship.",
            "premise_id": 5,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(rule_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0005",
                premise_id=5,
                source_text="Students who have been awarded an honors diploma qualify for the university scholarship.",
            )
        )

        self.assertEqual(result.frame.kind, "rule")
        self.assertTrue(result.frame.scope)
        self.assertEqual(result.frame.if_slots[0].name, "awarded_honors_diploma")
        self.assertEqual(result.frame.then_slots[0].relation, "qualifies_for")
        self.assertIn("scope_defaulted", result.diagnostics["normalization_warnings"])
        self.assertIn("predicate_name_alias:attribute", result.diagnostics["normalization_warnings"])
        self.assertIn("relation_name_alias:name", result.diagnostics["normalization_warnings"])

    async def test_direct_rule_without_condition_is_retyped_to_fact(self):
        direct_payload = {
            "kind": "rule",
            "scope": "projects",
            "then": [{"type": "predicate", "entity": "projects", "name": "optimized"}],
            "source_id": "premise_0013",
            "source_text": "There exists at least one project that is optimized.",
            "premise_id": 13,
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(direct_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="premise",
                source_id="premise_0013",
                premise_id=13,
                source_text="There exists at least one project that is optimized.",
            )
        )

        self.assertEqual(result.frame.kind, "fact")
        self.assertEqual(result.frame.facts[0].name, "optimized")
        self.assertIn("rule_without_condition_retyped:fact", result.diagnostics["normalization_warnings"])

    async def test_string_claim_is_wrapped_as_predicate_slot(self):
        claim_payload = {
            "kind": "claim",
            "answer_type": "yes_no_unknown",
            "claim": "Sophia qualifies for the university scholarship",
            "source_id": "question",
            "source_text": "Does Sophia qualify for the university scholarship?",
            "candidate_label": "claim",
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(claim_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="candidate",
                source_id="question",
                candidate_label="claim",
                source_text="Does Sophia qualify for the university scholarship?",
            )
        )

        self.assertEqual(result.frame.kind, "claim")
        self.assertEqual(result.frame.claim.type, "predicate")
        self.assertEqual(result.frame.claim.entity, "Sophia")
        self.assertIn("claim_text_wrapped_as_predicate", result.diagnostics["normalization_warnings"])

    async def test_missing_candidate_claim_falls_back_to_source_text_predicate(self):
        claim_payload = {
            "kind": "claim",
            "answer_type": "yes_no_unknown",
            "claim": None,
            "source_id": "question",
            "source_text": "Does Sophia qualify for the university scholarship?",
            "candidate_label": "claim",
            "warnings": [],
        }
        client = _ScriptedClient([json.dumps(claim_payload)])
        extractor = LLMFrameExtractor(client=client, max_attempts=1, max_repairs=0, jitter_seconds=0.0)

        result = await extractor.extract_frame(
            FrameExtractionInput(
                mode="candidate",
                source_id="question",
                candidate_label="claim",
                source_text="Does Sophia qualify for the university scholarship?",
            )
        )

        self.assertEqual(result.frame.kind, "claim")
        self.assertEqual(result.frame.claim.type, "predicate")
        self.assertEqual(result.frame.claim.entity, "Sophia")
        self.assertIn("claim_text_wrapped_as_predicate", result.diagnostics["normalization_warnings"])

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
