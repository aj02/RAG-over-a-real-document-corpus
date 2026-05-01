/**
 * TanStack Query hooks. Centralised so query keys + retry policy live in one place.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ask,
  health,
  listDocuments,
  search,
  type AskInput,
  type SearchInput,
} from "@/lib/api";

export function useAsk() {
  return useMutation({
    mutationFn: (input: AskInput) => ask(input),
    retry: 0,
  });
}

export function useSearch() {
  return useMutation({
    mutationFn: (input: SearchInput) => search(input),
    retry: 0,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => health(signal),
    staleTime: 30 * 1000,
    retry: 0,
  });
}

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: ({ signal }) => listDocuments(signal),
    // The corpus only changes when /ingest runs, so we can cache aggressively.
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
