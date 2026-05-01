"""BM25 keyword search over the chunk corpus.

We don't try to maintain a full-text index inside Postgres for a few reasons:
  - rank_bm25's BM25Okapi gives us full control over tokenisation
  - the corpus is small (a few thousand chunks); rebuilding the in-memory
    index on first query is fast and simplifies the system

The index is built lazily and cached in a module-level singleton. After
ingestion runs, callers should ``invalidate()`` to force a rebuild.
"""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.db import acquire
from app.logging import get_logger
from app.retrieval.types import ChunkRecord, ScoredChunk

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have he her his i in is it its of on or that
    the their them they this to was were will with would you your we our us my me
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Cheap tokenizer: lowercase, alpha-num runs, drop stopwords."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


@dataclass
class _BM25Index:
    bm25: BM25Okapi
    chunks: list[ChunkRecord]


_lock = threading.Lock()
_index: _BM25Index | None = None


async def _load_chunks() -> list[ChunkRecord]:
    rows: list[ChunkRecord] = []
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                c.chunk_id, c.doc_id, d.title, d.regulator,
                c.section_path, c.page_start, c.page_end,
                c.text, d.source_url
            FROM chunks c JOIN documents d USING (doc_id)
            ORDER BY c.doc_id, c.chunk_index
            """
        )
        for row in await cur.fetchall():
            rows.append(
                ChunkRecord(
                    chunk_id=row[0],
                    doc_id=row[1],
                    doc_title=row[2],
                    regulator=row[3],
                    section_path=row[4],
                    page_start=row[5],
                    page_end=row[6],
                    text=row[7],
                    source_url=row[8],
                )
            )
    return rows


async def _build() -> _BM25Index:
    chunks = await _load_chunks()
    if not chunks:
        # Build over a single dummy doc so .get_scores() doesn't divide by zero.
        bm25 = BM25Okapi([["__empty__"]])
        return _BM25Index(bm25=bm25, chunks=[])
    tokenised = [tokenize(c.text) for c in chunks]
    bm25 = BM25Okapi(tokenised)
    log.info("bm25.index_built", n_chunks=len(chunks))
    return _BM25Index(bm25=bm25, chunks=chunks)


def invalidate() -> None:
    """Drop the cached index. Call after ingestion."""
    global _index
    with _lock:
        _index = None


async def _get_index() -> _BM25Index:
    global _index
    if _index is not None:
        return _index
    # Build outside the lock to avoid blocking other coroutines on the I/O.
    built = await _build()
    with _lock:
        if _index is None:
            _index = built
        return _index


async def bm25_search(
    query: str,
    *,
    top_k: int,
    regulator_filter: str | None = None,
) -> list[ScoredChunk]:
    if top_k <= 0:
        return []
    idx = await _get_index()
    if not idx.chunks:
        return []

    tokens = tokenize(query)
    if not tokens:
        return []

    scores = idx.bm25.get_scores(tokens)
    # Apply regulator filter post-scoring; with corpora of this size it's fine.
    indexed = [
        (i, s)
        for i, s in enumerate(scores)
        if (regulator_filter is None or idx.chunks[i].regulator == regulator_filter)
        and s > 0.0
    ]
    indexed.sort(key=lambda t: t[1], reverse=True)
    indexed = indexed[:top_k]

    out: list[ScoredChunk] = []
    for i, s in indexed:
        out.append(
            ScoredChunk(
                chunk=idx.chunks[i],
                score=float(s),
                sources={"bm25": float(s)},
            )
        )
    return out


# Background invalidation helper used by the ingest endpoint.
async def maybe_warm() -> None:
    """Trigger a build if not already cached. Best-effort, never raises."""
    try:
        await _get_index()
    except Exception as e:  # noqa: BLE001
        log.warning("bm25.warm_failed", error=str(e))


def schedule_warm(loop: asyncio.AbstractEventLoop | None = None) -> None:
    loop = loop or asyncio.get_event_loop()
    loop.create_task(maybe_warm())
