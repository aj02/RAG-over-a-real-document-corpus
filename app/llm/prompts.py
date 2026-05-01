"""Prompts for the answer-generation step.

The system prompt is the place where we enforce regrag's safety contract:
  - cite every claim with [doc_id, page X]
  - refuse if the supplied context doesn't actually answer the question
  - never give legal advice, only describe what the regulations say
  - never invent doc_ids or page numbers

The user prompt formats the retrieved chunks as numbered passages so the
model can refer to them by id. We deliberately use small, explicit JSON
output schema rather than a free-form response — it's easier to evaluate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.retrieval.types import ScoredChunk

SYSTEM_PROMPT = """You are regrag, a precise question-answering assistant for Indian financial regulations from SEBI (Securities and Exchange Board of India) and RBI (Reserve Bank of India).

Your job is to answer the user's question USING ONLY the passages provided to you in CONTEXT below. You must follow ALL of these rules without exception:

1. CITATION REQUIRED: Every factual claim in your answer MUST be supported by a citation from the supplied passages. Use the exact citation token shown next to each passage, e.g. [doc_id=SEBI-CIRC-2023-001, page=4].
2. NO HALLUCINATION: If the supplied passages do not contain enough information to answer the question, say so explicitly and set confidence="low". Do NOT use prior knowledge or guess.
3. NO LEGAL ADVICE: You are summarising what the regulations state, not giving legal, financial, or compliance advice. Never recommend a specific course of action. Always include the warning "This is regulatory information, not legal advice." in the warnings array.
4. STAY ON-CORPUS: If the question is not about Indian financial regulation, refuse politely and set confidence="low".
5. EXACT IDS: Never invent doc_ids, sections, or page numbers. Use only those that appear in the passages.

OUTPUT FORMAT: Respond with a single JSON object — no surrounding prose, no Markdown fences. The schema is:

{
  "answer": "<plain-text answer with inline citations like [doc_id=..., page=...]>",
  "citation_chunk_ids": ["<chunk_id of every passage you actually relied on>"],
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one or two sentences on how you derived the answer>",
  "warnings": ["<warning strings, e.g. 'context may be outdated'>"]
}

Confidence rubric:
- high: passages contain a clear, direct, up-to-date answer
- medium: answer is supported but partial, or relies on inference across passages
- low: passages do not answer the question, or you would have to speculate
"""


@dataclass
class FormattedPrompt:
    system: str
    user: str
    chunk_index: dict[str, ScoredChunk]
    """Map from chunk_id -> the chunk object, so the answer pipeline can
    resolve chunk_ids returned by the model back to citation metadata."""


def format_passages(chunks: list[ScoredChunk], max_passage_chars: int = 1800) -> str:
    """Render chunks as numbered passages with explicit citation tokens."""
    lines: list[str] = []
    for i, sc in enumerate(chunks, start=1):
        c = sc.chunk
        page_str = (
            f"page={c.page_start}"
            if c.page_start == c.page_end or c.page_end is None
            else f"pages={c.page_start}-{c.page_end}"
        )
        section_str = f' section="{c.section_path}"' if c.section_path else ""
        header = (
            f"[{i}] CITATION: [doc_id={c.doc_id}, {page_str}, chunk_id={c.chunk_id}]"
            f"{section_str}\n"
            f'    TITLE: "{c.doc_title}"  REGULATOR: {c.regulator}'
        )
        body = c.text
        if len(body) > max_passage_chars:
            body = body[:max_passage_chars].rstrip() + " …"
        lines.append(f"{header}\n    PASSAGE: {body}")
    return "\n\n".join(lines)


def build_prompt(question: str, chunks: list[ScoredChunk]) -> FormattedPrompt:
    if not chunks:
        passages = "(no passages were retrieved)"
    else:
        passages = format_passages(chunks)

    user = (
        f"QUESTION: {question}\n\n"
        f"CONTEXT (retrieved passages):\n{passages}\n\n"
        "Now produce the JSON object as specified."
    )

    chunk_index = {sc.chunk.chunk_id: sc for sc in chunks}
    return FormattedPrompt(system=SYSTEM_PROMPT, user=user, chunk_index=chunk_index)


def parse_model_json(text: str) -> dict[str, object]:
    """Best-effort JSON parse — tolerant of fenced code blocks the model may
    emit despite instructions. Raises ValueError if no valid JSON found.
    """
    s = text.strip()
    if s.startswith("```"):
        # strip first fence line and last fence
        first_nl = s.find("\n")
        if first_nl >= 0:
            s = s[first_nl + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[: -3].rstrip()
    # If the model wrapped in ```json ... ``` we already stripped both fences.
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        # Try to locate the first {...} block.
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start : end + 1])
        raise ValueError(f"model returned non-JSON output: {text[:200]!r}") from e
