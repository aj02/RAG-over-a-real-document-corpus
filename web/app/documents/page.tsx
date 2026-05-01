"use client";

import { useMemo, useState } from "react";
import { Search, Library } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { DocumentCard } from "@/components/document-card";
import { ErrorState } from "@/components/error-state";
import { RegulatorFilter, type RegulatorChoice } from "@/components/regulator-filter";
import { useDocuments } from "@/lib/queries";
import type { DocumentSummary } from "@/lib/schemas";

function tokenize(s: string): string {
  return s.toLowerCase();
}

function filterDocs(
  docs: DocumentSummary[],
  query: string,
  regulator: RegulatorChoice,
): DocumentSummary[] {
  const q = tokenize(query.trim());
  return docs.filter((d) => {
    if (regulator !== "ALL" && d.regulator !== regulator) return false;
    if (!q) return true;
    return (
      tokenize(d.title).includes(q) ||
      tokenize(d.doc_id).includes(q) ||
      tokenize(d.category ?? "").includes(q) ||
      tokenize(d.preview).includes(q)
    );
  });
}

export default function DocumentsPage() {
  const { data, isPending, isError, error, refetch } = useDocuments();
  const [query, setQuery] = useState("");
  const [regulator, setRegulator] = useState<RegulatorChoice>("ALL");

  const filtered = useMemo(
    () => (data ? filterDocs(data.documents, query, regulator) : []),
    [data, query, regulator],
  );

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-12">
      <header className="mb-6 flex flex-col gap-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          <Library className="h-6 w-6 text-muted-foreground" />
          Document catalogue
        </h1>
        <p className="text-sm text-muted-foreground">
          Every PDF currently indexed in the corpus, with a short preview drawn
          from the first substantive passage of the document.
        </p>
      </header>

      <Alert variant="info" className="mb-6">
        <Library className="h-4 w-4" />
        <AlertTitle>How these previews are built</AlertTitle>
        <AlertDescription className="mt-1">
          Previews are not LLM-generated abstracts. They come from the first
          ~400 characters of each document&apos;s first non-TOC chunk —
          typically the preamble or scope statement. Open the source link to
          read the full master circular or master direction on
          sebi.gov.in / rbi.org.in.
        </AlertDescription>
      </Alert>

      <section className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by title, doc id, or preview text…"
            className="pl-9"
            aria-label="Filter documents"
          />
        </div>
        <RegulatorFilter value={regulator} onChange={setRegulator} />
      </section>

      {isPending && (
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="space-y-3 pt-6">
                <div className="flex gap-2">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-24" />
                </div>
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {isError && <ErrorState error={error} onRetry={() => refetch()} />}

      {data && (
        <>
          <div className="mb-3 text-xs text-muted-foreground">
            {filtered.length} of {data.total} documents
            {regulator !== "ALL" ? ` · ${regulator} only` : ""}
            {query ? ` · matching "${query}"` : ""}
          </div>
          {filtered.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border/70 bg-muted/30 px-4 py-10 text-center text-sm text-muted-foreground">
              No documents match the current filters.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {filtered.map((doc) => (
                <DocumentCard key={doc.doc_id} doc={doc} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
