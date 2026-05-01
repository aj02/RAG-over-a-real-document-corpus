/**
 * Typed client for the regrag FastAPI backend.
 *
 * Every response is validated with Zod before being returned to a hook —
 * if the backend ever drifts the parse fails loudly rather than corrupting
 * the UI silently.
 */

import { z } from "zod";
import {
  AnswerResponseSchema,
  ApiErrorSchema,
  DocumentsResponseSchema,
  HealthResponseSchema,
  SearchResponseSchema,
  type AnswerResponse,
  type DocumentsResponse,
  type HealthResponse,
  type Regulator,
  type SearchResponse,
} from "@/lib/schemas";

const DEFAULT_BASE_URL = "http://localhost:8000";

function baseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_BASE_URL).replace(
    /\/+$/,
    "",
  );
}

export class ApiCallError extends Error {
  status: number;
  details: unknown;
  constructor(message: string, status: number, details: unknown = null) {
    super(message);
    this.name = "ApiCallError";
    this.status = status;
    this.details = details;
  }
}

async function request<T>(
  path: string,
  init: RequestInit,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const url = `${baseUrl()}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    throw new ApiCallError(
      err instanceof Error ? err.message : "network error",
      0,
      err,
    );
  }

  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const parsed = ApiErrorSchema.safeParse(body);
    const message = parsed.success
      ? parsed.data.error.message
      : `HTTP ${res.status}`;
    throw new ApiCallError(message, res.status, body);
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiCallError(
      "response failed schema validation",
      res.status,
      parsed.error.issues,
    );
  }
  return parsed.data;
}

export interface AskInput {
  question: string;
  top_k?: number;
  regulator_filter?: Regulator | null;
}

export function ask(
  input: AskInput,
  signal?: AbortSignal,
): Promise<AnswerResponse> {
  return request(
    "/ask",
    {
      method: "POST",
      body: JSON.stringify({
        question: input.question,
        top_k: input.top_k ?? 5,
        regulator_filter: input.regulator_filter ?? null,
      }),
    },
    AnswerResponseSchema,
    signal,
  );
}

export interface SearchInput {
  query: string;
  top_k?: number;
  regulator?: Regulator | null;
  rerank?: boolean;
}

export function search(
  input: SearchInput,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = new URLSearchParams();
  params.set("q", input.query);
  params.set("top_k", String(input.top_k ?? 10));
  params.set("rerank", String(input.rerank ?? true));
  if (input.regulator) params.set("regulator", input.regulator);
  return request(
    `/search?${params.toString()}`,
    { method: "GET" },
    SearchResponseSchema,
    signal,
  );
}

export function health(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/health", { method: "GET" }, HealthResponseSchema, signal);
}

export function listDocuments(signal?: AbortSignal): Promise<DocumentsResponse> {
  return request(
    "/documents",
    { method: "GET" },
    DocumentsResponseSchema,
    signal,
  );
}
