"""Structure-aware chunking for regulatory text.

Why not naive character / token splits? Regulatory documents are organised as
nested numbered clauses ("3.", "3.1", "3.1.1") with cross-references. Chopping
at fixed character boundaries severs a clause from its number, which destroys
the most useful retrieval signal — a user asking about "clause 3.1.1" must be
able to find the chunk containing that label.

Algorithm:
  1. Walk pages in order, accumulating a running list of (text, page_number).
  2. Detect section headings (lines that look like "1.", "1.1", "Section 4",
     "Chapter II", or an UPPER CASE single-line heading) and treat them as
     hard boundaries that *start* a new chunk.
  3. Build chunks of approximately ``target_tokens`` tokens. We use a
     whitespace token approximation here — the embedder uses its own tokenizer
     anyway, and ~4 chars/token holds for English regulatory prose.
  4. Add ``overlap_tokens`` of trailing context to the next chunk so a clause
     reference at the boundary isn't lost.
  5. Track ``section_path`` (e.g. "3.1.1 Definitions") and the page range so
     each chunk can be cited precisely.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.ingestion.loader import PageText


# A line is considered a heading if it matches any of these — order matters,
# we try the most specific first.
_HEADING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "1.", "1.1", "1.1.1" with optional title text
    re.compile(r"^\s*(\d+(?:\.\d+){0,4})\.?\s+(.+)$"),
    # "Section 4", "Section IV"
    re.compile(r"^\s*(Section|SECTION|Chapter|CHAPTER|Part|PART|Annex|ANNEXURE|Schedule|SCHEDULE)\s+([A-Za-z0-9IVXLCDM]+)[:.\-—\s]*(.*)$"),
)


@dataclass
class Chunk:
    chunk_index: int
    text: str
    section_path: str | None
    page_start: int
    page_end: int
    token_count: int
    chunk_id: str = ""  # populated by ``finalise``


@dataclass
class _Buffer:
    """Mutable accumulator we flush into Chunks."""

    tokens: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    section_path: str | None = None

    @property
    def length(self) -> int:
        return len(self.tokens)

    def is_empty(self) -> bool:
        return not self.tokens

    def add(self, words: list[str], page_number: int) -> None:
        if not words:
            return
        if self.page_start is None:
            self.page_start = page_number
        self.page_end = page_number
        self.tokens.extend(words)


def _tokenise(text: str) -> list[str]:
    """Whitespace tokenisation. Embedder uses its own tokenizer downstream;
    this is only for chunk size estimation and is intentionally cheap."""
    return text.split()


def _detect_heading(line: str) -> tuple[str, str] | None:
    """Return (number, title) if line looks like a heading, else None."""
    s = line.strip()
    if not s or len(s) > 200:
        return None

    for pat in _HEADING_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 2:  # numeric "1.1 title"
            number, title = groups
            return number, title.strip()
        if len(groups) == 3:  # "Section X title"
            kind, number, title = groups
            return f"{kind.title()} {number}", title.strip()

    # ALL CAPS short heading like "DEFINITIONS"
    if (
        s.isupper()
        and 3 <= len(s) <= 80
        and not any(c.isdigit() for c in s)
        and " " in s
    ):
        return "", s.title()
    return None


def _heading_path(stack: list[str], number: str, title: str) -> tuple[list[str], str]:
    """Update the heading stack and return (new_stack, formatted_path).

    For numeric headings we use the dot-depth as the level; for "Section X"
    headings we treat them as level-0 so they reset the stack.
    """
    label = (f"{number} {title}".strip()) if number else title

    if number and "." in number:
        depth = number.count(".")
    elif number and number.isdigit():
        depth = 0
    else:
        depth = 0

    new_stack = stack[:depth]
    new_stack.append(label)
    return new_stack, " > ".join(new_stack)


def _make_chunk_id(doc_id: str, index: int, text: str) -> str:
    """Deterministic id: doc_id + index + content hash. Re-ingestion of the
    same content produces the same id, so we can upsert idempotently."""
    h = hashlib.sha256()
    h.update(doc_id.encode())
    h.update(b"\x00")
    h.update(str(index).encode())
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return f"{doc_id}::{index:04d}::{h.hexdigest()[:12]}"


def chunk_document(
    doc_id: str,
    pages: Iterable[PageText],
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
    min_tokens: int = 80,
) -> list[Chunk]:
    """Produce structure-aware chunks for a document.

    Args:
        doc_id: stable identifier; used to derive deterministic chunk ids.
        pages: cleaned per-page text.
        target_tokens: approximate target chunk size (whitespace tokens).
        overlap_tokens: tokens duplicated at the end of each chunk into the
            start of the next, so cross-boundary context is preserved.
        min_tokens: chunks shorter than this get merged into the next chunk;
            avoids many tiny chunks at heading boundaries.
    """
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be in [0, target_tokens)")

    chunks: list[Chunk] = []
    buf = _Buffer()
    heading_stack: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf.is_empty():
            return
        text = " ".join(buf.tokens).strip()
        if not text:
            buf = _Buffer(section_path=buf.section_path)
            return
        idx = len(chunks)
        chunks.append(
            Chunk(
                chunk_index=idx,
                text=text,
                section_path=buf.section_path,
                page_start=buf.page_start or 1,
                page_end=buf.page_end or buf.page_start or 1,
                token_count=buf.length,
            )
        )
        # carry overlap forward
        carry = buf.tokens[-overlap_tokens:] if overlap_tokens else []
        buf = _Buffer(
            tokens=list(carry),
            page_start=buf.page_end,
            page_end=buf.page_end,
            section_path=buf.section_path,
        )

    for page in pages:
        if not page.text.strip():
            continue

        # Process line by line so headings can act as boundaries.
        for line in page.text.splitlines():
            heading = _detect_heading(line)
            if heading is not None:
                # Flush whatever we had, then update the heading stack.
                if buf.length >= min_tokens:
                    flush()
                number, title = heading
                heading_stack, path = _heading_path(heading_stack, number, title)
                buf.section_path = path
                # Include the heading line itself in the new chunk.
                buf.add(_tokenise(line), page.page_number)
                continue

            words = _tokenise(line)
            if not words:
                continue
            buf.add(words, page.page_number)

            if buf.length >= target_tokens:
                flush()

    # Final flush — but if the tail is too small, fold it into the previous chunk.
    if not buf.is_empty():
        if chunks and buf.length < min_tokens:
            last = chunks[-1]
            merged_text = (last.text + " " + " ".join(buf.tokens)).strip()
            chunks[-1] = Chunk(
                chunk_index=last.chunk_index,
                text=merged_text,
                section_path=last.section_path,
                page_start=last.page_start,
                page_end=buf.page_end or last.page_end,
                token_count=last.token_count + buf.length,
            )
        else:
            flush()

    # Now stamp deterministic chunk_ids.
    for i, c in enumerate(chunks):
        chunks[i] = Chunk(
            chunk_index=i,
            text=c.text,
            section_path=c.section_path,
            page_start=c.page_start,
            page_end=c.page_end,
            token_count=c.token_count,
            chunk_id=_make_chunk_id(doc_id, i, c.text),
        )
    return chunks
