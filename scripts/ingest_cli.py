"""CLI for running ingestion outside the API.

Useful for the first-time bootstrap (download_corpus -> ingest_cli) and for
reproducing eval runs without standing up the FastAPI server.

Usage:
    python -m scripts.ingest_cli                  # ingest the full manifest
    python -m scripts.ingest_cli --doc SEBI-MC-MF-2024 --force
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db import close_pool, init_pool
from app.ingestion.pipeline import run_default_ingestion
from app.logging import configure_logging, get_logger


async def _run(doc_ids: list[str] | None, force: bool) -> int:
    configure_logging()
    log = get_logger("ingest_cli")
    await init_pool()
    try:
        result = await run_default_ingestion(doc_ids=doc_ids, force=force)
        log.info(
            "ingest_cli.done",
            run_id=result.run_id,
            docs_processed=result.docs_processed,
            chunks_written=result.chunks_written,
            status=result.status,
            duration_seconds=round(result.duration_seconds, 2),
            errors=result.errors,
        )
        return 0 if result.status == "success" else 1
    finally:
        await close_pool()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--doc", action="append", help="restrict to specific doc_ids")
    p.add_argument("--force", action="store_true", help="re-ingest even if present")
    args = p.parse_args()
    return asyncio.run(_run(args.doc, args.force))


if __name__ == "__main__":
    sys.exit(main())
