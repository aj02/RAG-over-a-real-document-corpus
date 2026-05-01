"""Refusal-on-empty-context behaviour.

The /ask service short-circuits before the LLM call when retrieval returns
nothing. This avoids hallucination on out-of-corpus questions and saves
cost. We test by monkeypatching ``hybrid_search`` to return an empty list.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import ask as ask_service


@pytest.mark.asyncio
async def test_empty_retrieval_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_hybrid(*args: object, **kwargs: object) -> list[object]:
        return []

    # Make sure no real DB or LLM is called.
    monkeypatch.setattr(ask_service, "hybrid_search", fake_hybrid)

    # The LLM client must not be touched.
    def boom() -> None:
        raise AssertionError("LLM should not have been called")

    monkeypatch.setattr(ask_service, "get_llm_client", lambda: boom())  # type: ignore[arg-type]

    resp = await ask_service.answer_question(
        question="Is this in scope?",
        top_k=5,
    )

    assert resp.confidence == "low"
    assert resp.citations == []
    assert any("not legal advice" in w.lower() for w in resp.warnings)
    assert any("no_relevant_context" in w for w in resp.warnings)
    assert "could not find" in resp.answer.lower()


@pytest.mark.asyncio
async def test_rerank_drops_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """If hybrid returns hits but rerank filters them all, we still refuse."""
    from app.retrieval.types import ChunkRecord, ScoredChunk

    fake_hit = ScoredChunk(
        chunk=ChunkRecord(
            chunk_id="c1", doc_id="d1", doc_title="t",
            regulator="SEBI", section_path=None,
            page_start=1, page_end=1, text="text",
            source_url="https://example.com",
        ),
        score=0.5,
        sources={},
    )

    async def fake_hybrid(*args: object, **kwargs: object) -> list[ScoredChunk]:
        return [fake_hit]

    async def fake_rerank(*args: object, **kwargs: object) -> list[ScoredChunk]:
        return []

    monkeypatch.setattr(ask_service, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(ask_service, "rerank_chunks", fake_rerank)

    def boom() -> None:
        raise AssertionError("LLM should not be called when rerank returns empty")

    monkeypatch.setattr(ask_service, "get_llm_client", lambda: boom())  # type: ignore[arg-type]

    resp = await ask_service.answer_question(question="anything", top_k=5)
    assert resp.confidence == "low"
    assert resp.citations == []


def test_async_setup() -> None:
    # Sanity: ensure the test loop is available; pytest-asyncio plugin is wired.
    assert asyncio.iscoroutinefunction(ask_service.answer_question)
