import Link from "next/link";
import { Github, Linkedin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { loadCorpusStats, loadLatestEvalRun } from "@/lib/corpus-stats";

export const dynamic = "force-static";

const REPO_URL = "https://github.com/your-handle/regrag";
const LINKEDIN_URL = "https://www.linkedin.com/in/your-handle/";

const ARCH_DIAGRAM = `┌────────────┐    ┌──────────────┐
│  question  │ ─▶ │ embed_query  │ ─┐
└────────────┘    └──────────────┘  │
       │                            ▼
       │                ┌──────────────────────┐
       │     ┌────────▶ │ pgvector cosine k=50 │
       │     │          └──────────┬───────────┘
       │     │                     │
       └─────┼──────────┐          │
             │          ▼          │
             │  ┌──────────────────┴───────┐
             │  │ BM25 (rank_bm25) k=50    │
             │  └──────────────┬───────────┘
             │                 │
             │      ┌──────────▼───────────┐
             │      │ Reciprocal Rank Fusion│
             │      │   k=60   →  top-30   │
             │      └──────────┬───────────┘
             │                 ▼
             │      ┌──────────────────────┐
             │      │ Cross-encoder rerank │
             │      │   →  top-K=5         │
             │      └──────────┬───────────┘
             │                 ▼
             │      ┌──────────────────────┐
             └────▶ │   LLM + citations    │
                    └──────────────────────┘`;

function fmt(value: number | null, digits = 4): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function fmtMs(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round(value)} ms`;
}

export default async function AboutPage() {
  const [stats, evalRun] = await Promise.all([
    loadCorpusStats(),
    loadLatestEvalRun(),
  ]);

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:py-14">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          About regrag
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          A research-grade RAG system over publicly-available SEBI circulars
          and RBI master directions.
        </p>
      </header>

      <article className="mt-8 space-y-10 text-sm leading-relaxed text-foreground">
        <section className="space-y-3">
          <h2 className="text-base font-semibold">What it does</h2>
          <p className="text-muted-foreground">
            You ask a natural-language question about Indian financial
            regulation. regrag retrieves the most relevant passages from its
            indexed corpus, hands them to an LLM with strict citation
            instructions, and returns an answer that points back to specific
            documents and pages. If the corpus does not actually contain the
            answer, the system is built to refuse rather than guess.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Why fintech RAG is hard</h2>
          <ul className="space-y-2 pl-5 text-muted-foreground [&>li]:list-disc">
            <li>
              <strong className="text-foreground">Cross-references.</strong>{" "}
              A clause in a master circular often points at a regulation
              elsewhere; the chunk that <em>contains</em> the answer often
              doesn&apos;t <em>describe</em> it.
            </li>
            <li>
              <strong className="text-foreground">Defined terms.</strong>{" "}
              &quot;Customer&quot;, &quot;AIF&quot;, &quot;PPI&quot; — each
              has a precise regulatory definition that can change between
              documents. Recall depends on the right one.
            </li>
            <li>
              <strong className="text-foreground">Amendments.</strong>{" "}
              Master circulars supersede earlier circulars; some clauses get
              amended out from under you. We bias toward the latest master
              circular and surface stale-context warnings.
            </li>
            <li>
              <strong className="text-foreground">Numbered hierarchy.</strong>{" "}
              Naive character-window chunking severs &quot;3.1.1&quot; from
              its clause. The chunker treats numbered headings as hard
              boundaries and stamps every chunk with its section path.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Architecture</h2>
          <p className="text-muted-foreground">
            BM25 and dense retrieval run in parallel against the same chunk
            corpus stored in Postgres + pgvector. Their rankings are merged
            with Reciprocal Rank Fusion, the top-30 are reranked with a
            cross-encoder, and the top-5 go to the LLM along with explicit
            citation tokens. The LLM is constrained to cite only the chunks
            it was given; cited IDs are resolved server-side and any
            unmatched IDs surface as warnings.
          </p>
          <pre className="overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-4 text-[11px] leading-relaxed text-muted-foreground">
            {ARCH_DIAGRAM}
          </pre>
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Corpus</h2>
          <Card>
            <CardContent className="grid grid-cols-2 gap-4 pt-6 sm:grid-cols-4">
              <Stat label="Documents" value={stats.total.toString()} />
              <Stat label="SEBI" value={stats.bySebi.toString()} />
              <Stat label="RBI" value={stats.byRbi.toString()} />
              <Stat label="Categories" value={stats.categories.toString()} />
            </CardContent>
          </Card>
          <p className="text-xs text-muted-foreground">
            PDFs are not committed (copyright). The manifest at{" "}
            <code className="rounded bg-muted px-1 font-mono text-[11px]">
              data/corpus_manifest.json
            </code>{" "}
            plus{" "}
            <code className="rounded bg-muted px-1 font-mono text-[11px]">
              scripts/download_corpus.py
            </code>{" "}
            reproduces the corpus.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Evaluation</h2>
          {evalRun ? (
            <>
              <p className="text-xs text-muted-foreground">
                Latest run · {new Date(evalRun.startedAt).toLocaleString()}
                {" · "}
                {evalRun.nItems} items
                {evalRun.nErrors > 0 && ` · ${evalRun.nErrors} errors`}
              </p>
              <div className="overflow-hidden rounded-lg border border-border/60">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left">metric</th>
                      <th className="px-4 py-2 text-right">value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    <Row label="recall@1" value={fmt(evalRun.recallAt1)} />
                    <Row label="recall@3" value={fmt(evalRun.recallAt3)} />
                    <Row label="recall@5" value={fmt(evalRun.recallAt5)} />
                    <Row label="MRR" value={fmt(evalRun.mrr)} />
                    <Row
                      label="citation_in_retrieved"
                      value={fmt(evalRun.citationInRetrieved)}
                    />
                    <Row
                      label="faithfulness"
                      value={fmt(evalRun.faithfulness)}
                    />
                    <Row
                      label="completeness"
                      value={fmt(evalRun.completeness)}
                    />
                    <Row
                      label="refusal_correctness"
                      value={fmt(evalRun.refusal)}
                    />
                    <Row
                      label="latency p50"
                      value={fmtMs(evalRun.latencyP50Ms)}
                    />
                    <Row
                      label="latency p95"
                      value={fmtMs(evalRun.latencyP95Ms)}
                    />
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border/70 bg-muted/30 px-4 py-5 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">
                No eval run committed yet.
              </p>
              <p className="mt-2">
                The harness in{" "}
                <code className="rounded bg-muted px-1 font-mono text-[11px]">
                  eval/run_eval.py
                </code>{" "}
                computes recall@k, MRR, citation correctness, latency
                percentiles, and LLM-as-judge faithfulness/completeness/refusal
                scores against the 40-item set in{" "}
                <code className="rounded bg-muted px-1 font-mono text-[11px]">
                  eval/eval_set.json
                </code>
                . Run{" "}
                <code className="rounded bg-muted px-1 font-mono text-[11px]">
                  python -m eval.run_eval
                </code>{" "}
                after ingestion to populate this table.
              </p>
            </div>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Limitations</h2>
          <ul className="space-y-1.5 pl-5 text-muted-foreground [&>li]:list-disc">
            <li>Not legal advice. Retrieve and summarise only.</li>
            <li>
              Tabular data inside PDFs is flattened — fee schedules and
              limits may need a structured loader to be fully reliable.
            </li>
            <li>
              Supersession isn&apos;t modelled as a graph; amendments
              surface as parallel results.
            </li>
            <li>
              Local cross-encoder reranking adds ~200 ms on CPU. Switch to
              Cohere or GPU if p95 is too high.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-base font-semibold">Author</h2>
          <p className="text-muted-foreground">
            Built by Ajay Tambe as a public showcase of production-grade RAG
            engineering. The code, manifest, eval set, and harness are all
            on GitHub.
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 font-medium text-foreground hover:bg-accent"
            >
              <Github className="h-4 w-4" />
              Repository
            </Link>
            <Link
              href={LINKEDIN_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 font-medium text-foreground hover:bg-accent"
            >
              <Linkedin className="h-4 w-4" />
              LinkedIn
            </Link>
          </div>
        </section>
      </article>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      <div className="mt-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
        {label}
      </td>
      <td className="px-4 py-2 text-right font-mono text-xs">{value}</td>
    </tr>
  );
}
