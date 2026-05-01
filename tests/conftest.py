"""Pytest config — sets safe defaults so tests don't accidentally hit the network
or load the embedding model.
"""

from __future__ import annotations

import os

# Run tests as if no API keys were configured. Each test that needs them can
# monkeypatch before import.
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("INGEST_BEARER_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "postgresql://regrag:regrag@localhost:5432/regrag")
