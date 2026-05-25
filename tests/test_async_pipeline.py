import asyncio
import json
import shutil
import unittest
from pathlib import Path
from typing import Any

from app.cache import build_api_premise_cache_key, build_local_premise_cache_key
from app.data import LocalRuntimeSample, RuntimeQuery
from app.llm import FrameExtractionInput, FrameExtractionResult
from app.logic.frames import parse_frame
from app.pipeline import AsyncRuntimePipeline, write_pipeline_artifacts


def _premise_frame_payload(source_id: str, source_text: str, premise_id: int) -> dict[str, Any]:
    return {
        "kind": "fact",
        "entity": "Mai",
        "facts": [{"type": "predicate", "entity": "Mai", "name": "eligible", "polarity": True}],
        "source_id": source_id,
        "source_text": source_text,
        "premise_id": premise_id,
        "warnings": [],
    }


def _candidate_frame_payload(source_id: str, source_text: str, candidate_label: str) -> dict[str, Any]:
    return {
        "kind": "claim",
        "answer_type": "claim",
        "claim": {"type": "predicate", "entity": "Mai", "name": "eligible", "polarity": True},
        "source_id": source_id,
        "source_text": source_text,
        "candidate_label": candidate_label,
        "warnings": [],
    }


class _ScriptedFrameExtractor:
    def __init__(
        self,
        *,
        delay_by_mode: dict[str, float] | None = None,
        fail_source_ids: set[str] | None = None,
    ):
        self._delay_by_mode = dict(delay_by_mode or {})
        self._fail_source_ids = set(fail_source_ids or set())
        self.calls: list[FrameExtractionInput] = []

    async def extract_frame(self, request: FrameExtractionInput) -> FrameExtractionResult:
        self.calls.append(request)
        delay_seconds = self._delay_by_mode.get(request.mode, 0.0)
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        if request.source_id in self._fail_source_ids:
            raise ValueError(f"scripted extractor failure for {request.source_id}")

        if request.mode == "premise":
            payload = _premise_frame_payload(
                source_id=request.source_id,
                source_text=request.source_text,
                premise_id=request.premise_id if request.premise_id is not None else 1,
            )
        else:
            payload = _candidate_frame_payload(
                source_id=request.source_id,
                source_text=request.source_text,
                candidate_label=request.candidate_label or "claim",
            )

        frame = parse_frame(payload)
        return FrameExtractionResult(
            frame=frame,
            raw_content=json.dumps(payload, ensure_ascii=True),
            raw_payload=payload,
            cache_key=f"mock:{request.mode}:{request.source_id}",
            diagnostics={
                "model": "mock",
                "prompt_version": "test",
                "extractor_version": "test",
                "attempts": 1,
                "repair_count": 0,
                "retry_count": 0,
                "cache_hit": False,
                "errors": [],
            },
        )


class AsyncPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_local_samples_share_premise_conversion(self):
        extractor = _ScriptedFrameExtractor(delay_by_mode={"premise": 0.05})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=2, request_timeout_seconds=1.0, sample_timeout_seconds=2.0)

        samples = [
            LocalRuntimeSample(sample_id="s2", record_id=7, question_id=2, premises_nl=["Mai is eligible."], question="Is Mai eligible?"),
            LocalRuntimeSample(sample_id="s1", record_id=7, question_id=1, premises_nl=["Mai is eligible."], question="Is Mai eligible?"),
        ]
        results = await pipeline.process_local_samples(samples)

        self.assertEqual([result.question_id for result in results], [1, 2])
        cache_key = build_local_premise_cache_key(7)
        self.assertEqual(pipeline.premise_conversion_counts.get(cache_key), 1)
        premise_calls = [call for call in extractor.calls if call.mode == "premise"]
        self.assertEqual(len(premise_calls), 1)

    async def test_repeated_api_requests_share_premise_conversion_with_single_flight(self):
        extractor = _ScriptedFrameExtractor(delay_by_mode={"premise": 0.05})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=4, request_timeout_seconds=1.0, sample_timeout_seconds=2.0)
        query = RuntimeQuery.from_mapping({"premises-NL": ["Mai is eligible."], "question": "Is Mai eligible?"})

        first, second = await asyncio.gather(pipeline.process_runtime_query(query), pipeline.process_runtime_query(query))

        cache_key = build_api_premise_cache_key(query.premises_nl)
        self.assertEqual(pipeline.premise_conversion_counts.get(cache_key), 1)
        self.assertEqual(first.status, "partial")
        self.assertEqual(second.status, "partial")
        premise_calls = [call for call in extractor.calls if call.mode == "premise"]
        self.assertEqual(len(premise_calls), 1)
        self.assertTrue(first.single_flight_waited or second.single_flight_waited or first.cache_hit or second.cache_hit)

    async def test_failed_sample_does_not_stop_batch(self):
        extractor = _ScriptedFrameExtractor(fail_source_ids={"question"})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=2, request_timeout_seconds=1.0, sample_timeout_seconds=2.0)

        samples = [
            LocalRuntimeSample(sample_id="s1", record_id=1, question_id=1, premises_nl=["Mai is eligible."], question="Is Mai eligible?"),
            LocalRuntimeSample(
                sample_id="s2",
                record_id=1,
                question_id=2,
                premises_nl=["Mai is eligible."],
                question="What can we conclude?\nA. Mai is eligible\nB. Mai is not eligible",
            ),
        ]
        results = await pipeline.process_local_samples(samples)

        self.assertEqual(len(results), 2)
        self.assertEqual(sum(1 for item in results if item.status == "failed"), 1)
        self.assertEqual(sum(1 for item in results if item.status == "partial"), 1)

    async def test_request_timeout_marks_result_failed(self):
        extractor = _ScriptedFrameExtractor(delay_by_mode={"candidate": 0.05})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=1, request_timeout_seconds=0.01, sample_timeout_seconds=1.0)
        query = RuntimeQuery.from_mapping({"premises-NL": ["Mai is eligible."], "question": "Is Mai eligible?"})

        result = await pipeline.process_runtime_query(query)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.trace.root_cause_category, "timeout_error")

    async def test_sample_timeout_marks_result_failed(self):
        extractor = _ScriptedFrameExtractor(delay_by_mode={"premise": 0.02, "candidate": 0.02})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=1, request_timeout_seconds=1.0, sample_timeout_seconds=0.01)
        query = RuntimeQuery.from_mapping({"premises-NL": ["Mai is eligible."], "question": "Is Mai eligible?"})

        result = await pipeline.process_runtime_query(query)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.trace.root_cause_category, "timeout_error")

    async def test_artifacts_are_written_for_partial_and_failed_results(self):
        extractor = _ScriptedFrameExtractor(fail_source_ids={"question"})
        pipeline = AsyncRuntimePipeline(frame_extractor=extractor, max_concurrency=2, request_timeout_seconds=1.0, sample_timeout_seconds=2.0)

        samples = [
            LocalRuntimeSample(sample_id="s1", record_id=2, question_id=1, premises_nl=["Mai is eligible."], question="Is Mai eligible?"),
            LocalRuntimeSample(
                sample_id="s2",
                record_id=2,
                question_id=2,
                premises_nl=["Mai is eligible."],
                question="Choose one:\nA. Mai is eligible\nB. Mai is not eligible",
            ),
        ]
        results = await pipeline.process_local_samples(samples)

        output_dir = Path(".pytest_tmp_batch6_pipeline")
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            artifacts = write_pipeline_artifacts(output_dir, results)
            predictions = json.loads(Path(artifacts.predictions_path).read_text(encoding="utf-8"))
            traces = [json.loads(line) for line in Path(artifacts.debug_traces_path).read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(predictions), 2)
            self.assertEqual(len(traces), 2)
            self.assertEqual(sum(1 for item in predictions if item["status"] == "failed"), 1)
            self.assertEqual(sum(1 for item in predictions if item["status"] == "partial"), 1)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

