"""Postgres writes for ingestion: documents, chunks, embeddings.

All writes happen in a single transaction per document so a failure mid-doc
leaves the DB in a clean state (no orphan chunks). Re-ingestion is idempotent
because chunk_ids are deterministic — we use ``ON CONFLICT DO UPDATE``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.db import acquire
from app.ingestion.chunker import Chunk
from app.ingestion.manifest import ManifestEntry
from app.logging import get_logger

log = get_logger(__name__)


async def document_exists(doc_id: str) -> bool:
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM documents WHERE doc_id = %s", (doc_id,))
        return (await cur.fetchone()) is not None


async def delete_document(doc_id: str) -> None:
    """Cascades to chunks via FK ON DELETE CASCADE."""
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))


async def upsert_document(entry: ManifestEntry, *, num_pages: int, sha256: str) -> None:
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO documents (
                doc_id, title, regulator, category, issue_date,
                source_url, num_pages, sha256
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE SET
                title = EXCLUDED.title,
                regulator = EXCLUDED.regulator,
                category = EXCLUDED.category,
                issue_date = EXCLUDED.issue_date,
                source_url = EXCLUDED.source_url,
                num_pages = EXCLUDED.num_pages,
                sha256 = EXCLUDED.sha256,
                ingested_at = NOW()
            """,
            (
                entry.doc_id,
                entry.title,
                entry.regulator,
                entry.category,
                entry.issue_date,
                str(entry.source_url),
                num_pages,
                sha256,
            ),
        )
        await conn.commit()


async def write_chunks(
    doc_id: str,
    chunks: Sequence[Chunk],
    embeddings: np.ndarray,
) -> int:
    """Insert/upsert chunks + their embeddings.

    Returns the number of rows written.
    """
    if len(chunks) != embeddings.shape[0]:
        raise ValueError(
            f"chunk/embedding length mismatch: {len(chunks)} vs {embeddings.shape[0]}"
        )

    written = 0
    async with acquire() as conn:
        # Replace-all-chunks for the document. Simpler & safer than partial
        # upserts when the chunker output changes between runs.
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))

            for c, vec in zip(chunks, embeddings, strict=True):
                await cur.execute(
                    """
                    INSERT INTO chunks (
                        chunk_id, doc_id, chunk_index, section_path,
                        page_start, page_end, token_count, text, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        c.chunk_id,
                        doc_id,
                        c.chunk_index,
                        c.section_path,
                        c.page_start,
                        c.page_end,
                        c.token_count,
                        c.text,
                        vec.tolist(),
                    ),
                )
                written += 1
        await conn.commit()
    log.info("store.chunks_written", doc_id=doc_id, count=written)
    return written


async def start_run() -> int:
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO ingestion_runs (status) VALUES ('running') RETURNING run_id"
        )
        row = await cur.fetchone()
        await conn.commit()
        if row is None:
            raise RuntimeError("failed to create ingestion_run")
        return int(row[0])


async def finish_run(
    run_id: int,
    *,
    docs_processed: int,
    chunks_written: int,
    status: str,
    error_message: str | None = None,
) -> None:
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE ingestion_runs SET
                finished_at = NOW(),
                status = %s,
                docs_processed = %s,
                chunks_written = %s,
                error_message = %s
            WHERE run_id = %s
            """,
            (status, docs_processed, chunks_written, error_message, run_id),
        )
        await conn.commit()
