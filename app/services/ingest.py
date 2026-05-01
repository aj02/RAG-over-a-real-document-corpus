"""Ingestion endpoint glue."""

from __future__ import annotations

from app.ingestion.pipeline import run_default_ingestion
from app.models.schemas import IngestResponse


async def run_ingestion(
    *,
    doc_ids: list[str] | None = None,
    force: bool = False,
) -> IngestResponse:
    result = await run_default_ingestion(doc_ids=doc_ids, force=force)
    return IngestResponse(
        run_id=result.run_id,
        docs_processed=result.docs_processed,
        chunks_written=result.chunks_written,
        status=result.status,  # type: ignore[arg-type]
        duration_seconds=round(result.duration_seconds, 3),
        errors=result.errors,
    )
