"""Prompt builders for compact parse-frame extraction."""

from __future__ import annotations

from typing import Literal

PROMPT_VERSION = "batch5_v1"
EXTRACTOR_VERSION = "batch5_v1"


def build_premise_frame_messages(source_text: str, source_id: str, premise_id: int) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": (
                "Parse the premise into one compact parse frame.\n"
                "Return JSON object only, no markdown.\n"
                f"source_id: {source_id}\n"
                f"premise_id: {premise_id}\n"
                f"source_text: {source_text}\n"
                "For premise mode, JSON must include: kind, source_id, source_text, premise_id, warnings.\n"
                "If the text is a direct fact, prefer this shape:\n"
                "{\"kind\":\"fact\",\"entity\":\"<entity>\",\"facts\":[{\"type\":\"numeric_value\",\"entity\":\"<entity>\","
                "\"attribute\":\"<attribute>\",\"value\":1}],\"source_id\":\""
                + source_id
                + "\",\"source_text\":\""
                + source_text
                + "\",\"premise_id\":"
                + str(premise_id)
                + ",\"warnings\":[]}"
            ),
        },
    ]


def build_candidate_frame_messages(
    source_text: str,
    source_id: str,
    candidate_label: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": (
                "Parse the candidate/question text into one compact parse frame.\n"
                "Return JSON object only, no markdown.\n"
                f"source_id: {source_id}\n"
                f"candidate_label: {candidate_label}\n"
                f"source_text: {source_text}\n"
                "For candidate mode, JSON must include: kind, source_id, source_text, candidate_label, warnings.\n"
                "A valid claim shape is:\n"
                "{\"kind\":\"claim\",\"answer_type\":\"claim\",\"claim\":{\"type\":\"predicate\",\"entity\":\"<entity>\","
                "\"name\":\"<predicate_name>\",\"polarity\":true},\"source_id\":\""
                + source_id
                + "\",\"source_text\":\""
                + source_text
                + "\",\"candidate_label\":\""
                + candidate_label
                + "\",\"warnings\":[]}"
            ),
        },
    ]


def build_repair_frame_messages(
    *,
    source_text: str,
    source_id: str,
    premise_id: int | None,
    candidate_label: str | None,
    frame_mode: Literal["premise", "candidate"],
    validation_error: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": (
                "Your previous JSON frame was invalid.\n"
                f"frame_mode: {frame_mode}\n"
                f"validation_error: {validation_error}\n"
                f"source_id: {source_id}\n"
                f"premise_id: {premise_id}\n"
                f"candidate_label: {candidate_label}\n"
                f"source_text: {source_text}\n"
                "Return one corrected compact parse frame JSON object only."
            ),
        },
    ]


def _system_instruction() -> str:
    return (
        "You are a compact parse-frame extractor for educational logic text.\n"
        "Use only these frame kinds: rule, fact, claim, compound, ambiguous.\n"
        "Use source metadata exactly as provided and keep fields JSON-serializable.\n"
        "Use strict slot types: predicate, numeric_condition, numeric_value, arithmetic_expression, entity_relation.\n"
        "Fact frames require a `facts` array of slot objects.\n"
        "Rule frames require `scope`, `if` array, and `then` array.\n"
        "Claim frames require `answer_type` and `claim` slot.\n"
        "Every frame must include `warnings` as a JSON array (use [] if none).\n"
        "Do not answer the question; output only one parse frame JSON object."
    )
