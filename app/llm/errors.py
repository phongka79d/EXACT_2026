"""Error types for LLM client and frame extraction flows."""

from __future__ import annotations

from typing import Any


class LLMClientError(RuntimeError):
    """Base error for model-client failures."""


class LLMTransientError(LLMClientError):
    """Retryable provider/network failure."""


class LLMResponseError(LLMClientError):
    """Non-retryable response-shape or protocol failure."""


class FrameExtractionError(RuntimeError):
    """Raised when compact parse-frame extraction cannot succeed safely."""

    def __init__(self, message: str, *, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = dict(diagnostics or {})

