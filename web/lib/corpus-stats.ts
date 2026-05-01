/**
 * Server-side helpers that read the regrag manifest and any committed eval
 * results from disk at build time. These are *not* shipped to the client —
 * the values are interpolated into the static /about page during build.
 */

import { promises as fs } from "node:fs";
import path from "node:path";

const REPO_ROOT = path.join(process.cwd(), "..");

interface ManifestEntry {
  doc_id: string;
  title: string;
  regulator: "SEBI" | "RBI";
  category: string;
}

export interface CorpusStats {
  total: number;
  bySebi: number;
  byRbi: number;
  categories: number;
  manifestDescription: string | null;
}

export async function loadCorpusStats(): Promise<CorpusStats> {
  const manifestPath = path.join(REPO_ROOT, "data", "corpus_manifest.json");
  try {
    const raw = await fs.readFile(manifestPath, "utf-8");
    const parsed: { description?: string; documents: ManifestEntry[] } =
      JSON.parse(raw);
    const docs = parsed.documents ?? [];
    return {
      total: docs.length,
      bySebi: docs.filter((d) => d.regulator === "SEBI").length,
      byRbi: docs.filter((d) => d.regulator === "RBI").length,
      categories: new Set(docs.map((d) => d.category)).size,
      manifestDescription: parsed.description ?? null,
    };
  } catch {
    return {
      total: 0,
      bySebi: 0,
      byRbi: 0,
      categories: 0,
      manifestDescription: null,
    };
  }
}

export interface EvalSummary {
  startedAt: string;
  baseUrl: string;
  nItems: number;
  nErrors: number;
  recallAt1: number | null;
  recallAt3: number | null;
  recallAt5: number | null;
  mrr: number | null;
  citationInRetrieved: number | null;
  faithfulness: number | null;
  completeness: number | null;
  refusal: number | null;
  latencyP50Ms: number | null;
  latencyP95Ms: number | null;
}

interface EvalRunFile {
  started_at: string;
  base_url: string;
  n_items: number;
  n_errors: number;
  aggregate_recall_at_k: Record<string, number>;
  aggregate_mrr: number;
  aggregate_citation_in_retrieved: number;
  aggregate_faithfulness: number | null;
  aggregate_completeness: number | null;
  aggregate_refusal: number | null;
  latency_p50_ms: number;
  latency_p95_ms: number;
}

export async function loadLatestEvalRun(): Promise<EvalSummary | null> {
  const dir = path.join(REPO_ROOT, "eval", "results");
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return null;
  }

  const runFiles = entries
    .filter((f) => f.startsWith("run_") && f.endsWith(".json"))
    .sort()
    .reverse();
  if (runFiles.length === 0) return null;

  try {
    const raw = await fs.readFile(path.join(dir, runFiles[0]), "utf-8");
    const parsed: EvalRunFile = JSON.parse(raw);
    return {
      startedAt: parsed.started_at,
      baseUrl: parsed.base_url,
      nItems: parsed.n_items,
      nErrors: parsed.n_errors,
      recallAt1: parsed.aggregate_recall_at_k?.["1"] ?? null,
      recallAt3: parsed.aggregate_recall_at_k?.["3"] ?? null,
      recallAt5: parsed.aggregate_recall_at_k?.["5"] ?? null,
      mrr: parsed.aggregate_mrr ?? null,
      citationInRetrieved: parsed.aggregate_citation_in_retrieved ?? null,
      faithfulness: parsed.aggregate_faithfulness,
      completeness: parsed.aggregate_completeness,
      refusal: parsed.aggregate_refusal,
      latencyP50Ms: parsed.latency_p50_ms ?? null,
      latencyP95Ms: parsed.latency_p95_ms ?? null,
    };
  } catch {
    return null;
  }
}
