"""Tokenizer behaviour for BM25."""

from __future__ import annotations

from app.retrieval.bm25 import tokenize


def test_tokenize_lowercases_and_drops_stopwords() -> None:
    out = tokenize("The Investment Adviser must register with SEBI.")
    assert out == ["investment", "adviser", "must", "register", "sebi"]


def test_tokenize_keeps_alphanumeric_runs() -> None:
    out = tokenize("Section 3.1 describes Form A2.")
    # Note: "3.1" splits into "3" and "1"; that's intentional given our regex.
    assert "section" in out
    assert "form" in out
    assert "a2" in out


def test_tokenize_handles_empty() -> None:
    assert tokenize("") == []
    assert tokenize("   the and of   ") == []


def test_tokenize_unicode_safe() -> None:
    out = tokenize("KYC обязательный")  # cyrillic is dropped
    assert "kyc" in out
