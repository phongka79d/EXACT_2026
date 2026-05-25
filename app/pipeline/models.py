"""Result contracts for the Batch 6 async runtime pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.tracing import DebugTrace


@dataclass(frozen=True)
class PipelineSampleResult:
    sample_id: str | None
    record_id: int | None
    question_id: int | None
    answer: str
    explanation: str
    status: Literal["ok", "failed", "partial"]
    question_type: str | None
    cache_mode: Literal["local", "api", "none"]
    cache_key: str | None
    cache_hit: bool | None
    single_flight_waited: bool | None
    solver_handoff_ready: bool
    error: str | None
    trace: DebugTrace

    def to_prediction_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sample_id": self.sample_id,
            "record_id": self.record_id,
            "question_id": self.question_id,
            "answer": self.answer,
            "explanation": self.explanation,
            "status": self.status,
            "question_type": self.question_type,
            "cache_mode": self.cache_mode,
            "cache_hit": self.cache_hit,
            "single_flight_waited": self.single_flight_waited,
            "solver_handoff_ready": self.solver_handoff_ready,
            "error": self.error,
        }
        if self.cache_key is not None:
            payload["cache_key"] = self.cache_key
        return payload


@dataclass(frozen=True)
class PipelineArtifacts:
    predictions_path: str
    debug_traces_path: str

