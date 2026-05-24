"""Typed runtime and evaluation sample models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _validate_premises_nl(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("`premises-NL` must be a list of strings")
    return list(value)


def _validate_question(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("`question` must be a non-empty string")
    return value


@dataclass(frozen=True)
class RuntimeQuery:
    premises_nl: list[str]
    question: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RuntimeQuery":
        return cls(
            premises_nl=_validate_premises_nl(payload.get("premises-NL")),
            question=_validate_question(payload.get("question")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"premises-NL": list(self.premises_nl), "question": self.question}


@dataclass(frozen=True)
class LocalRuntimeSample:
    sample_id: str
    record_id: int
    question_id: int
    premises_nl: list[str]
    question: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LocalRuntimeSample":
        return cls(
            sample_id=_require_string(payload, "sample_id"),
            record_id=_require_int(payload, "record_id"),
            question_id=_require_int(payload, "question_id"),
            premises_nl=_validate_premises_nl(payload.get("premises-NL")),
            question=_validate_question(payload.get("question")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "record_id": self.record_id,
            "question_id": self.question_id,
            "premises-NL": list(self.premises_nl),
            "question": self.question,
        }

    def to_runtime_query(self) -> RuntimeQuery:
        return RuntimeQuery(premises_nl=list(self.premises_nl), question=self.question)


@dataclass(frozen=True)
class EvaluationSample:
    sample_id: str
    record_id: int
    question_id: int
    premises_nl: list[str]
    question: str
    premises_fol: Any | None = None
    answer: Any | None = None
    explanation: Any | None = None
    idx: Any | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EvaluationSample":
        return cls(
            sample_id=_require_string(payload, "sample_id"),
            record_id=_require_int(payload, "record_id"),
            question_id=_require_int(payload, "question_id"),
            premises_nl=_validate_premises_nl(payload.get("premises-NL")),
            question=_validate_question(payload.get("question")),
            premises_fol=payload.get("premises-FOL"),
            answer=payload.get("answer"),
            explanation=payload.get("explanation"),
            idx=payload.get("idx"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "record_id": self.record_id,
            "question_id": self.question_id,
            "premises-NL": list(self.premises_nl),
            "premises-FOL": self.premises_fol,
            "question": self.question,
            "answer": self.answer,
            "explanation": self.explanation,
            "idx": self.idx,
        }

    def to_runtime_sample(self) -> LocalRuntimeSample:
        return LocalRuntimeSample(
            sample_id=self.sample_id,
            record_id=self.record_id,
            question_id=self.question_id,
            premises_nl=list(self.premises_nl),
            question=self.question,
        )


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"`{key}` must be a non-empty string")
    return value


def _require_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"`{key}` must be an integer")
    return value

