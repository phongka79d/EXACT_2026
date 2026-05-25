"""Artifact writers for runtime pipeline outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from app.tracing import write_debug_trace_jsonl

from .models import PipelineArtifacts, PipelineSampleResult


def write_pipeline_artifacts(output_dir: str | Path, results: Sequence[PipelineSampleResult]) -> PipelineArtifacts:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    predictions_path = output_path / "predictions.json"
    debug_traces_path = output_path / "debug_traces.jsonl"

    predictions_payload = [result.to_prediction_payload() for result in results]
    predictions_path.write_text(
        json.dumps(predictions_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_debug_trace_jsonl(debug_traces_path, [result.trace for result in results])

    return PipelineArtifacts(
        predictions_path=str(predictions_path),
        debug_traces_path=str(debug_traces_path),
    )
