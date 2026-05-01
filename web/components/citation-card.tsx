"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Citation } from "@/lib/schemas";
import { cn } from "@/lib/utils";

interface Props {
  citation: Citation;
  index: number;
}

const SNIPPET_PREVIEW = 240;

export function CitationCard({ citation, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const isLong = citation.snippet.length > SNIPPET_PREVIEW;
  const displayed =
    expanded || !isLong
      ? citation.snippet
      : citation.snippet.slice(0, SNIPPET_PREVIEW).trimEnd() + "…";

  return (
    <article className="group rounded-lg border border-border/60 bg-card p-4 shadow-sm transition-colors hover:border-border">
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="grid h-5 w-5 place-items-center rounded-full border border-border/80 bg-background font-mono font-semibold text-foreground">
            {index + 1}
          </span>
          <Badge
            variant={citation.regulator === "RBI" ? "rbi" : "sebi"}
            className="text-[10px]"
          >
            {citation.regulator}
          </Badge>
          {citation.page != null && (
            <span className="font-mono">page {citation.page}</span>
          )}
          {citation.section && (
            <span
              className="hidden truncate sm:inline"
              title={citation.section}
            >
              · {citation.section}
            </span>
          )}
        </div>
        <Button asChild variant="ghost" size="sm" className="shrink-0 -mr-2">
          <a
            href={citation.url}
            target="_blank"
            rel="noreferrer noopener"
            aria-label={`Open ${citation.doc_title} on regulator site`}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">source</span>
          </a>
        </Button>
      </header>
      <div className="mt-2 flex items-start gap-2 text-sm font-medium text-foreground">
        <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span>{citation.doc_title}</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {displayed}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <ChevronDown
            className={cn(
              "h-3 w-3 transition-transform",
              expanded && "rotate-180",
            )}
          />
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </article>
  );
}
