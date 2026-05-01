"""LLM provider selection — single env var picks Anthropic or OpenAI."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMClient


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient

        return AnthropicClient()
    if settings.llm_provider == "openai":
        from app.llm.openai_client import OpenAIClient

        return OpenAIClient()
    raise RuntimeError(f"unknown LLM_PROVIDER: {settings.llm_provider}")
