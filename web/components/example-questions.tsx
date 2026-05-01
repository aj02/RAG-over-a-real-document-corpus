"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EXAMPLE_QUESTIONS } from "@/lib/examples";

interface Props {
  onPick: (question: string) => void;
  disabled?: boolean;
}

export function ExampleQuestions({ onPick, disabled }: Props) {
  return (
    <section
      aria-label="Example questions"
      className="rounded-xl border border-border/60 bg-muted/30 p-5"
    >
      <div className="mb-4 flex items-center gap-2 text-sm">
        <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-medium text-foreground">Try an example</span>
        <span className="text-muted-foreground">— click to load</span>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {EXAMPLE_QUESTIONS.map((ex) => (
          <li key={ex.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(ex.question)}
              className="group flex w-full items-start gap-3 rounded-md border border-transparent bg-background px-3 py-3 text-left text-sm shadow-sm transition-all hover:border-border hover:bg-accent disabled:pointer-events-none disabled:opacity-50"
            >
              <Badge
                variant={ex.category === "RBI" ? "rbi" : "sebi"}
                className="mt-0.5 shrink-0 text-[10px]"
              >
                {ex.category}
              </Badge>
              <div className="flex-1">
                <p className="text-foreground">{ex.question}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {ex.hint}
                </p>
              </div>
              <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
