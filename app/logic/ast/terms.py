"""Typed term models for logic AST nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, TypeAlias


@dataclass(frozen=True)
class VarTerm:
    kind: Literal["var"]
    name: str


@dataclass(frozen=True)
class ConstTerm:
    kind: Literal["const"]
    name: str
    surface: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class NumberTerm:
    kind: Literal["number"]
    value: float | int
    unit: str | None = None


Term: TypeAlias = VarTerm | ConstTerm | NumberTerm


def parse_term(payload: Mapping[str, Any]) -> Term:
    kind = _require_string(payload, "kind")

    if kind == "var":
        return VarTerm(kind="var", name=_require_string(payload, "name"))
    if kind == "const":
        return ConstTerm(
            kind="const",
            name=_require_string(payload, "name"),
            surface=_optional_string(payload.get("surface")),
            domain=_optional_string(payload.get("domain")),
        )
    if kind == "number":
        return NumberTerm(
            kind="number",
            value=_require_number(payload, "value"),
            unit=_optional_string(payload.get("unit")),
        )

    raise ValueError(f"Unsupported term kind: {kind}")


def _require_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{key}` must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Optional string value must be a non-empty string when provided")
    return value.strip()


def _require_number(payload: Mapping[str, Any], key: str) -> float | int:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"`{key}` must be numeric")
    return value
