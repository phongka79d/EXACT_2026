"""Prompt builders for compact parse-frame extraction."""

from __future__ import annotations

from typing import Literal

PROMPT_VERSION = "batch8_6_v1"
EXTRACTOR_VERSION = "batch8_6_v1"


def build_premise_frame_messages(source_text: str, source_id: str, premise_id: int) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": _premise_instruction(
                source_text=source_text,
                source_id=source_id,
                premise_id=premise_id,
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
            "content": _candidate_instruction(
                source_text=source_text,
                source_id=source_id,
                candidate_label=candidate_label,
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
    repair_instruction = _repair_instruction(
        source_text=source_text,
        source_id=source_id,
        premise_id=premise_id,
        candidate_label=candidate_label,
        frame_mode=frame_mode,
        validation_error=validation_error,
    )
    return [
        {
            "role": "system",
            "content": _system_instruction(),
        },
        {
            "role": "user",
            "content": repair_instruction,
        },
    ]


def _system_instruction() -> str:
    return (
        "You are a compact parse-frame extractor for educational logic text.\n"
        "You are a semantic parser only, not a solver and not a final-answer generator.\n"
        "Return exactly one JSON object and no markdown.\n"
        "Allowed frame kinds: rule, fact, claim, compound, ambiguous.\n"
        "Allowed slot types: predicate, numeric_condition, numeric_value, arithmetic_expression, entity_relation.\n"
        "Every frame must include `warnings` as a JSON array (use [] when none).\n"
        "Never include reference-only fields: `premises-FOL`, `answer`, `explanation`, `idx`.\n"
        "Never output final answer decisions, option picks, or verdict text.\n"
        "If the text is unclear, preserve uncertainty via `ambiguous` with warnings rather than inventing facts.\n"
        "Numeric extraction rules:\n"
        "- Use `numeric_value` for observed quantities (scores, GPA, percentages, fees, durations, deadlines).\n"
        "- Use `numeric_condition` for requirements/thresholds/comparisons (`at least`, `higher than`, `lower than`, `no more than`, `within`, `before`, `after`, `between`, `or higher`, `or lower`, `minimum`, `maximum`).\n"
        "- Use `arithmetic_expression` inside numeric conditions when text describes computed thresholds (percent-of, averages, weighted averages, offsets).\n"
        "- Preserve units explicitly when present (percent, points, credits, days, months, fees, currency units).\n"
        "- Do not flatten computed expressions into guessed constants.\n"
        "Nested/compound guidance:\n"
        "- Preserve implication direction and condition/consequence roles.\n"
        "- Do not reverse or merge directional clauses.\n"
        "- If one safe frame cannot preserve meaning, emit `compound` or `ambiguous` with warnings."
    )


def _premise_instruction(source_text: str, source_id: str, premise_id: int) -> str:
    return (
        "Frame mode: premise.\n"
        "Parse one premise into one compact frame.\n"
        "Prefer frame kinds by content:\n"
        "- `rule` for if/then or requirement-to-outcome statements.\n"
        "- `fact` for direct observations.\n"
        "- `compound` for multiple linked clauses where one flat rule/fact would lose structure.\n"
        "- `ambiguous` when referents, direction, or scope cannot be resolved safely.\n"
        "- `claim` is allowed only when the premise itself is explicitly a claim statement.\n"
        "Premise metadata requirements: `kind`, `source_id`, `source_text`, `premise_id`, `warnings`.\n"
        "`kind` must be one of: rule, fact, claim, compound, ambiguous.\n"
        "`premise_id` must be an integer number, not a string.\n"
        f"source_id: {source_id}\n"
        f"premise_id: {premise_id}\n"
        f"source_text: {source_text}\n"
        "For `rule`, include `scope`, `if`, and `then`.\n"
        "For `fact`, include `facts`.\n"
        "For numeric requirements, encode explicit numeric slots and avoid vague predicates.\n"
        "Do not answer any question or infer final eligibility decisions.\n"
        "Output JSON object only."
    )


def _candidate_instruction(source_text: str, source_id: str, candidate_label: str) -> str:
    return (
        "Frame mode: candidate.\n"
        "Parse the candidate/question text into one compact frame.\n"
        "Candidate metadata requirements: `kind`, `source_id`, `source_text`, `candidate_label`, `warnings`.\n"
        "`kind` must be one of: claim, ambiguous, compound.\n"
        f"source_id: {source_id}\n"
        f"candidate_label: {candidate_label}\n"
        f"source_text: {source_text}\n"
        "Candidate guidance:\n"
        "- Use `claim` for MCQ options, yes/no/unknown claims, numeric claims, and open-ended claim statements.\n"
        "- `claim.answer_type` must reflect intent (`mcq`, `yes_no_unknown`, `numeric`, `open_ended`, or `claim`).\n"
        "- Encode numeric claims with `numeric_condition` or `numeric_value` instead of plain predicates when quantities are explicit.\n"
        "- If wording is unresolved or under-specified, emit `ambiguous` with options/warnings.\n"
        "Do not choose an option, do not return yes/no, and do not provide final-answer text.\n"
        "Output JSON object only."
    )


def _repair_instruction(
    *,
    source_text: str,
    source_id: str,
    premise_id: int | None,
    candidate_label: str | None,
    frame_mode: Literal["premise", "candidate"],
    validation_error: str,
) -> str:
    shared = (
        "Your previous JSON frame was invalid.\n"
        f"frame_mode: {frame_mode}\n"
        f"validation_error: {validation_error}\n"
        f"source_id: {source_id}\n"
        f"premise_id: {premise_id}\n"
        f"candidate_label: {candidate_label}\n"
        f"source_text: {source_text}\n"
        "Return exactly one corrected compact parse frame JSON object.\n"
        "Do not include markdown, explanation text, or wrapper keys.\n"
        "Do not include `premises-FOL`, `answer`, `explanation`, or `idx`.\n"
    )
    if frame_mode == "premise":
        return (
            shared
            + "Required keys: kind, source_id, source_text, premise_id, warnings.\n"
            + "`premise_id` must be an integer.\n"
            + "If direct fact, use:\n"
            + "{\"kind\":\"fact\",\"entity\":\"student\",\"facts\":[{\"type\":\"numeric_value\",\"entity\":\"student\",\"attribute\":\"gpa\",\"value\":7.2}],\"source_id\":\""
            + source_id
            + "\",\"source_text\":\""
            + source_text
            + "\",\"premise_id\":"
            + str(premise_id)
            + ",\"warnings\":[]}\n"
            + "If uncertain, return `ambiguous` with reason/options/warnings."
        )
    return (
        shared
        + "Required keys: kind, source_id, source_text, candidate_label, warnings.\n"
        + "For candidate claims, use:\n"
        + "{\"kind\":\"claim\",\"answer_type\":\"claim\",\"claim\":{\"type\":\"predicate\",\"entity\":\"student\",\"name\":\"eligible\",\"polarity\":true},\"source_id\":\""
        + source_id
        + "\",\"source_text\":\""
        + source_text
        + "\",\"candidate_label\":\""
        + str(candidate_label or "")
        + "\",\"warnings\":[]}\n"
        + "If uncertain, return `ambiguous` with reason/options/warnings."
    )
