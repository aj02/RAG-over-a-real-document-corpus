"""Citation extraction & prompt formatting."""

from __future__ import annotations

from app.llm.prompts import build_prompt, format_passages, parse_model_json
from app.retrieval.types import ChunkRecord, ScoredChunk


def _chunk(cid: str, page: int = 7, section: str | None = "3.1 Title") -> ScoredChunk:
    return ScoredChunk(
        chunk=ChunkRecord(
            chunk_id=cid,
            doc_id="SEBI-MC-MF-2024",
            doc_title="SEBI Master Circular for Mutual Funds",
            regulator="SEBI",
            section_path=section,
            page_start=page,
            page_end=page,
            text="An asset management company shall ensure ...",
            source_url="https://www.sebi.gov.in/x.html",
        ),
        score=0.91,
        sources={"rerank": 0.91},
    )


def test_format_passages_emits_citation_tokens() -> None:
    chunks = [_chunk("c1", 7), _chunk("c2", 9, section=None)]
    out = format_passages(chunks)
    assert "doc_id=SEBI-MC-MF-2024" in out
    assert "page=7" in out
    assert "chunk_id=c1" in out
    # No section_path key for chunk without section
    assert out.count('section="3.1 Title"') == 1


def test_format_passages_truncates_long_text() -> None:
    chunk = _chunk("c1")
    chunk.chunk.text = "x" * 5000
    out = format_passages([chunk], max_passage_chars=200)
    # The truncation marker must appear after exactly max_passage_chars.
    assert "…" in out


def test_build_prompt_indexes_chunks() -> None:
    chunks = [_chunk("c1"), _chunk("c2")]
    prompt = build_prompt("What is the role of an AMC?", chunks)
    assert "QUESTION: What is the role of an AMC?" in prompt.user
    assert set(prompt.chunk_index) == {"c1", "c2"}


def test_parse_model_json_handles_plain_object() -> None:
    out = parse_model_json('{"answer": "x", "citation_chunk_ids": ["c1"]}')
    assert out["answer"] == "x"


def test_parse_model_json_handles_fenced_block() -> None:
    raw = '```json\n{"answer": "x", "citation_chunk_ids": []}\n```'
    out = parse_model_json(raw)
    assert out["answer"] == "x"


def test_parse_model_json_extracts_object_from_prose() -> None:
    raw = 'Sure! Here is the JSON: {"answer": "x", "citation_chunk_ids": []} thanks!'
    out = parse_model_json(raw)
    assert out["answer"] == "x"


def test_parse_model_json_raises_on_garbage() -> None:
    try:
        parse_model_json("not json at all")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-JSON output")
