"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Clock,
  Cpu,
  GitMerge,
  Hash,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { AnswerResponse, Confidence } from "@/lib/schemas";
import { cn, formatLatency, formatNumber } from "@/lib/utils";

interface Props {
  data: AnswerResponse;
}

function confidenceVariant(c: Confidence) {
  if (c === "high") return "confidenceHigh" as const;
  if (c === "medium") return "confidenceMedium" as const;
  return "confidenceLow" as const;
}

const DISCLAIMER = "This is regulatory information, not legal advice.";

export function AnswerCard({ data }: Props) {
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const visibleWarnings = data.warnings.filter((w) => w !== DISCLAIMER);

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <header className="flex flex-wrap items-center gap-2">
          <Badge variant={confidenceVariant(data.confidence)}>
            {data.confidence} confidence
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px]">
            {data.retrieval_method}
          </Badge>
          {data.warnings.includes("no_relevant_context") && (
            <Badge variant="destructive">no relevant context</Badge>
          )}
          {data.warnings.some((w) => w.startsWith("model cited unknown")) && (
            <Badge variant="destructive">unmatched citation</Badge>
          )}
        </header>

        <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-base leading-relaxed text-foreground">
          {data.answer}
        </div>

        {visibleWarnings.length > 0 && (
          <div className="rounded-md border border-amber-200/60 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <ul className="space-y-0.5">
                {visibleWarnings.map((w, i) => (
                  <li key={i} className="font-mono">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <Separator />

        <div className="space-y-2 text-xs">
          <button
            type="button"
            onClick={() => setReasoningOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 font-medium text-muted-foreground transition-colors hover:text-foreground"
            aria-expanded={reasoningOpen}
          >
            <ChevronDown
              className={cn(
                "h-3 w-3 transition-transform",
                reasoningOpen && "rotate-180",
              )}
            />
            How this was derived
          </button>
          {reasoningOpen && (
            <p className="pl-4 leading-relaxed text-muted-foreground">
              {data.reasoning || "(no reasoning provided)"}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <Stat icon={Cpu} label={data.model_used} title="Model" />
          <Stat
            icon={Hash}
            label={`${formatNumber(data.tokens_used)} tokens`}
            title="Tokens used"
          />
          <Stat
            icon={Clock}
            label={formatLatency(data.latency_ms)}
            title="Latency"
          />
          <Stat
            icon={GitMerge}
            label={data.retrieval_method}
            title="Retrieval method"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({
  icon: Icon,
  label,
  title,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  title: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <Icon className="h-3 w-3" />
      <span className="font-mono">{label}</span>
    </span>
  );
}
