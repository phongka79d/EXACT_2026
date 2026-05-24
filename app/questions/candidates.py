"""Question typing and candidate extraction for runtime-safe inference."""

from __future__ import annotations

import re
from dataclasses import dataclass

_OPTION_LINE_RE = re.compile(r"^\s*([A-Z])\s*[\.\):\-]\s*(.+?)\s*$")
_YES_NO_STARTERS = (
    "is",
    "are",
    "am",
    "was",
    "were",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "will",
    "has",
    "have",
    "had",
    "may",
    "might",
    "must",
)
_NUMERIC_KEYWORDS = (
    "how many",
    "calculate",
    "compute",
    "percentage",
    "percent",
    "average",
    "total",
    "sum",
    "difference",
    "gpa",
    "score",
    "credits",
    "semester",
    "fee",
    "duration",
    "time",
    "at least",
    "at most",
    "minimum",
    "maximum",
    "greater than",
    "less than",
    "before",
    "after",
    "between",
)


@dataclass(frozen=True)
class CandidateClaim:
    label: str
    text: str
    question_type: str
    source_id: str
    source_text: str

    def to_payload(self) -> dict[str, str]:
        return {
            "label": self.label,
            "text": self.text,
            "question_type": self.question_type,
            "source_id": self.source_id,
            "source_text": self.source_text,
        }


@dataclass(frozen=True)
class CandidateExtractionResult:
    question_type: str
    question_text: str
    candidates: list[CandidateClaim]
    warnings: list[str]

    def to_payload(self) -> dict[str, object]:
        return {
            "question_type": self.question_type,
            "question_text": self.question_text,
            "candidates": [candidate.to_payload() for candidate in self.candidates],
            "warnings": list(self.warnings),
        }


def classify_question(question: str) -> str:
    return extract_candidates(question).question_type


def extract_candidates(question: str) -> CandidateExtractionResult:
    question_text = _validate_question(question)
    extracted_options = extract_labeled_options(question_text)

    if extracted_options:
        option_labels = [label for label, _ in extracted_options]
        candidates = [
            CandidateClaim(
                label=label,
                text=text,
                question_type="mcq",
                source_id=f"candidate_{label}",
                source_text=text,
            )
            for label, text in extracted_options
        ]
        if _has_well_formed_mcq_labels(option_labels):
            return CandidateExtractionResult(
                question_type="mcq",
                question_text=question_text,
                candidates=candidates,
                warnings=[],
            )
        return CandidateExtractionResult(
            question_type="ambiguous",
            question_text=question_text,
            candidates=candidates,
            warnings=["Malformed option labels; expected contiguous labels starting from A."],
        )

    if _is_yes_no_question(question_text):
        return _single_claim_result("yes_no_unknown", question_text, label="claim")
    if _is_numeric_question(question_text):
        return _single_claim_result("numeric", question_text, label="claim")
    if question_text.endswith("?"):
        return _single_claim_result("open_ended", question_text, label="open")

    return CandidateExtractionResult(
        question_type="ambiguous",
        question_text=question_text,
        candidates=[],
        warnings=["Could not determine question type from structure."],
    )


def extract_labeled_options(question: str) -> list[tuple[str, str]]:
    question_text = _validate_question(question)
    options: list[tuple[str, str]] = []

    for line in question_text.splitlines():
        matched = _OPTION_LINE_RE.match(line)
        if not matched:
            continue
        label = matched.group(1).upper()
        text = matched.group(2).strip()
        if text:
            options.append((label, text))
    return options


def _single_claim_result(question_type: str, question_text: str, *, label: str) -> CandidateExtractionResult:
    return CandidateExtractionResult(
        question_type=question_type,
        question_text=question_text,
        candidates=[
            CandidateClaim(
                label=label,
                text=question_text,
                question_type=question_type,
                source_id="question",
                source_text=question_text,
            )
        ],
        warnings=[],
    )


def _has_well_formed_mcq_labels(labels: list[str]) -> bool:
    if len(labels) < 2:
        return False
    if len(set(labels)) != len(labels):
        return False
    expected = [chr(ord("A") + index) for index in range(len(labels))]
    return labels == expected


def _is_yes_no_question(question_text: str) -> bool:
    lowered = question_text.lower()
    if not lowered.endswith("?"):
        return False
    stripped = lowered.rstrip("?").strip()
    for starter in _YES_NO_STARTERS:
        if stripped == starter or stripped.startswith(f"{starter} "):
            return True
    return False


def _is_numeric_question(question_text: str) -> bool:
    lowered = question_text.lower()
    if not lowered.endswith("?"):
        return False
    return any(keyword in lowered for keyword in _NUMERIC_KEYWORDS) or bool(re.search(r"\d", lowered))


def _validate_question(question: str) -> str:
    if not isinstance(question, str):
        raise ValueError("`question` must be a string")
    stripped = question.strip()
    if not stripped:
        raise ValueError("`question` must be a non-empty string")
    return stripped

