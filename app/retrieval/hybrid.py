"""Hybrid retrieval: parallel BM25 + vector with Reciprocal Rank Fusion.

Why RRF instead of normalising scores? BM25 raw scores and cosine
similarities live on different scales and don't combine cleanly via
arithmetic — the dominant signal becomes whichever has higher variance.
RRF combines purely by rank, so each retriever contributes its top-k
opinions equally. The constant ``k`` damps the contribution of items
ranked far down each list:

    rrf_score(item) = sum over retrievers of 1 / (k + rank)

For our defaults (k=60, top-50 from each retriever) the scores end up in
roughly [0, 0.033], comfortably above the floating-point noise floor.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from app.config import get_settings
from app.ingestion.embedder import embed_query
from app.logging import get_logger
from app.retrieval.bm25 import bm25_search
from app.retrieval.types import ScoredChunk
from app.retrieval.vector import vector_search

log = get_logger(__name__)


def reciprocal_rank_fusion(
    rankings: Iterable[list[ScoredChunk]],
    *,
    k: int = 60,
) -> list[ScoredChunk]:
    """Merge ranked lists with RRF. Returns a list sorted by fused score desc."""
    fused: dict[str, ScoredChunk] = {}
    rankings = list(rankings)

    for ranked in rankings:
        for rank, sc in enumerate(ranked, start=1):
            cid = sc.chunk.chunk_id
            contribution = 1.0 / (k + rank)
            if cid in fused:
                existing = fused[cid]
                existing.score += contribution
                existing.sources.update(sc.sources)
            else:
                merged = ScoredChunk(
                    chunk=sc.chunk,
                    score=contribution,
                    sources=dict(sc.sources),
                )
                fused[cid] = merged

    return sorted(fused.values(), key=lambda s: s.score, reverse=True)


async def hybrid_search(
    query: str,
    *,
    bm25_top_k: int | None = None,
    vector_top_k: int | None = None,
    fused_top_k: int | None = None,
    regulator_filter: str | None = None,
) -> list[ScoredChunk]:
    settings = get_settings()
    bm25_k = bm25_top_k or settings.bm25_top_k
    vec_k = vector_top_k or settings.vector_top_k
    out_k = fused_top_k or settings.rerank_top_k

    # Embed once; the BM25 path doesn't need it but the vector path does.
    query_vec = await asyncio.get_running_loop().run_in_executor(None, embed_query, query)

    bm25_task = bm25_search(query, top_k=bm25_k, regulator_filter=regulator_filter)
    vec_task = vector_search(query_vec, top_k=vec_k, regulator_filter=regulator_filter)
    bm25_hits, vec_hits = await asyncio.gather(bm25_task, vec_task)

    log.info(
        "retrieval.parallel",
        bm25_hits=len(bm25_hits),
        vector_hits=len(vec_hits),
    )

    fused = reciprocal_rank_fusion(
        [bm25_hits, vec_hits], k=settings.rrf_k
    )[:out_k]

    # Stamp the rrf score in sources for debug visibility.
    for sc in fused:
        sc.sources["rrf"] = sc.score
    return fused
