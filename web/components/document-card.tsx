"use client";

import { ExternalLink, FileText, Hash } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { DocumentSummary } from "@/lib/schemas";
import { formatNumber } from "@/lib/utils";

interface Props {
  doc: DocumentSummary;
}

export function DocumentCard({ doc }: Props) {
  return (
    <Card className="flex h-full flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 pt-6">
        <header className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge
            variant={doc.regulator === "RBI" ? "rbi" : "sebi"}
            className="text-[10px]"
          >
            {doc.regulator}
          </Badge>
          {doc.category && (
            <span className="font-mono text-[10px] uppercase tracking-wide">
              {doc.category.replace(/_/g, " ")}
            </span>
          )}
          {doc.issue_date && (
            <span className="font-mono">{doc.issue_date}</span>
          )}
        </header>

        <h3 className="text-sm font-semibold leading-snug text-foreground">
          {doc.title}
        </h3>

        <p className="flex-1 text-xs leading-relaxed text-muted-foreground">
          {doc.preview ||
            "No preview available — this document was registered but its first chunk did not contain extractable prose."}
        </p>

        <footer className="flex items-center justify-between border-t border-border/60 pt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1" title="Pages">
              <FileText className="h-3 w-3" />
              {doc.num_pages ?? "?"} p.
            </span>
            <span
              className="inline-flex items-center gap-1"
              title="Chunks indexed"
            >
              <Hash className="h-3 w-3" />
              {formatNumber(doc.chunk_count)}
            </span>
            <span className="font-mono text-[10px]">{doc.doc_id}</span>
          </div>
          <a
            href={doc.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 hover:text-foreground"
            aria-label={`Open ${doc.title} on regulator site`}
          >
            <ExternalLink className="h-3 w-3" />
            source
          </a>
        </footer>
      </CardContent>
    </Card>
  );
}
