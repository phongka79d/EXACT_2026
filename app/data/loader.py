"""Flattened dataset loading and runtime-safety sanitization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import EvaluationSample, LocalRuntimeSample

REFERENCE_ONLY_FIELDS = {"premises-FOL", "answer", "explanation", "idx"}
RUNTIME_SAMPLE_FIELDS = {"sample_id", "record_id", "question_id", "premises-NL", "question"}


def load_flattened_dataset(path: str | Path) -> list[EvaluationSample]:
    rows = _load_json_list(path)
    return [EvaluationSample.from_mapping(row) for row in rows]


def load_runtime_samples(path: str | Path) -> list[LocalRuntimeSample]:
    evaluation_samples = load_flattened_dataset(path)
    return [sample.to_runtime_sample() for sample in evaluation_samples]


def sanitize_runtime_sample(sample: EvaluationSample | Mapping[str, Any]) -> LocalRuntimeSample:
    if isinstance(sample, EvaluationSample):
        return sample.to_runtime_sample()

    runtime_payload = {key: sample[key] for key in RUNTIME_SAMPLE_FIELDS if key in sample}
    return LocalRuntimeSample.from_mapping(runtime_payload)


def strip_reference_fields(sample: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy without reference-only annotations."""
    return {key: value for key, value in sample.items() if key not in REFERENCE_ONLY_FIELDS}


def _load_json_list(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, list):
        raise ValueError(f"Expected list JSON payload in {file_path}")
    if any(not isinstance(item, dict) for item in loaded):
        raise ValueError(f"Expected each JSON row to be an object in {file_path}")
    return loaded

