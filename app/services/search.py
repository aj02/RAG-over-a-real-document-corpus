"""Pure retrieval — debug endpoint that skips the LLM."""

from __future__ import annotations

import time

from app.config import get_settings
from app.models.schemas import RetrievedChunk, SearchResponse
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import rerank as rerank_chunks
from app.retrieval.types import ScoredChunk


def _to_retrieved(scored: ScoredChunk) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=scored.chunk.chunk_id,
        doc_id=scored.chunk.doc_id,
        doc_title=scored.chunk.doc_title,
        regulator=scored.chunk.regulator,
        section_path=scored.chunk.section_path,
        page_start=scored.chunk.page_start,
        page_end=scored.chunk.page_end,
        text=scored.chunk.text,
        score=scored.score,
        source_url=scored.chunk.source_url,
    )


async def search_only(
    *,
    query: str,
    top_k: int,
    regulator_filter: str | None,
    rerank: bool,
) -> SearchResponse:
    settings = get_settings()
    started = time.perf_counter()

    fused = await hybrid_search(
        query,
        regulator_filter=regulator_filter,
        fused_top_k=settings.rerank_top_k,
    )

    if rerank and fused:
        ranked = await rerank_chunks(query, fused, top_k=top_k)
        method = "hybrid+rerank"
    else:
        ranked = fused[:top_k]
        method = "hybrid"

    chunks = [_to_retrieved(r) for r in ranked]
    return SearchResponse(
        query=query,
        chunks=chunks,
        latency_ms=int((time.perf_counter() - started) * 1000),
        retrieval_method=method,  # type: ignore[arg-type]
    )
