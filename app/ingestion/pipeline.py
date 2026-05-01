"""Ingestion orchestration: manifest -> PDFs -> chunks -> Postgres.

This module implements the full pipeline once a PDF is on disk; downloading
is handled by ``scripts/download_corpus.py`` so we keep network concerns out
of the runtime path.

Idempotency: re-running on the same corpus produces the same chunk_ids
(deterministic hashes) and replaces all chunks for each document atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.ingestion.chunker import chunk_document
from app.ingestion.cleaner import clean_pages
from app.ingestion.embedder import embed_texts, warm
from app.ingestion.loader import load_pdf, page_count, sha256_file
from app.ingestion.manifest import Manifest, ManifestEntry, filter_by_ids, load_manifest
from app.ingestion.store import (
    document_exists,
    finish_run,
    start_run,
    upsert_document,
    write_chunks,
)
from app.logging import get_logger

log = get_logger(__name__)


@dataclass
class IngestionResult:
    run_id: int
    docs_processed: int
    chunks_written: int
    status: str
    duration_seconds: float
    errors: list[str]


def _pdf_path(entry: ManifestEntry, pdf_dir: Path) -> Path:
    return pdf_dir / f"{entry.doc_id}.pdf"


async def ingest_one(
    entry: ManifestEntry,
    *,
    pdf_dir: Path,
    target_tokens: int,
    overlap_tokens: int,
    min_tokens: int,
) -> int:
    """Ingest a single document. Returns chunks_written."""
    path = _pdf_path(entry, pdf_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"PDF not on disk for {entry.doc_id}: {path}. "
            f"Run scripts/download_corpus.py first."
        )

    log.info("ingest.start_doc", doc_id=entry.doc_id, title=entry.title)

    raw_pages = load_pdf(path)
    cleaned = clean_pages(raw_pages)
    chunks = chunk_document(
        entry.doc_id,
        cleaned,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
        min_tokens=min_tokens,
    )

    if not chunks:
        log.warning("ingest.no_chunks", doc_id=entry.doc_id)
        return 0

    log.info("ingest.embedding", doc_id=entry.doc_id, chunks=len(chunks))
    embeddings = embed_texts([c.text for c in chunks])

    n_pages = page_count(path)
    sha = sha256_file(path)

    await upsert_document(entry, num_pages=n_pages, sha256=sha)
    written = await write_chunks(entry.doc_id, chunks, embeddings)
    log.info(
        "ingest.done_doc",
        doc_id=entry.doc_id,
        pages=n_pages,
        chunks=written,
    )
    return written


async def ingest_manifest(
    manifest: Manifest,
    *,
    pdf_dir: Path,
    doc_ids: list[str] | None = None,
    force: bool = False,
) -> IngestionResult:
    """Run the ingestion pipeline over the (filtered) manifest."""
    import time

    settings = get_settings()
    entries = filter_by_ids(manifest, doc_ids)

    # Pre-load embedder once so we don't pay per-doc startup cost.
    warm()

    run_id = await start_run()
    started = time.perf_counter()

    docs_done = 0
    total_chunks = 0
    errors: list[str] = []

    for entry in entries:
        try:
            if not force and await document_exists(entry.doc_id):
                log.info("ingest.skip_existing", doc_id=entry.doc_id)
                continue
            n = await ingest_one(
                entry,
                pdf_dir=pdf_dir,
                target_tokens=settings.chunk_target_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
                min_tokens=settings.chunk_min_tokens,
            )
            total_chunks += n
            docs_done += 1
        except Exception as e:  # noqa: BLE001
            log.exception("ingest.doc_failed", doc_id=entry.doc_id)
            errors.append(f"{entry.doc_id}: {e}")

    duration = time.perf_counter() - started
    status = "success" if not errors else ("partial" if docs_done else "failed")
    await finish_run(
        run_id,
        docs_processed=docs_done,
        chunks_written=total_chunks,
        status="success" if status == "success" else "failed",
        error_message="; ".join(errors) if errors else None,
    )

    log.info(
        "ingest.run_complete",
        run_id=run_id,
        docs_processed=docs_done,
        chunks=total_chunks,
        status=status,
        duration_s=round(duration, 2),
    )
    return IngestionResult(
        run_id=run_id,
        docs_processed=docs_done,
        chunks_written=total_chunks,
        status=status,
        duration_seconds=duration,
        errors=errors,
    )


def default_manifest_path() -> Path:
    return Path("data/corpus_manifest.json")


def default_pdf_dir() -> Path:
    return Path("data/pdfs")


async def run_default_ingestion(
    *,
    doc_ids: list[str] | None = None,
    force: bool = False,
) -> IngestionResult:
    manifest = load_manifest(default_manifest_path())
    return await ingest_manifest(
        manifest,
        pdf_dir=default_pdf_dir(),
        doc_ids=doc_ids,
        force=force,
    )
