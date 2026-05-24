"""Premise cache key utilities."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

_PREMISE_SEPARATOR = "\n<PREMISE_SEP>\n"
_HASH_SEPARATOR = "\n<HASH_COMPONENT>\n"


def normalize_premises_text(premises_nl: Sequence[str]) -> str:
    """Normalize premises by trimming each premise while preserving order."""
    if isinstance(premises_nl, (str, bytes)):
        raise ValueError("`premises_nl` must be a sequence of strings")

    normalized: list[str] = []
    for premise in premises_nl:
        if not isinstance(premise, str):
            raise ValueError("Each premise must be a string")
        stripped = premise.strip()
        if not stripped:
            raise ValueError("Premises must not contain empty strings")
        normalized.append(stripped)

    if not normalized:
        raise ValueError("`premises_nl` must contain at least one premise")

    return _PREMISE_SEPARATOR.join(normalized)


def hash_premises_text(
    premises_nl: Sequence[str],
    *,
    hash_components: Sequence[str] = (),
) -> str:
    """Create a stable hash over normalized premises and optional version components."""
    payload_parts = [normalize_premises_text(premises_nl)]
    payload_parts.extend(_normalize_hash_components(hash_components))
    payload = _HASH_SEPARATOR.join(payload_parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_local_premise_cache_key(record_id: int) -> str:
    """Build local evaluation cache key using the record identifier."""
    if not isinstance(record_id, int):
        raise ValueError("`record_id` must be an integer")
    return f"record:{record_id}"


def build_api_premise_cache_key(
    premises_nl: Sequence[str],
    *,
    hash_components: Sequence[str] = (),
) -> str:
    """Build API runtime cache key from normalized premise text hash."""
    return f"premises_hash:{hash_premises_text(premises_nl, hash_components=hash_components)}"


def _normalize_hash_components(components: Sequence[str]) -> list[str]:
    normalized_components: list[str] = []
    for component in components:
        if not isinstance(component, str):
            raise ValueError("Hash components must be strings")
        stripped = component.strip()
        if not stripped:
            raise ValueError("Hash components must not be empty")
        normalized_components.append(stripped)
    return normalized_components

