"use client";

import { useState } from "react";
import { Search as SearchIcon, ToggleLeft, ToggleRight } from "lucide-react";
import { AskForm } from "@/components/ask-form";
import { ChunkRow } from "@/components/chunk-row";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { RegulatorChoice } from "@/components/regulator-filter";
import type { TopKValue } from "@/components/top-k-selector";
import { useSearch } from "@/lib/queries";
import { cn, formatLatency } from "@/lib/utils";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [regulator, setRegulator] = useState<RegulatorChoice>("ALL");
  const [topK, setTopK] = useState<TopKValue>(10);
  const [rerank, setRerank] = useState(true);
  const search = useSearch();

  const submit = () => {
    const q = query.trim();
    if (q.length < 1) return;
    search.mutate({
      query: q,
      top_k: topK,
      regulator: regulator === "ALL" ? null : regulator,
      rerank,
    });
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-12">
      <Alert variant="info" className="mb-6">
        <SearchIcon className="h-4 w-4" />
        <AlertTitle>Retrieval debug view</AlertTitle>
        <AlertDescription>
          This view runs the retrieval pipeline (hybrid BM25 + vector → RRF →
          rerank) but skips the LLM generation step. Use it to inspect which
          chunks are being ranked and why.
        </AlertDescription>
      </Alert>

      <section className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Search</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Inspect raw retrieval output without generation.
        </p>
      </section>

      <section className="mb-3">
        <AskForm
          question={query}
          onQuestionChange={setQuery}
          regulator={regulator}
          onRegulatorChange={setRegulator}
          topK={topK}
          onTopKChange={setTopK}
          isPending={search.isPending}
          onSubmit={submit}
        />
      </section>

      <div className="mb-8 flex items-center justify-end">
        <button
          type="button"
          onClick={() => setRerank((v) => !v)}
          disabled={search.isPending}
          className={cn(
            "inline-flex items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1 text-xs font-medium transition-colors",
            rerank ? "text-foreground" : "text-muted-foreground",
            search.isPending && "cursor-not-allowed opacity-60",
          )}
          aria-pressed={rerank}
          title="Toggle cross-encoder rerank"
        >
          {rerank ? (
            <ToggleRight className="h-3.5 w-3.5 text-primary" />
          ) : (
            <ToggleLeft className="h-3.5 w-3.5" />
          )}
          rerank: {rerank ? "on" : "off"}
        </button>
      </div>

      {search.isPending && (
        <ul className="space-y-3" role="status" aria-label="Loading results">
          {[0, 1, 2, 3].map((i) => (
            <li
              key={i}
              className="space-y-2 rounded-lg border border-border/60 bg-card p-4"
            >
              <div className="flex gap-2">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
              </div>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </li>
          ))}
        </ul>
      )}

      {search.isError && (
        <ErrorState error={search.error} onRetry={submit} />
      )}

      {search.data && !search.isPending && (
        <>
          <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {search.data.chunks.length} chunks ·{" "}
              <span className="font-mono">{search.data.retrieval_method}</span>
            </span>
            <span className="font-mono">
              {formatLatency(search.data.latency_ms)}
            </span>
          </div>
          {search.data.chunks.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
              No chunks matched. The corpus may not cover this query, or the
              database has not been ingested yet.
            </div>
          ) : (
            <ul className="space-y-3">
              {search.data.chunks.map((c, i) => (
                <li key={c.chunk_id}>
                  <ChunkRow chunk={c} rank={i + 1} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
