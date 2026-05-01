"""LLM-as-judge for answer quality.

We use a structured rubric and ask the configured LLM (the same one used for
generation, which is fine because we're not gaming benchmarks — we're sanity
checking on a real corpus). The judge sees:
  - the question
  - the reference notes (what a correct answer should mention)
  - the system's answer + citations
  - the expected behaviour (answer | refuse)

It returns three sub-scores in [0, 1]: faithfulness, completeness, refusal.
We log raw scores and the judge's free-text reasoning for traceability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from app.llm.factory import get_llm_client
from app.llm.prompts import parse_model_json
from app.logging import get_logger

log = get_logger(__name__)

JUDGE_SYSTEM = """You are an evaluator for a regulatory-RAG system. You will read a question, a reference rubric, and the system's answer with citations. Your job is to assign three numeric sub-scores in [0.0, 1.0]:

1. faithfulness: Does the answer ONLY claim things that the cited passages support? 1.0 = every claim is grounded; 0.0 = mostly unsupported.
2. completeness: Does the answer cover the key points implied by the rubric/reference? 1.0 = covers all material points; 0.0 = misses everything.
3. refusal_correctness: If expected_behaviour is "refuse", does the system actually refuse and explain why? If expected_behaviour is "answer", does the system actually attempt an answer? 1.0 = correct behaviour; 0.0 = wrong behaviour.

Be strict. Penalise:
- Claims that go beyond the cited passages
- Generic non-answers when a real answer is expected
- Missing the legal-disclaimer warning
- Confidently answering questions the system should refuse

Return strictly this JSON object — no surrounding prose:
{
  "faithfulness": <float in [0,1]>,
  "completeness": <float in [0,1]>,
  "refusal_correctness": <float in [0,1]>,
  "reasoning": "<2-3 sentences>"
}
"""


@dataclass
class JudgeScores:
    faithfulness: float
    completeness: float
    refusal_correctness: float
    reasoning: str

    @property
    def aggregate(self) -> float:
        return round(
            (self.faithfulness + self.completeness + self.refusal_correctness) / 3.0,
            4,
        )


def _coerce(v: object, default: float = 0.0) -> float:
    try:
        x = float(cast(float, v))
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, x))


async def judge_answer(
    *,
    question: str,
    reference_notes: str,
    expected: str,
    answer: str,
    citations: list[dict[str, object]],
) -> JudgeScores:
    citations_text = json.dumps(citations, indent=2, default=str)
    user = (
        f"QUESTION: {question}\n\n"
        f"EXPECTED BEHAVIOUR: {expected}\n\n"
        f"REFERENCE NOTES (what a correct answer should mention):\n{reference_notes}\n\n"
        f"SYSTEM ANSWER:\n{answer}\n\n"
        f"SYSTEM CITATIONS:\n{citations_text}\n\n"
        "Now produce the JSON object as specified."
    )
    client = get_llm_client()
    resp = await client.complete_json(
        system=JUDGE_SYSTEM,
        user=user,
        max_tokens=512,
        temperature=0.0,
    )
    try:
        parsed = parse_model_json(resp.text)
    except ValueError:
        log.warning("judge.parse_failed", raw=resp.text[:200])
        return JudgeScores(0.0, 0.0, 0.0, "judge output unparseable")
    return JudgeScores(
        faithfulness=_coerce(parsed.get("faithfulness")),
        completeness=_coerce(parsed.get("completeness")),
        refusal_correctness=_coerce(parsed.get("refusal_correctness")),
        reasoning=str(parsed.get("reasoning", "")),
    )
