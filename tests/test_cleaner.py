"""Cleaner edge cases."""

from __future__ import annotations

from app.ingestion.cleaner import clean_page_text, clean_pages
from app.ingestion.loader import PageText


def test_hyphenated_linebreak_repaired() -> None:
    out = clean_page_text("regula-\ntion of mutual funds")
    assert "regulation of mutual funds" in out


def test_ligatures_normalised() -> None:
    out = clean_page_text("ﬁnancial inﬂuence ﬀalse")
    assert "financial" in out
    assert "influence" in out


def test_repeated_headers_dropped() -> None:
    pages = [
        PageText(page_number=i, text="RESERVE BANK OF INDIA\n\nClause text page " + str(i))
        for i in range(1, 6)
    ]
    cleaned = clean_pages(pages)
    for c in cleaned:
        assert not c.text.startswith("RESERVE BANK OF INDIA")
        assert "Clause text" in c.text


def test_unique_first_lines_preserved() -> None:
    pages = [
        PageText(page_number=1, text="Unique title one\nbody one"),
        PageText(page_number=2, text="Different title two\nbody two"),
    ]
    cleaned = clean_pages(pages)
    assert "Unique title one" in cleaned[0].text
    assert "Different title two" in cleaned[1].text


def test_bare_page_numbers_stripped() -> None:
    out = clean_page_text("Some content\n42\nMore content")
    assert "42" not in out.splitlines()


def test_multispace_collapsed() -> None:
    out = clean_page_text("foo     bar")
    assert "foo bar" in out
