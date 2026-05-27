import json
import shutil
import unittest
from pathlib import Path

from app.tracing import (
    NUMERIC_VALIDATION_FAILURES_PATH,
    ROOT_CAUSE_CATEGORIES,
    CacheMetadata,
    DebugTrace,
    PARSER_REPLAY_PREFIX,
    NumericDerivation,
    ProofTraceStep,
    SourceCitation,
    TraceStage,
    serialize_debug_trace,
    serialize_proof_trace_step,
    write_debug_trace_json,
    write_debug_trace_jsonl,
    write_numeric_validation_failures_jsonl,
    write_parser_replay_jsonl,
)


class DebugTraceTests(unittest.TestCase):
    def test_root_cause_categories_cover_batch4_requirements(self):
        required = {
            "data_validation_error",
            "question_parsing_error",
            "llm_frame_error",
            "frame_validation_error",
            "frame_compile_error",
            "ast_validation_error",
            "numeric_extraction_error",
            "solver_capability_gap",
            "z3_encoding_error",
            "semantic_fallback_used",
            "timeout_error",
            "output_formatting_error",
        }
        self.assertTrue(required.issubset(ROOT_CAUSE_CATEGORIES))

    def test_trace_serialization_redacts_sensitive_values(self):
        trace = self._build_trace()

        serialized = serialize_debug_trace(trace)

        stage_metadata = serialized["stages"][0]["metadata"]
        self.assertNotEqual(stage_metadata["Authorization"], "Bearer super-secret-token")
        self.assertNotEqual(stage_metadata["SHOPAIKEY_API_KEY"], "sk-test-12345")
        self.assertEqual(serialized["metadata"]["question_type"], "yes_no")
        self.assertEqual(serialized["root_cause_category"], "llm_frame_error")
        self.assertIn("proof_trace", serialized)

    def test_reference_only_fields_are_rejected_from_trace_payloads(self):
        trace_with_answer = DebugTrace(
            sample_id="sample-1",
            record_id=1,
            question_id=1,
            status="failed",
            root_cause_category="data_validation_error",
            metadata={"answer": "Yes"},
        )
        with self.assertRaisesRegex(ValueError, "reference-only"):
            serialize_debug_trace(trace_with_answer)

        step_with_fol = ProofTraceStep(
            step_id="step-1",
            action="validate",
            solver_route="none",
            metadata={"premises-FOL": ["ForAll(x, p(x))"]},
        )
        with self.assertRaisesRegex(ValueError, "reference-only"):
            serialize_proof_trace_step(step_with_fol)

    def test_json_and_jsonl_writers_produce_sanitized_artifacts(self):
        trace = self._build_trace()
        second_trace = DebugTrace(
            sample_id="sample-2",
            record_id=1,
            question_id=2,
            status="ok",
            root_cause_category=None,
            stages=[TraceStage(name="candidate_extraction", status="ok", duration_ms=1.5)],
        )

        tmp_path = Path(".pytest_tmp_debug_trace_artifacts")
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            json_path = tmp_path / "debug_trace.json"
            jsonl_path = tmp_path / "debug_traces.jsonl"

            write_debug_trace_json(json_path, trace)
            write_debug_trace_jsonl(jsonl_path, [trace, second_trace])

            json_text = json_path.read_text(encoding="utf-8")
            self.assertIn('"root_cause_category": "llm_frame_error"', json_text)
            self.assertNotIn("super-secret-token", json_text)
            self.assertNotIn("sk-test-12345", json_text)

            lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            records = [json.loads(line) for line in lines]
            self.assertEqual(records[0]["status"], "failed")
            self.assertEqual(records[1]["status"], "ok")
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_parser_replay_and_numeric_failure_artifact_contracts(self):
        tmp_path = Path(".pytest_tmp_trace_contract_artifacts")
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            parser_replay_path = tmp_path / f"{PARSER_REPLAY_PREFIX}batch4.jsonl"
            parser_payloads = [
                {
                    "source_id": "premise_0001",
                    "failure_type": "frame_validation_error",
                    "headers": {"Authorization": "Bearer must-redact"},
                }
            ]
            write_parser_replay_jsonl(parser_replay_path, parser_payloads)
            parser_text = parser_replay_path.read_text(encoding="utf-8")
            self.assertNotIn("must-redact", parser_text)

            numeric_path = tmp_path / NUMERIC_VALIDATION_FAILURES_PATH.name
            numeric_payloads = [
                {
                    "error_type": "unit_mismatch",
                    "details": "Expected credits but got percent",
                    "api_key": "sk-test-should-be-redacted",
                }
            ]
            write_numeric_validation_failures_jsonl(numeric_path, numeric_payloads)
            numeric_text = numeric_path.read_text(encoding="utf-8")
            self.assertNotIn("sk-test-should-be-redacted", numeric_text)

            with self.assertRaisesRegex(ValueError, "parser_replay_\\*\\.jsonl"):
                write_parser_replay_jsonl(tmp_path / "replay.jsonl", parser_payloads)
            with self.assertRaisesRegex(ValueError, "numeric_validation_failures.jsonl"):
                write_numeric_validation_failures_jsonl(tmp_path / "numeric_failures.jsonl", numeric_payloads)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def _build_trace(self) -> DebugTrace:
        return DebugTrace(
            sample_id="sample-1",
            record_id=17,
            question_id=3,
            status="failed",
            root_cause_category="llm_frame_error",
            root_cause_message="Upstream model timeout",
            created_at="2026-05-24T09:15:00Z",
            total_duration_ms=1234.5,
            premises_hash="premises_hash:abc123",
            warnings=["retry_applied"],
            stages=[
                TraceStage(
                    name="llm_frame_extraction",
                    status="failed",
                    started_at="2026-05-24T09:15:00Z",
                    ended_at="2026-05-24T09:15:01Z",
                    duration_ms=1000.0,
                    metadata={
                        "Authorization": "Bearer super-secret-token",
                        "SHOPAIKEY_API_KEY": "sk-test-12345",
                        "attempt": 2,
                    },
                )
            ],
            cache=CacheMetadata(
                mode="local",
                cache_key="record:17",
                cache_key_hash="f9ad0c",
                cache_hit=False,
                single_flight_waited=True,
            ),
            proof_trace=[
                ProofTraceStep(
                    step_id="step-1",
                    action="derive_numeric_fact",
                    solver_route="numeric",
                    status="partial",
                    used_premise_ids=[1],
                    derived_facts=["gpa(mai) >= 7.0"],
                    numeric_derivations=[
                        NumericDerivation(
                            name="gpa_threshold",
                            value=7.0,
                            unit="gpa",
                            expression="gpa(mai) >= 7.0",
                            sources=[
                                SourceCitation(
                                    source_id="premise_0001",
                                    source_text="Mai has GPA 7.0.",
                                    premise_id=1,
                                )
                            ],
                        )
                    ],
                    citations=[SourceCitation(source_id="premise_0001", premise_id=1)],
                )
            ],
            metadata={
                "question_type": "yes_no",
                "headers": {"Authorization": "Bearer still-secret"},
            },
        )


if __name__ == "__main__":
    unittest.main()
