"use client";

import { Quote } from "lucide-react";
import { CitationCard } from "@/components/citation-card";
import type { Citation } from "@/lib/schemas";

interface Props {
  citations: Citation[];
}

export function CitationList({ citations }: Props) {
  if (citations.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border/70 bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
        No citations were returned. The system either refused or could not find
        supporting passages — see the warnings above.
      </div>
    );
  }
  return (
    <section aria-label="Citations" className="space-y-3">
      <header className="flex items-center gap-2 text-sm font-medium">
        <Quote className="h-3.5 w-3.5 text-muted-foreground" />
        <h3>Citations</h3>
        <span className="text-xs font-normal text-muted-foreground">
          ({citations.length})
        </span>
      </header>
      <ul className="space-y-3">
        {citations.map((c, i) => (
          <li key={`${c.doc_id}-${c.page ?? "x"}-${i}`}>
            <CitationCard citation={c} index={i} />
          </li>
        ))}
      </ul>
    </section>
  );
}
