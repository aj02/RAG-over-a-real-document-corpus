"""RRF fusion correctness."""

from __future__ import annotations

from app.retrieval.hybrid import reciprocal_rank_fusion
from app.retrieval.types import ChunkRecord, ScoredChunk


def _sc(chunk_id: str, score: float, source: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=ChunkRecord(
            chunk_id=chunk_id,
            doc_id="d",
            doc_title="t",
            regulator="SEBI",
            section_path=None,
            page_start=1,
            page_end=1,
            text="text",
            source_url="https://example.com",
        ),
        score=score,
        sources={source: score},
    )


def test_rrf_aggregates_two_lists() -> None:
    bm25 = [_sc("a", 10.0, "bm25"), _sc("b", 8.0, "bm25"), _sc("c", 5.0, "bm25")]
    vec = [_sc("b", 0.92, "vector"), _sc("d", 0.90, "vector"), _sc("a", 0.80, "vector")]
    fused = reciprocal_rank_fusion([bm25, vec], k=60)

    ids = [s.chunk.chunk_id for s in fused]
    # Items present in both lists should rank above singletons.
    assert ids.index("a") < ids.index("c")
    assert ids.index("b") < ids.index("d")


def test_rrf_score_is_sum_of_reciprocal_ranks() -> None:
    bm25 = [_sc("a", 10.0, "bm25"), _sc("b", 8.0, "bm25")]
    vec = [_sc("b", 0.92, "vector"), _sc("a", 0.80, "vector")]
    fused = reciprocal_rank_fusion([bm25, vec], k=60)
    score_map = {s.chunk.chunk_id: s.score for s in fused}

    expected_a = 1 / 61 + 1 / 62  # bm25 rank1 + vec rank2
    expected_b = 1 / 62 + 1 / 61
    assert abs(score_map["a"] - expected_a) < 1e-9
    assert abs(score_map["b"] - expected_b) < 1e-9


def test_rrf_preserves_per_stage_sources() -> None:
    bm25 = [_sc("a", 10.0, "bm25")]
    vec = [_sc("a", 0.9, "vector")]
    fused = reciprocal_rank_fusion([bm25, vec], k=60)
    assert "bm25" in fused[0].sources
    assert "vector" in fused[0].sources


def test_rrf_handles_empty_inputs() -> None:
    assert reciprocal_rank_fusion([[], []], k=60) == []
    out = reciprocal_rank_fusion([[_sc("a", 1.0, "bm25")], []], k=60)
    assert len(out) == 1 and out[0].chunk.chunk_id == "a"


def test_rrf_singleton_dedupes_within_a_list() -> None:
    bm25 = [_sc("a", 10.0, "bm25")]
    vec = [_sc("a", 0.9, "vector")]
    fused = reciprocal_rank_fusion([bm25, vec], k=60)
    assert len(fused) == 1
