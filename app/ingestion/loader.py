"""PDF loading with per-page text extraction.

Strategy:
  - Use pdfplumber as the primary extractor — it preserves layout reasonably
    well for text-heavy regulatory docs.
  - Fall back to pypdf if pdfplumber fails on a particular page (some SEBI
    PDFs trip pdfplumber's parser).
  - Always emit (page_number, text) so downstream code can attach a precise
    page citation to every chunk.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pypdf

from app.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class PageText:
    page_number: int  # 1-indexed
    text: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_with_pdfplumber(path: Path) -> Iterator[PageText]:
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "loader.pdfplumber.page_failed",
                    path=str(path),
                    page=i,
                    error=str(e),
                )
                text = ""
            yield PageText(page_number=i, text=text)


def _extract_with_pypdf(path: Path) -> Iterator[PageText]:
    reader = pypdf.PdfReader(str(path))
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001
            log.warning(
                "loader.pypdf.page_failed", path=str(path), page=i, error=str(e)
            )
            text = ""
        yield PageText(page_number=i, text=text)


def load_pdf(path: Path) -> list[PageText]:
    """Return one ``PageText`` per page. Falls back to pypdf on plumber failure."""
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    try:
        pages = list(_extract_with_pdfplumber(path))
        # If plumber returns blanks for everything, retry with pypdf.
        if not any(p.text.strip() for p in pages):
            log.info("loader.pdfplumber.empty_falling_back", path=str(path))
            pages = list(_extract_with_pypdf(path))
        return pages
    except Exception as e:  # noqa: BLE001
        log.warning("loader.pdfplumber.failed_falling_back", path=str(path), error=str(e))
        return list(_extract_with_pypdf(path))


def page_count(path: Path) -> int:
    return len(pypdf.PdfReader(str(path)).pages)
