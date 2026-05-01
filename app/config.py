"""Centralised settings, loaded from environment variables.

We use pydantic-settings so values are validated and the rest of the app can
treat configuration as an immutable, typed object.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    app_bind_host: str = "0.0.0.0"
    app_bind_port: int = 8000
    ingest_bearer_token: str = "replace-me-with-a-long-random-string"
    # Comma-separated origins permitted to call the API from a browser.
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- Database ----
    database_url: str = "postgresql://regrag:regrag_dev_password@localhost:5432/regrag"
    db_pool_min: int = 1
    db_pool_max: int = 8
    db_timeout_seconds: float = 15.0

    # ---- Embeddings ----
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_batch_size: int = 32

    # ---- Reranker ----
    reranker_provider: Literal["local", "cohere"] = "local"
    reranker_model: str = "BAAI/bge-reranker-base"
    cohere_api_key: str | None = None

    # ---- LLM ----
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 60.0

    # ---- Retrieval ----
    bm25_top_k: int = 50
    vector_top_k: int = 50
    rrf_k: int = 60
    rerank_top_k: int = 30
    answer_top_k: int = 5
    min_rerank_score: float = 0.0

    # ---- Chunking ----
    chunk_target_tokens: int = 500
    chunk_overlap_tokens: int = 50
    chunk_min_tokens: int = 80

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor so the env is parsed exactly once per process."""
    return Settings()
