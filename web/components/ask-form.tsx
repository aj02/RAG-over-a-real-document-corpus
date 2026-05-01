"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RegulatorFilter, type RegulatorChoice } from "@/components/regulator-filter";
import { TopKSelector, type TopKValue } from "@/components/top-k-selector";

interface Props {
  question: string;
  onQuestionChange: (q: string) => void;
  regulator: RegulatorChoice;
  onRegulatorChange: (r: RegulatorChoice) => void;
  topK: TopKValue;
  onTopKChange: (k: TopKValue) => void;
  isPending: boolean;
  onSubmit: () => void;
  autoFocus?: boolean;
}

export function AskForm({
  question,
  onQuestionChange,
  regulator,
  onRegulatorChange,
  topK,
  onTopKChange,
  isPending,
  onSubmit,
  autoFocus = false,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  const canSubmit = question.trim().length >= 3 && !isPending;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canSubmit) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit();
      }}
      className="space-y-3"
    >
      <div className="relative rounded-lg border border-input bg-background shadow-sm transition-shadow focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
        <Textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about a SEBI circular or RBI master direction…"
          className="min-h-[120px] resize-none border-0 bg-transparent pr-14 text-base shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
          disabled={isPending}
          aria-label="Question"
        />
        <div className="absolute bottom-2 right-2">
          <Button
            type="submit"
            size="icon"
            disabled={!canSubmit}
            aria-label="Ask"
            title="Ask (⌘+Enter)"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <RegulatorFilter
            value={regulator}
            onChange={onRegulatorChange}
            disabled={isPending}
          />
          <TopKSelector value={topK} onChange={onTopKChange} disabled={isPending} />
        </div>
        <span className="text-xs text-muted-foreground">
          ⌘ + Enter to submit
        </span>
      </div>
    </form>
  );
}
