"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RetrievedChunk } from "@/lib/schemas";
import { cn } from "@/lib/utils";

interface Props {
  chunk: RetrievedChunk;
  rank: number;
}

const PREVIEW_CHARS = 360;

export function ChunkRow({ chunk, rank }: Props) {
  const [open, setOpen] = useState(false);
  const isLong = chunk.text.length > PREVIEW_CHARS;
  const text =
    open || !isLong
      ? chunk.text
      : chunk.text.slice(0, PREVIEW_CHARS).trimEnd() + "…";

  const pageRange =
    chunk.page_start != null && chunk.page_end != null
      ? chunk.page_start === chunk.page_end
        ? `p.${chunk.page_start}`
        : `p.${chunk.page_start}–${chunk.page_end}`
      : null;

  return (
    <article className="rounded-lg border border-border/60 bg-card p-4 shadow-sm">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
        <span className="grid h-5 w-5 place-items-center rounded-full border border-border/80 bg-background font-mono font-semibold text-foreground">
          {rank}
        </span>
        <Badge
          variant={chunk.regulator === "RBI" ? "rbi" : "sebi"}
          className="text-[10px]"
        >
          {chunk.regulator}
        </Badge>
        <span className="font-mono">
          score {chunk.score.toFixed(4)}
        </span>
        {pageRange && <span className="font-mono">{pageRange}</span>}
        <span className="ml-auto inline-flex">
          <a
            href={chunk.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 hover:text-foreground"
          >
            <ExternalLink className="h-3 w-3" />
            source
          </a>
        </span>
      </header>
      <h3 className="mt-2 text-sm font-medium text-foreground">
        {chunk.doc_title}
      </h3>
      {chunk.section_path && (
        <p className="mt-0.5 text-xs text-muted-foreground" title={chunk.section_path}>
          {chunk.section_path}
        </p>
      )}
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          <ChevronDown
            className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
          />
          {open ? "show less" : "show full chunk"}
        </button>
      )}
      <div className="mt-3 font-mono text-[10px] text-muted-foreground">
        <span className="opacity-60">chunk_id:</span> {chunk.chunk_id}
      </div>
    </article>
  );
}
