"""Document listing — backs the /documents page.

For each document in the catalogue we surface a small "preview" paragraph
to give visitors a sense of what the regulation covers. We do NOT call an
LLM here; instead we use the first ingested chunk that has substantive
content (skipping bare-TOC / cover-page chunks). For Indian regulatory
documents the first non-TOC chunk is almost always the preamble / scope
statement, which is a useful proxy for a one-sentence abstract.

If/when an LLM-generated summary becomes worthwhile, replace ``preview``
with a precomputed column on ``documents`` so we don't pay per-request
LLM cost.
"""

from __future__ import annotations

import re
from typing import cast

from app.db import acquire
from app.logging import get_logger
from app.models.schemas import DocumentsResponse, DocumentSummary, Regulator

log = get_logger(__name__)

_MAX_PREVIEW_CHARS = 480
_MIN_PREVIEW_CHARS = 120


_TOC_PATTERN = re.compile(r"\.{4,}|\bcontents\b|\btable of contents\b", re.IGNORECASE)


def _is_likely_toc(text: str) -> bool:
    """Crude heuristic: many dot-leaders or the literal 'Table of Contents'."""
    return bool(_TOC_PATTERN.search(text[:600]))


def _make_preview(text: str) -> str:
    """Take a generous snippet and tidy whitespace."""
    flat = " ".join(text.split())
    if len(flat) <= _MAX_PREVIEW_CHARS:
        return flat
    cut = flat[:_MAX_PREVIEW_CHARS]
    # Don't end mid-word — back off to the last sentence/space boundary.
    last_period = cut.rfind(". ")
    if last_period >= _MIN_PREVIEW_CHARS:
        return cut[: last_period + 1]
    last_space = cut.rfind(" ")
    if last_space >= _MIN_PREVIEW_CHARS:
        return cut[:last_space].rstrip() + "…"
    return cut.rstrip() + "…"


async def list_documents() -> DocumentsResponse:
    """Return one summary row per document in the corpus.

    Pulls metadata from ``documents`` and joins to the first chunk that
    has substantive content. Documents that have no chunks (i.e.
    metadata-only) still appear, with an empty preview.
    """
    sql = """
        WITH ranked AS (
            SELECT
                c.doc_id,
                c.chunk_index,
                c.text,
                ROW_NUMBER() OVER (PARTITION BY c.doc_id ORDER BY c.chunk_index) AS rn
            FROM chunks c
            WHERE LENGTH(c.text) >= 200
        )
        SELECT
            d.doc_id,
            d.title,
            d.regulator,
            d.category,
            d.issue_date::text AS issue_date,
            d.source_url,
            d.num_pages,
            d.ingested_at::text AS ingested_at,
            (SELECT COUNT(*) FROM chunks c2 WHERE c2.doc_id = d.doc_id) AS chunk_count,
            -- gather the first three substantive chunks; we'll filter TOC client-side
            (SELECT array_agg(text ORDER BY chunk_index)
               FROM ranked r WHERE r.doc_id = d.doc_id AND r.rn <= 3) AS first_chunks
        FROM documents d
        ORDER BY d.regulator, d.title
    """
    out: list[DocumentSummary] = []
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute(sql)
        rows = await cur.fetchall()
        for row in rows:
            (
                doc_id,
                title,
                regulator,
                category,
                issue_date,
                source_url,
                num_pages,
                ingested_at,
                chunk_count,
                first_chunks,
            ) = row

            preview = ""
            if first_chunks:
                # Pick the earliest chunk that does NOT look like a TOC.
                for candidate in first_chunks:
                    if not _is_likely_toc(candidate):
                        preview = _make_preview(candidate)
                        break
                if not preview:
                    preview = _make_preview(first_chunks[0])

            out.append(
                DocumentSummary(
                    doc_id=doc_id,
                    title=title,
                    regulator=cast(Regulator, regulator),
                    category=category,
                    issue_date=issue_date,
                    source_url=source_url,
                    num_pages=num_pages,
                    chunk_count=int(chunk_count or 0),
                    ingested_at=ingested_at,
                    preview=preview,
                )
            )
    log.info("documents.listed", n=len(out))
    return DocumentsResponse(documents=out, total=len(out))
