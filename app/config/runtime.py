"""Runtime configuration loading from .env and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .redaction import redact_mapping


class EnvConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class RuntimeConfig:
    shopaikey_base_url: str
    shopaikey_api_key: str
    shopaikey_model: str
    llm_temperature: float
    llm_max_tokens: int

    def to_safe_dict(self) -> dict[str, object]:
        """Return a redacted dictionary for diagnostics."""
        return redact_mapping(
            {
                "SHOPAIKEY_BASE_URL": self.shopaikey_base_url,
                "SHOPAIKEY_API_KEY": self.shopaikey_api_key,
                "SHOPAIKEY_MODEL": self.shopaikey_model,
                "LLM_TEMPERATURE": self.llm_temperature,
                "LLM_MAX_TOKENS": self.llm_max_tokens,
            }
        )


def load_runtime_config(
    env_path: str | Path = ".env",
    *,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Load runtime config from `.env` plus optional environment overrides."""
    file_values = parse_env_file(env_path)
    env_values = dict(environ or os.environ)

    def resolve(key: str, default: str | None = None) -> str | None:
        if key in env_values and env_values[key] != "":
            return env_values[key]
        if key in file_values and file_values[key] != "":
            return file_values[key]
        return default

    base_url = _require_value("SHOPAIKEY_BASE_URL", resolve("SHOPAIKEY_BASE_URL"))
    api_key = _require_value("SHOPAIKEY_API_KEY", resolve("SHOPAIKEY_API_KEY"))
    model = _require_value("SHOPAIKEY_MODEL", resolve("SHOPAIKEY_MODEL"))

    llm_temperature = _parse_float("LLM_TEMPERATURE", resolve("LLM_TEMPERATURE", "0.0"))
    llm_max_tokens = _parse_int("LLM_MAX_TOKENS", resolve("LLM_MAX_TOKENS", "1024"))

    return RuntimeConfig(
        shopaikey_base_url=base_url,
        shopaikey_api_key=api_key,
        shopaikey_model=model,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
    )


def parse_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        raise EnvConfigError(f"Missing env file: {env_path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise EnvConfigError(f"Invalid .env line {line_number}: {raw_line}")
        key, value = stripped.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _require_value(key: str, value: str | None) -> str:
    if value is None or value.strip() == "":
        raise EnvConfigError(f"Missing required config value: {key}")
    return value.strip()


def _parse_float(key: str, value: str | None) -> float:
    required = _require_value(key, value)
    try:
        return float(required)
    except ValueError as exc:  # pragma: no cover - defensive parse guard
        raise EnvConfigError(f"Invalid float for {key}: {required}") from exc


def _parse_int(key: str, value: str | None) -> int:
    required = _require_value(key, value)
    try:
        return int(required)
    except ValueError as exc:  # pragma: no cover - defensive parse guard
        raise EnvConfigError(f"Invalid int for {key}: {required}") from exc

