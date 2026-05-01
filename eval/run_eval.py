"""End-to-end eval runner.

For each item in ``eval/eval_set.json``:
  - call /search to get retrieved chunks; record retrieval metrics
    (recall@k for the gold doc_ids, MRR over the gold-doc rank)
  - call /ask to get the synthesized answer; record:
      * latency_ms, tokens_used
      * citation correctness: every cited doc_id is from the retrieved set
      * LLM-as-judge scores (faithfulness, completeness, refusal_correctness)

Outputs a markdown report to ``eval/results/run_<UTC-timestamp>.md`` with
per-question detail and aggregate scores. Also writes a JSON sidecar so
results are machine-readable for diffing across runs.

Usage:
    python -m eval.run_eval                         # full set against http://localhost:8000
    python -m eval.run_eval --base-url http://api:8000
    python -m eval.run_eval --no-judge              # skip LLM-as-judge
    python -m eval.run_eval --limit 5               # smoke run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.logging import configure_logging, get_logger

log = get_logger("eval")

DEFAULT_TOP_K = 5
RECALL_KS = (1, 3, 5)


@dataclass
class PerItemResult:
    id: str
    question: str
    expected: str  # "answer" | "refuse"
    tags: list[str]
    gold_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    retrieval_recall_at_k: dict[int, float]
    retrieval_mrr: float
    answer: str
    citations: list[dict[str, object]]
    confidence: str
    latency_ms: int
    tokens_used: int
    warnings: list[str]
    citation_in_retrieved: float
    judge_faithfulness: float | None = None
    judge_completeness: float | None = None
    judge_refusal: float | None = None
    judge_reasoning: str | None = None
    error: str | None = None


@dataclass
class RunSummary:
    started_at: str
    finished_at: str
    n_items: int
    n_errors: int
    base_url: str
    aggregate_recall_at_k: dict[int, float] = field(default_factory=dict)
    aggregate_mrr: float = 0.0
    aggregate_citation_in_retrieved: float = 0.0
    aggregate_faithfulness: float | None = None
    aggregate_completeness: float | None = None
    aggregate_refusal: float | None = None
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    items: list[PerItemResult] = field(default_factory=list)


def _recall_at_k(gold: list[str], retrieved: list[str], k: int) -> float:
    if not gold:
        # For refusal items there is no gold; treat as N/A by returning 1.0
        # only when retrieval is empty, else 0.0. We exclude these from agg.
        return 1.0 if not retrieved[:k] else 0.0
    top_k = retrieved[:k]
    hits = sum(1 for g in gold if g in top_k)
    return hits / len(gold)


def _mrr(gold: list[str], retrieved: list[str]) -> float:
    if not gold:
        return 0.0
    ranks: list[float] = []
    for g in gold:
        try:
            r = retrieved.index(g) + 1
            ranks.append(1.0 / r)
        except ValueError:
            ranks.append(0.0)
    return sum(ranks) / len(gold)


def _citation_in_retrieved(citations: list[dict[str, object]], retrieved: list[str]) -> float:
    if not citations:
        return 1.0  # nothing cited → vacuously valid; refusals fall here
    cited = [str(c.get("doc_id", "")) for c in citations]
    matches = sum(1 for d in cited if d in retrieved)
    return matches / len(cited)


async def _call_search(
    client: httpx.AsyncClient, base_url: str, q: str, top_k: int
) -> tuple[list[str], list[dict[str, object]]]:
    r = await client.get(
        f"{base_url}/search",
        params={"q": q, "top_k": top_k, "rerank": "true"},
        timeout=120.0,
    )
    r.raise_for_status()
    data = r.json()
    chunks = data.get("chunks", [])
    return [str(c["doc_id"]) for c in chunks], chunks


async def _call_ask(
    client: httpx.AsyncClient, base_url: str, q: str, top_k: int
) -> dict[str, object]:
    r = await client.post(
        f"{base_url}/ask",
        json={"question": q, "top_k": top_k, "regulator_filter": None},
        timeout=180.0,
    )
    r.raise_for_status()
    return r.json()


async def _evaluate_one(
    client: httpx.AsyncClient,
    base_url: str,
    item: dict[str, object],
    *,
    top_k: int,
    use_judge: bool,
) -> PerItemResult:
    qid = str(item["id"])
    question = str(item["question"])
    expected = str(item["expected"])
    gold = [str(g) for g in item.get("gold_doc_ids") or []]
    tags = [str(t) for t in item.get("tags") or []]
    ref_notes = str(item.get("reference_notes", ""))

    log.info("eval.start_item", id=qid)
    started = time.perf_counter()

    try:
        retrieved_doc_ids, _retrieved_chunks = await _call_search(
            client, base_url, question, top_k=max(top_k, max(RECALL_KS))
        )
        ans = await _call_ask(client, base_url, question, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        log.exception("eval.item_failed", id=qid)
        return PerItemResult(
            id=qid,
            question=question,
            expected=expected,
            tags=tags,
            gold_doc_ids=gold,
            retrieved_doc_ids=[],
            retrieval_recall_at_k={k: 0.0 for k in RECALL_KS},
            retrieval_mrr=0.0,
            answer="",
            citations=[],
            confidence="low",
            latency_ms=int((time.perf_counter() - started) * 1000),
            tokens_used=0,
            warnings=[],
            citation_in_retrieved=0.0,
            error=f"{type(e).__name__}: {e}",
        )

    citations = list(ans.get("citations") or [])
    retrieval_recall = {k: _recall_at_k(gold, retrieved_doc_ids, k) for k in RECALL_KS}
    mrr = _mrr(gold, retrieved_doc_ids)
    cit_in_ret = _citation_in_retrieved(citations, retrieved_doc_ids)

    judge_f = judge_c = judge_r = None
    judge_reasoning = None
    if use_judge:
        try:
            from eval.judge import judge_answer

            scores = await judge_answer(
                question=question,
                reference_notes=ref_notes,
                expected=expected,
                answer=str(ans.get("answer", "")),
                citations=citations,
            )
            judge_f = scores.faithfulness
            judge_c = scores.completeness
            judge_r = scores.refusal_correctness
            judge_reasoning = scores.reasoning
        except Exception as e:  # noqa: BLE001
            log.warning("eval.judge_failed", id=qid, error=str(e))

    return PerItemResult(
        id=qid,
        question=question,
        expected=expected,
        tags=tags,
        gold_doc_ids=gold,
        retrieved_doc_ids=retrieved_doc_ids,
        retrieval_recall_at_k=retrieval_recall,
        retrieval_mrr=mrr,
        answer=str(ans.get("answer", "")),
        citations=citations,
        confidence=str(ans.get("confidence", "low")),
        latency_ms=int(ans.get("latency_ms", 0)),
        tokens_used=int(ans.get("tokens_used", 0)),
        warnings=[str(w) for w in ans.get("warnings") or []],
        citation_in_retrieved=cit_in_ret,
        judge_faithfulness=judge_f,
        judge_completeness=judge_c,
        judge_refusal=judge_r,
        judge_reasoning=judge_reasoning,
    )


def _aggregate(items: list[PerItemResult]) -> dict[str, object]:
    answer_items = [i for i in items if i.expected == "answer" and i.error is None]
    out: dict[str, object] = {}

    # Recall is only meaningful on items that have gold_doc_ids.
    for k in RECALL_KS:
        scores = [i.retrieval_recall_at_k[k] for i in answer_items if i.gold_doc_ids]
        out[f"recall@{k}"] = round(statistics.mean(scores), 4) if scores else 0.0

    mrrs = [i.retrieval_mrr for i in answer_items if i.gold_doc_ids]
    out["mrr"] = round(statistics.mean(mrrs), 4) if mrrs else 0.0

    cit = [i.citation_in_retrieved for i in items if i.error is None]
    out["citation_in_retrieved"] = round(statistics.mean(cit), 4) if cit else 0.0

    judges_f = [i.judge_faithfulness for i in items if i.judge_faithfulness is not None]
    judges_c = [i.judge_completeness for i in items if i.judge_completeness is not None]
    judges_r = [i.judge_refusal for i in items if i.judge_refusal is not None]
    out["faithfulness"] = (
        round(statistics.mean(judges_f), 4) if judges_f else None
    )
    out["completeness"] = (
        round(statistics.mean(judges_c), 4) if judges_c else None
    )
    out["refusal_correctness"] = (
        round(statistics.mean(judges_r), 4) if judges_r else None
    )

    latencies = [i.latency_ms for i in items if i.error is None]
    if latencies:
        sorted_lat = sorted(latencies)
        out["latency_p50_ms"] = sorted_lat[len(sorted_lat) // 2]
        out["latency_p95_ms"] = sorted_lat[max(0, int(len(sorted_lat) * 0.95) - 1)]
    return out


def _render_markdown(summary: RunSummary, agg: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append(f"# regrag eval run — {summary.started_at}")
    lines.append("")
    lines.append(f"- base url: `{summary.base_url}`")
    lines.append(f"- items: {summary.n_items}  (errors: {summary.n_errors})")
    lines.append(f"- finished: {summary.finished_at}")
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("| --- | --- |")
    for k, v in agg.items():
        if v is None:
            v_str = "n/a"
        elif isinstance(v, float):
            v_str = f"{v:.4f}"
        else:
            v_str = str(v)
        lines.append(f"| {k} | {v_str} |")
    lines.append("")
    lines.append("## Per-item results")
    lines.append("")
    lines.append(
        "| id | tags | expected | conf | r@5 | mrr | faith | comp | refusal | "
        "lat ms | tokens |"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    for i in summary.items:
        lines.append(
            "| {id} | {tags} | {exp} | {conf} | {r5:.2f} | {mrr:.2f} | "
            "{f} | {c} | {r} | {lat} | {tok} |".format(
                id=i.id,
                tags=", ".join(i.tags),
                exp=i.expected,
                conf=i.confidence,
                r5=i.retrieval_recall_at_k.get(5, 0.0),
                mrr=i.retrieval_mrr,
                f=("-" if i.judge_faithfulness is None else f"{i.judge_faithfulness:.2f}"),
                c=("-" if i.judge_completeness is None else f"{i.judge_completeness:.2f}"),
                r=("-" if i.judge_refusal is None else f"{i.judge_refusal:.2f}"),
                lat=i.latency_ms,
                tok=i.tokens_used,
            )
        )
    lines.append("")
    lines.append("## Detail")
    for i in summary.items:
        lines.append("")
        lines.append(f"### {i.id} — {i.question}")
        if i.error:
            lines.append(f"**error**: `{i.error}`")
            continue
        lines.append(f"- expected: **{i.expected}**, tags: {', '.join(i.tags)}")
        lines.append(f"- gold: `{i.gold_doc_ids}`")
        lines.append(f"- retrieved (top): `{i.retrieved_doc_ids[:5]}`")
        lines.append(f"- confidence: **{i.confidence}**, warnings: `{i.warnings}`")
        lines.append(f"- answer:")
        lines.append(f"  > {i.answer.strip().replace(chr(10), ' ')[:1000]}")
        if i.citations:
            lines.append("- citations:")
            for c in i.citations:
                lines.append(
                    f"    - `{c.get('doc_id')}` p.{c.get('page')} — "
                    f"{c.get('section') or ''}"
                )
        if i.judge_reasoning:
            lines.append(f"- judge: {i.judge_reasoning}")
    return "\n".join(lines)


async def run_eval(
    *,
    base_url: str,
    eval_set_path: Path,
    out_dir: Path,
    top_k: int,
    use_judge: bool,
    limit: int | None,
    concurrency: int,
) -> Path:
    configure_logging()
    eval_data = json.loads(eval_set_path.read_text(encoding="utf-8"))
    items: list[dict[str, object]] = list(eval_data["items"])
    if limit:
        items = items[:limit]

    started = datetime.now(UTC)
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        async def _bound(item: dict[str, object]) -> PerItemResult:
            async with sem:
                return await _evaluate_one(
                    client, base_url, item, top_k=top_k, use_judge=use_judge
                )

        results = await asyncio.gather(*[_bound(i) for i in items])

    finished = datetime.now(UTC)
    n_errors = sum(1 for r in results if r.error)

    summary = RunSummary(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        n_items=len(results),
        n_errors=n_errors,
        base_url=base_url,
        items=results,
    )
    agg = _aggregate(results)
    summary.aggregate_recall_at_k = {
        k: float(agg.get(f"recall@{k}", 0.0)) for k in RECALL_KS  # type: ignore[arg-type]
    }
    summary.aggregate_mrr = float(agg.get("mrr", 0.0))  # type: ignore[arg-type]
    summary.aggregate_citation_in_retrieved = float(  # type: ignore[arg-type]
        agg.get("citation_in_retrieved", 0.0)
    )
    summary.aggregate_faithfulness = (
        float(agg["faithfulness"]) if agg.get("faithfulness") is not None else None  # type: ignore[arg-type]
    )
    summary.aggregate_completeness = (
        float(agg["completeness"]) if agg.get("completeness") is not None else None  # type: ignore[arg-type]
    )
    summary.aggregate_refusal = (
        float(agg["refusal_correctness"])  # type: ignore[arg-type]
        if agg.get("refusal_correctness") is not None
        else None
    )
    summary.latency_p50_ms = float(agg.get("latency_p50_ms", 0))  # type: ignore[arg-type]
    summary.latency_p95_ms = float(agg.get("latency_p95_ms", 0))  # type: ignore[arg-type]

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    md_path = out_dir / f"run_{stamp}.md"
    json_path = out_dir / f"run_{stamp}.json"

    md_path.write_text(_render_markdown(summary, agg), encoding="utf-8")
    json_path.write_text(
        json.dumps(asdict(summary), indent=2, default=str), encoding="utf-8"
    )

    log.info("eval.run_done", md=str(md_path), n=len(results), errors=n_errors)
    return md_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--eval-set", default="eval/eval_set.json")
    p.add_argument("--out-dir", default="eval/results")
    p.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="how many eval items to run in parallel",
    )
    args = p.parse_args()
    md = asyncio.run(
        run_eval(
            base_url=args.base_url,
            eval_set_path=Path(args.eval_set),
            out_dir=Path(args.out_dir),
            top_k=args.top_k,
            use_judge=not args.no_judge,
            limit=args.limit,
            concurrency=args.concurrency,
        )
    )
    print(f"\nwrote: {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
