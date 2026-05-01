/**
 * Zod schemas mirroring the backend Pydantic models in app/models/schemas.py.
 *
 * Every API response is validated through these — if the backend ever drifts,
 * the parse fails loudly instead of silently feeding bad data to the UI.
 */

import { z } from "zod";

export const RegulatorSchema = z.enum(["SEBI", "RBI"]);
export type Regulator = z.infer<typeof RegulatorSchema>;

export const ConfidenceSchema = z.enum(["high", "medium", "low"]);
export type Confidence = z.infer<typeof ConfidenceSchema>;

export const CitationSchema = z.object({
  doc_id: z.string(),
  doc_title: z.string(),
  regulator: RegulatorSchema,
  section: z.string().nullable().optional(),
  page: z.number().int().nullable().optional(),
  snippet: z.string(),
  url: z.string(),
});
export type Citation = z.infer<typeof CitationSchema>;

export const AnswerResponseSchema = z.object({
  question: z.string(),
  answer: z.string(),
  citations: z.array(CitationSchema),
  confidence: ConfidenceSchema,
  reasoning: z.string(),
  retrieval_method: z.literal("hybrid"),
  model_used: z.string(),
  tokens_used: z.number().int(),
  latency_ms: z.number().int(),
  warnings: z.array(z.string()),
});
export type AnswerResponse = z.infer<typeof AnswerResponseSchema>;

export const RetrievedChunkSchema = z.object({
  chunk_id: z.string(),
  doc_id: z.string(),
  doc_title: z.string(),
  regulator: RegulatorSchema,
  section_path: z.string().nullable().optional(),
  page_start: z.number().int().nullable().optional(),
  page_end: z.number().int().nullable().optional(),
  text: z.string(),
  score: z.number(),
  source_url: z.string(),
});
export type RetrievedChunk = z.infer<typeof RetrievedChunkSchema>;

export const SearchResponseSchema = z.object({
  query: z.string(),
  chunks: z.array(RetrievedChunkSchema),
  latency_ms: z.number().int(),
  retrieval_method: z.enum(["hybrid", "hybrid+rerank"]),
});
export type SearchResponse = z.infer<typeof SearchResponseSchema>;

export const HealthResponseSchema = z.object({
  status: z.literal("ok"),
  version: z.string(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.number().int(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;
