"""Tests for the structure-aware chunker.

Covers the edge cases that broke earlier iterations:
  - empty input
  - a single short page (must still produce one chunk, not zero)
  - heading boundaries split chunks even mid-page
  - overlap is preserved between consecutive chunks
  - chunk ids are deterministic + content-hashed
  - tail smaller than min_tokens is folded into the previous chunk
"""

from __future__ import annotations

from app.ingestion.chunker import chunk_document
from app.ingestion.loader import PageText


def _page(n: int, text: str) -> PageText:
    return PageText(page_number=n, text=text)


def test_empty_input_yields_no_chunks() -> None:
    assert chunk_document("doc-empty", []) == []
    assert chunk_document("doc-empty", [_page(1, "")]) == []


def test_single_short_page_yields_one_chunk() -> None:
    page = _page(1, "Short paragraph about KYC requirements for low-risk customers.")
    chunks = chunk_document("doc-1", [page], target_tokens=500, min_tokens=4)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.page_start == 1 and c.page_end == 1
    assert "KYC" in c.text
    assert c.chunk_id.startswith("doc-1::0000::")


def test_heading_starts_new_chunk_when_buffer_meets_min() -> None:
    body = " ".join([f"word{i}" for i in range(120)])
    page = _page(1, f"{body}\n3. New Section heading\nMore content here {body}")
    chunks = chunk_document("doc-2", [page], target_tokens=500, min_tokens=80)
    assert len(chunks) >= 2
    # The chunk that *starts* with the new section should have section_path set.
    section_chunks = [c for c in chunks if c.section_path and "New Section" in c.section_path]
    assert section_chunks, "expected at least one chunk under '3 New Section'"


def test_overlap_carries_tokens_forward() -> None:
    big = " ".join(f"w{i}" for i in range(1500))
    page = _page(1, big)
    chunks = chunk_document(
        "doc-3", [page], target_tokens=500, overlap_tokens=50, min_tokens=10
    )
    assert len(chunks) >= 2
    # The last 50 tokens of chunk N should be a prefix of chunk N+1.
    for a, b in zip(chunks, chunks[1:], strict=False):
        a_tail = a.text.split()[-50:]
        b_head = b.text.split()[:50]
        # They overlap by exactly the overlap window (modulo the heading line
        # being prepended in some boundary cases).
        common = set(a_tail) & set(b_head)
        assert len(common) >= 30, "expected meaningful token overlap"


def test_chunk_ids_are_deterministic_and_unique() -> None:
    page = _page(1, "alpha beta gamma " * 200)
    a = chunk_document("doc-4", [page])
    b = chunk_document("doc-4", [page])
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert len({c.chunk_id for c in a}) == len(a)


def test_tail_below_min_is_folded() -> None:
    # 220 tokens then a 10-token tail at min_tokens=80 should produce 1 chunk.
    body = " ".join(f"w{i}" for i in range(220))
    page = _page(1, body + "\n\nshort tail of just ten more words here right now")
    chunks = chunk_document(
        "doc-5", [page], target_tokens=500, overlap_tokens=0, min_tokens=80
    )
    # Buffer never crosses target_tokens, so we get exactly one chunk and the
    # tail is concatenated into it.
    assert len(chunks) == 1
    assert "short tail" in chunks[0].text


def test_section_path_nests_with_dotted_numbering() -> None:
    text = (
        "1. Preliminary\n"
        "Some preliminary content goes here for the first section. " * 5
        + "\n1.1 Definitions\nDefinitions of important terms used. " * 5
        + "\n1.1.1 Customer\nA customer means any person. " * 8
    )
    chunks = chunk_document(
        "doc-6", [_page(1, text)], target_tokens=80, min_tokens=10
    )
    paths = [c.section_path for c in chunks if c.section_path]
    assert any("Definitions" in p for p in paths)
    assert any("Customer" in p for p in paths)


def test_invalid_overlap_raises() -> None:
    page = _page(1, "x")
    try:
        chunk_document("d", [page], target_tokens=10, overlap_tokens=10)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when overlap >= target")
