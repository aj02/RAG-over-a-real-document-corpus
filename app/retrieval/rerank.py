"""Rerank candidate chunks with a cross-encoder (or Cohere).

Cross-encoders score (query, passage) jointly and are far more accurate than
bi-encoders at ranking — but expensive, so we only run them on the top-30
RRF candidates. The local default ``BAAI/bge-reranker-base`` is small enough
to run on CPU with acceptable latency (~200 ms for 30 pairs).

Cohere is supported as an opt-in if you have an API key — useful when
running in resource-constrained containers.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.config import get_settings
from app.logging import get_logger
from app.retrieval.types import ScoredChunk

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

log = get_logger(__name__)

_lock = threading.Lock()
_local_model: "CrossEncoder | None" = None


def _load_local() -> "CrossEncoder":
    global _local_model
    with _lock:
        if _local_model is not None:
            return _local_model
        from sentence_transformers import CrossEncoder

        settings = get_settings()
        log.info("rerank.loading_local", model=settings.reranker_model)
        _local_model = CrossEncoder(settings.reranker_model, max_length=512)
        log.info("rerank.local_ready")
        return _local_model


def _rerank_local_sync(query: str, candidates: list[ScoredChunk]) -> list[float]:
    model = _load_local()
    pairs = [(query, sc.chunk.text) for sc in candidates]
    scores = model.predict(pairs, show_progress_bar=False)
    return [float(s) for s in scores]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.3, max=2.0),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _rerank_cohere(query: str, candidates: list[ScoredChunk]) -> list[float]:
    settings = get_settings()
    if not settings.cohere_api_key:
        raise RuntimeError("RERANKER_PROVIDER=cohere but COHERE_API_KEY is unset")

    payload = {
        "model": "rerank-v3.0",
        "query": query,
        "documents": [sc.chunk.text for sc in candidates],
        "top_n": len(candidates),
    }
    headers = {"Authorization": f"Bearer {settings.cohere_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.cohere.ai/v1/rerank", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
    # Cohere returns results out of order with relevance_score in [0, 1].
    scores = [0.0] * len(candidates)
    for r in data.get("results", []):
        scores[r["index"]] = float(r["relevance_score"])
    return scores


async def rerank(
    query: str,
    candidates: list[ScoredChunk],
    *,
    top_k: int | None = None,
) -> list[ScoredChunk]:
    """Re-score and re-order candidates. Returns the top_k (or all if None).

    The reranker score replaces the fused score so downstream consumers see
    a calibrated relevance signal in ``ScoredChunk.score``. The original
    fused score is preserved under ``sources['rrf']``.
    """
    if not candidates:
        return []

    settings = get_settings()
    if settings.reranker_provider == "cohere":
        scores = await _rerank_cohere(query, candidates)
    else:
        # Cross-encoder is sync + CPU-bound; offload to the default executor.
        scores = await asyncio.get_running_loop().run_in_executor(
            None, _rerank_local_sync, query, candidates
        )

    for sc, s in zip(candidates, scores, strict=True):
        sc.sources["rerank"] = float(s)
        sc.score = float(s)

    # Drop near-zero / negative scores if a floor is configured.
    threshold = settings.min_rerank_score
    candidates = [c for c in candidates if c.score >= threshold]
    candidates.sort(key=lambda c: c.score, reverse=True)
    if top_k is not None:
        candidates = candidates[:top_k]
    log.info("rerank.done", kept=len(candidates))
    return candidates
