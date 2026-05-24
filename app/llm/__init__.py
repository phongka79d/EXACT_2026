"""LLM parsing components for compact frame extraction."""

from .client import OpenAICompatibleChatClient
from .errors import FrameExtractionError, LLMClientError, LLMResponseError, LLMTransientError
from .extractor import (
    EXTRACTOR_VERSION,
    PROMPT_VERSION,
    FrameExtractionInput,
    FrameExtractionResult,
    LLMFrameExtractor,
    MockFrameExtractor,
    assert_runtime_safe_metadata,
    build_default_llm_frame_extractor,
    build_frame_cache_key,
)

__all__ = [
    "EXTRACTOR_VERSION",
    "PROMPT_VERSION",
    "FrameExtractionError",
    "FrameExtractionInput",
    "FrameExtractionResult",
    "LLMClientError",
    "LLMFrameExtractor",
    "LLMResponseError",
    "LLMTransientError",
    "MockFrameExtractor",
    "OpenAICompatibleChatClient",
    "assert_runtime_safe_metadata",
    "build_default_llm_frame_extractor",
    "build_frame_cache_key",
]

