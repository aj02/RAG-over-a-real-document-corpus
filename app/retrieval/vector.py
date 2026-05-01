"""Vector search via pgvector.

pgvector's cosine distance operator is ``<=>`` and returns a value in
[0, 2] where 0 means identical. We convert to a similarity score in [0, 1]
so it's easier to reason about.
"""

from __future__ import annotations

import numpy as np

from app.db import acquire
from app.retrieval.types import ChunkRecord, ScoredChunk


async def vector_search(
    query_vec: np.ndarray,
    *,
    top_k: int,
    regulator_filter: str | None = None,
) -> list[ScoredChunk]:
    """Return the top_k chunks ranked by cosine similarity.

    The IVFFlat index requires ``SET LOCAL ivfflat.probes = N`` for higher
    recall; we set it conservatively to 10. For a corpus of ~5-10k chunks
    this gives near-exact results with fast latency.
    """
    if top_k <= 0:
        return []

    vec_param = query_vec.tolist()
    params: list[object] = [vec_param]  # for SELECT distance
    where_sql = ""
    if regulator_filter:
        where_sql = "WHERE d.regulator = %s"
        params.append(regulator_filter)
    params.append(vec_param)  # for ORDER BY distance
    params.append(top_k)

    sql = f"""
        SELECT
            c.chunk_id,
            c.doc_id,
            d.title,
            d.regulator,
            c.section_path,
            c.page_start,
            c.page_end,
            c.text,
            d.source_url,
            1 - (c.embedding <=> %s::vector) AS similarity
        FROM chunks c
        JOIN documents d USING (doc_id)
        {where_sql}
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s
    """

    out: list[ScoredChunk] = []
    async with acquire() as conn, conn.cursor() as cur:
        await cur.execute("SET LOCAL ivfflat.probes = 10")
        await cur.execute(sql, params)
        rows = await cur.fetchall()
        for row in rows:
            (
                chunk_id,
                doc_id,
                title,
                regulator,
                section_path,
                page_start,
                page_end,
                text,
                source_url,
                similarity,
            ) = row
            out.append(
                ScoredChunk(
                    chunk=ChunkRecord(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        doc_title=title,
                        regulator=regulator,
                        section_path=section_path,
                        page_start=page_start,
                        page_end=page_end,
                        text=text,
                        source_url=source_url,
                    ),
                    score=float(similarity),
                    sources={"vector": float(similarity)},
                )
            )
    return out
