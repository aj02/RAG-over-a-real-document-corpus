"""Internal retrieval DTOs.

Kept separate from app.models.schemas because these flow through internal
pipeline stages and we don't want to round-trip through Pydantic at every
hop — they're plain dataclasses with attached score metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Regulator = Literal["SEBI", "RBI"]


@dataclass
class ChunkRecord:
    """Hydrated chunk loaded from Postgres."""

    chunk_id: str
    doc_id: str
    doc_title: str
    regulator: Regulator
    section_path: str | None
    page_start: int | None
    page_end: int | None
    text: str
    source_url: str


@dataclass
class ScoredChunk:
    """A chunk with a score from a particular retrieval stage."""

    chunk: ChunkRecord
    score: float
    sources: dict[str, float] = field(default_factory=dict)
    """Per-stage scores, e.g. {"bm25": 0.84, "vector": 0.91, "rrf": ..., "rerank": ...}.
    Keeping these around makes debugging *and* eval far simpler."""
