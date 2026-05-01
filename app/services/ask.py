"""End-to-end answer pipeline: retrieve -> rerank -> synthesise -> cite.

This is the heart of the public API. It does the following in order:
  1. hybrid retrieval (BM25 + vector) with RRF fusion -> top-30
  2. cross-encoder rerank -> top-K (default 5)
  3. build a prompt with explicit citation tokens
  4. call the LLM (Anthropic or OpenAI)
  5. parse the structured response and resolve citation_chunk_ids back to
     full citation metadata (doc title, URL, page, section)
  6. return AnswerResponse — the schema visitors see

If retrieval returns nothing we short-circuit with an explicit refusal
response (no LLM call) so we never charge for a question we can't answer.
"""

from __future__ import annotations

import time
from typing import cast

from app.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.prompts import build_prompt, parse_model_json
from app.logging import get_logger
from app.models.schemas import AnswerResponse, Citation, Confidence, Regulator
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import rerank as rerank_chunks
from app.retrieval.types import ScoredChunk

log = get_logger(__name__)

_LEGAL_DISCLAIMER = "This is regulatory information, not legal advice."


def _empty_context_response(question: str, latency_ms: int) -> AnswerResponse:
    """Honest refusal when no passages were retrieved."""
    return AnswerResponse(
        question=question,
        answer=(
            "I could not find any passages in the indexed SEBI/RBI corpus that "
            "answer this question. The corpus may not cover this topic, the "
            "question may be outside the regulatory scope, or no documents have "
            "been ingested yet."
        ),
        citations=[],
        confidence="low",
        reasoning="Retrieval returned no relevant passages above the score threshold.",
        retrieval_method="hybrid",
        model_used="(none — refused before LLM call)",
        tokens_used=0,
        latency_ms=latency_ms,
        warnings=[
            _LEGAL_DISCLAIMER,
            "no_relevant_context",
        ],
    )


def _make_snippet(text: str, max_chars: int = 220) -> str:
    snippet = " ".join(text.split())
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip() + "…"
    return snippet


def _resolve_citations(
    cited_ids: list[str],
    chunk_index: dict[str, ScoredChunk],
) -> tuple[list[Citation], list[str]]:
    """Resolve chunk_ids returned by the model into full Citation objects.

    Returns ``(citations, warnings)``. We warn (but don't fail) if the model
    cited a chunk_id that wasn't in the retrieved set — this is a sign of
    hallucination and visitors deserve to see it.
    """
    citations: list[Citation] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for cid in cited_ids:
        if cid in seen:
            continue
        seen.add(cid)
        sc = chunk_index.get(cid)
        if sc is None:
            warnings.append(f"model cited unknown chunk_id={cid}")
            continue
        c = sc.chunk
        citations.append(
            Citation(
                doc_id=c.doc_id,
                doc_title=c.doc_title,
                regulator=cast(Regulator, c.regulator),
                section=c.section_path,
                page=c.page_start,
                snippet=_make_snippet(c.text),
                url=c.source_url,
            )
        )
    return citations, warnings


def _coerce_confidence(value: object) -> Confidence:
    if isinstance(value, str) and value.lower() in {"high", "medium", "low"}:
        return cast(Confidence, value.lower())
    return "low"


async def answer_question(
    *,
    question: str,
    top_k: int,
    regulator_filter: str | None = None,
) -> AnswerResponse:
    settings = get_settings()
    started = time.perf_counter()

    # ---- retrieve ----
    fused = await hybrid_search(
        question,
        regulator_filter=regulator_filter,
        fused_top_k=settings.rerank_top_k,
    )
    if not fused:
        return _empty_context_response(
            question, latency_ms=int((time.perf_counter() - started) * 1000)
        )

    # ---- rerank ----
    ranked = await rerank_chunks(question, fused, top_k=top_k)
    if not ranked:
        return _empty_context_response(
            question, latency_ms=int((time.perf_counter() - started) * 1000)
        )

    # ---- LLM ----
    prompt = build_prompt(question, ranked)
    client = get_llm_client()
    log.info("ask.llm_call", provider=client.name, n_chunks=len(ranked))

    try:
        llm_response = await client.complete_json(
            system=prompt.system,
            user=prompt.user,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("ask.llm_failed")
        latency = int((time.perf_counter() - started) * 1000)
        return AnswerResponse(
            question=question,
            answer=(
                "The answer model was unreachable. Please retry shortly. "
                "Retrieval results are not included because the synthesis "
                "step did not run."
            ),
            citations=[],
            confidence="low",
            reasoning=f"LLM call failed: {type(e).__name__}",
            model_used="(unavailable)",
            tokens_used=0,
            latency_ms=latency,
            warnings=[_LEGAL_DISCLAIMER, "llm_unavailable"],
        )

    # ---- parse ----
    warnings: list[str] = [_LEGAL_DISCLAIMER]
    try:
        parsed = parse_model_json(llm_response.text)
    except ValueError:
        log.warning("ask.parse_failed", raw=llm_response.text[:300])
        latency = int((time.perf_counter() - started) * 1000)
        return AnswerResponse(
            question=question,
            answer=(
                "The model returned an unparseable response. Try rephrasing "
                "your question."
            ),
            citations=[],
            confidence="low",
            reasoning="Could not parse JSON from model output.",
            model_used=llm_response.model,
            tokens_used=llm_response.total_tokens,
            latency_ms=latency,
            warnings=[*warnings, "model_output_unparseable"],
        )

    answer_text = str(parsed.get("answer", "")).strip()
    cited_ids = [str(x) for x in cast(list[object], parsed.get("citation_chunk_ids", []))]
    confidence = _coerce_confidence(parsed.get("confidence"))
    reasoning = str(parsed.get("reasoning", "")).strip()
    model_warnings = [
        str(w)
        for w in cast(list[object], parsed.get("warnings", []) or [])
        if isinstance(w, (str, int, float))
    ]

    citations, citation_warnings = _resolve_citations(cited_ids, prompt.chunk_index)
    warnings.extend(citation_warnings)
    warnings.extend(model_warnings)

    if not citations and confidence != "low":
        # If the model claimed high/medium confidence but cited nothing, downgrade.
        confidence = "low"
        warnings.append("downgraded_confidence_no_citations")

    latency = int((time.perf_counter() - started) * 1000)
    return AnswerResponse(
        question=question,
        answer=answer_text,
        citations=citations,
        confidence=confidence,
        reasoning=reasoning or "(no reasoning provided)",
        model_used=llm_response.model,
        tokens_used=llm_response.total_tokens,
        latency_ms=latency,
        warnings=warnings,
    )
