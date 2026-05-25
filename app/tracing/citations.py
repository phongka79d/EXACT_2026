"""Deterministic source-citation resolution for proof-trace steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.logic.ast import LogicNode

from .models import SourceCitation


@dataclass(frozen=True)
class CitationResolution:
    citation: SourceCitation | None
    warnings: list[str]


class CitationRegistry:
    """Lookup registry that resolves source metadata into trace-safe citations."""

    def __init__(
        self,
        *,
        by_source_id: dict[str, SourceCitation],
        by_premise_id: dict[int, SourceCitation],
        by_candidate_label: dict[str, SourceCitation],
    ) -> None:
        self._by_source_id = dict(by_source_id)
        self._by_premise_id = dict(by_premise_id)
        self._by_candidate_label = dict(by_candidate_label)

    def resolve(
        self,
        *,
        source_id: str | None = None,
        premise_id: int | None = None,
        candidate_label: str | None = None,
    ) -> CitationResolution:
        normalized_source_id = _normalize_text(source_id)
        normalized_candidate_label = _normalize_text(candidate_label)
        warnings: list[str] = []

        citation: SourceCitation | None = None
        if normalized_source_id is not None:
            citation = self._by_source_id.get(normalized_source_id)
        if citation is None and premise_id is not None:
            citation = self._by_premise_id.get(premise_id)
        if citation is None and normalized_candidate_label is not None:
            citation = self._by_candidate_label.get(normalized_candidate_label)

        if citation is None:
            fallback_source_id = normalized_source_id or (
                f"candidate_{normalized_candidate_label}" if normalized_candidate_label is not None else None
            )
            if fallback_source_id is None:
                return CitationResolution(citation=None, warnings=["citation_missing_source_id"])
            warnings.append(f"citation_unresolved_source:{fallback_source_id}")
            citation = SourceCitation(
                source_id=fallback_source_id,
                source_text=None,
                premise_id=premise_id,
                candidate_label=normalized_candidate_label,
            )
        else:
            citation = _prefer_metadata(
                citation,
                premise_id=premise_id,
                candidate_label=normalized_candidate_label,
            )

        if citation.source_text is None or not citation.source_text.strip():
            warnings.append(f"citation_missing_source_text:{citation.source_id}")
        return CitationResolution(citation=citation, warnings=warnings)

    def resolve_premise_ids(self, premise_ids: Sequence[int]) -> tuple[list[SourceCitation], list[str]]:
        citations: list[SourceCitation] = []
        warnings: list[str] = []
        seen: set[tuple[str, int | None, str | None]] = set()
        for premise_id in premise_ids:
            resolved = self.resolve(premise_id=premise_id)
            warnings.extend(resolved.warnings)
            citation = resolved.citation
            if citation is None:
                continue
            key = (citation.source_id, citation.premise_id, citation.candidate_label)
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
        return citations, _unique_strings(warnings)


def build_source_registry(premise_asts: Sequence[LogicNode], candidate_asts: Sequence[LogicNode]) -> CitationRegistry:
    by_source_id: dict[str, SourceCitation] = {}
    by_premise_id: dict[int, SourceCitation] = {}
    by_candidate_label: dict[str, SourceCitation] = {}

    for node in premise_asts:
        _register_node(node, by_source_id, by_premise_id, by_candidate_label)
    for node in candidate_asts:
        _register_node(node, by_source_id, by_premise_id, by_candidate_label)

    return CitationRegistry(
        by_source_id=by_source_id,
        by_premise_id=by_premise_id,
        by_candidate_label=by_candidate_label,
    )


def _register_node(
    node: LogicNode,
    by_source_id: dict[str, SourceCitation],
    by_premise_id: dict[int, SourceCitation],
    by_candidate_label: dict[str, SourceCitation],
) -> None:
    source_id = _normalize_text(getattr(node, "source_id", None))
    source_text = _normalize_text(getattr(node, "source_text", None))
    premise_id = getattr(node, "premise_id", None)
    candidate_label = _normalize_text(getattr(node, "candidate_label", None))

    if source_id is None:
        if premise_id is not None:
            source_id = f"premise_{premise_id:04d}"
        elif candidate_label is not None:
            source_id = f"candidate_{candidate_label}"
        else:
            return

    citation = SourceCitation(
        source_id=source_id,
        source_text=source_text,
        premise_id=premise_id if isinstance(premise_id, int) else None,
        candidate_label=candidate_label,
    )

    existing = by_source_id.get(source_id)
    by_source_id[source_id] = _prefer_richer(existing, citation)
    if citation.premise_id is not None:
        existing = by_premise_id.get(citation.premise_id)
        by_premise_id[citation.premise_id] = _prefer_richer(existing, citation)
    if citation.candidate_label is not None:
        existing = by_candidate_label.get(citation.candidate_label)
        by_candidate_label[citation.candidate_label] = _prefer_richer(existing, citation)


def _prefer_richer(existing: SourceCitation | None, candidate: SourceCitation) -> SourceCitation:
    if existing is None:
        return candidate
    if _has_source_text(existing) and not _has_source_text(candidate):
        return existing
    if _has_source_text(candidate) and not _has_source_text(existing):
        return candidate
    if existing.premise_id is None and candidate.premise_id is not None:
        return candidate
    if existing.candidate_label is None and candidate.candidate_label is not None:
        return candidate
    return existing


def _prefer_metadata(citation: SourceCitation, *, premise_id: int | None, candidate_label: str | None) -> SourceCitation:
    return SourceCitation(
        source_id=citation.source_id,
        source_text=citation.source_text,
        premise_id=premise_id if premise_id is not None else citation.premise_id,
        candidate_label=candidate_label if candidate_label is not None else citation.candidate_label,
    )


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _has_source_text(citation: SourceCitation) -> bool:
    return citation.source_text is not None and bool(citation.source_text.strip())


def _unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
