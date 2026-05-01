"""Text cleaning for PDF-extracted regulatory documents.

PDF extraction leaves a recognisable set of artifacts in this corpus:
  - hyphenated line breaks: "regula-\ntion"  -> "regulation"
  - footer noise like "Page 3 of 12" or "SEBI/HO/IMD/...."
  - repeated page headers from the regulator (e.g. "RESERVE BANK OF INDIA")
  - ligature glyphs (ﬁ, ﬂ) and non-breaking spaces
  - bullet glyphs that vary by font

We only do *safe* normalisation here — keep the actual content intact so the
chunker can still see section headings, numbered lists, etc.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.ingestion.loader import PageText

# A small allowlist of patterns to strip when they appear alone on a line —
# expanding this is risky because regulatory text is full of numbers.
_FOOTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),  # bare page numbers
)

_HYPHEN_LINEBREAK = re.compile(r"(\w+)-\n(\w+)")
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")

_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}


def _normalise_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    # Convert non-breaking spaces / soft hyphens to plain whitespace / nothing.
    text = text.replace(" ", " ").replace("­", "")
    return text


def _drop_repeated_headers(pages: list[PageText]) -> list[PageText]:
    """If the first non-empty line repeats on >50% of pages, drop it.

    Regulatory PDFs often have a corporate header on every page; removing it
    keeps that boilerplate out of every chunk.
    """
    if len(pages) < 4:
        return pages

    first_lines: list[str] = []
    for p in pages:
        for line in p.text.splitlines():
            if line.strip():
                first_lines.append(line.strip())
                break
        else:
            first_lines.append("")

    if not first_lines:
        return pages

    # Count occurrences of each first-line; drop ones repeated on > half the pages.
    counts: dict[str, int] = {}
    for line in first_lines:
        counts[line] = counts.get(line, 0) + 1
    threshold = max(2, len(pages) // 2)
    repeated = {line for line, n in counts.items() if line and n >= threshold}

    if not repeated:
        return pages

    cleaned: list[PageText] = []
    for p in pages:
        lines = p.text.splitlines()
        new_lines: list[str] = []
        skipped_first = False
        for line in lines:
            if not skipped_first and line.strip() in repeated:
                skipped_first = True
                continue
            new_lines.append(line)
        cleaned.append(PageText(page_number=p.page_number, text="\n".join(new_lines)))
    return cleaned


def _strip_footers(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        if any(p.match(line) for p in _FOOTER_PATTERNS):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def clean_page_text(text: str) -> str:
    text = _normalise_unicode(text)
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    text = _strip_footers(text)
    text = _TRAILING_WS.sub("\n", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTIPLE_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def clean_pages(pages: Iterable[PageText]) -> list[PageText]:
    page_list = list(pages)
    page_list = _drop_repeated_headers(page_list)
    return [
        PageText(page_number=p.page_number, text=clean_page_text(p.text))
        for p in page_list
    ]
