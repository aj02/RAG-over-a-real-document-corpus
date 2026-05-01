"use client";

import { useState } from "react";
import { AskForm } from "@/components/ask-form";
import { AnswerCard } from "@/components/answer-card";
import { CitationList } from "@/components/citation-list";
import { ExampleQuestions } from "@/components/example-questions";
import { EmptyState } from "@/components/empty-state";
import { AnswerLoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import type { RegulatorChoice } from "@/components/regulator-filter";
import type { TopKValue } from "@/components/top-k-selector";
import { useAsk } from "@/lib/queries";

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [regulator, setRegulator] = useState<RegulatorChoice>("ALL");
  const [topK, setTopK] = useState<TopKValue>(5);
  const ask = useAsk();

  const submit = () => {
    const q = question.trim();
    if (q.length < 3) return;
    ask.mutate({
      question: q,
      top_k: topK,
      regulator_filter: regulator === "ALL" ? null : regulator,
    });
  };

  const handlePickExample = (q: string) => {
    setQuestion(q);
    ask.mutate({
      question: q,
      top_k: topK,
      regulator_filter: regulator === "ALL" ? null : regulator,
    });
  };

  const showExamples = !ask.isPending && !ask.isError && !ask.data;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-12">
      <section className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Ask the regulations
        </h1>
        <p className="mt-2 text-sm text-muted-foreground sm:text-base">
          Natural-language Q&amp;A over SEBI circulars and RBI master
          directions. Every answer is grounded in retrieved passages and cited
          back to the source.
        </p>
      </section>

      <section className="mb-6">
        <AskForm
          question={question}
          onQuestionChange={setQuestion}
          regulator={regulator}
          onRegulatorChange={setRegulator}
          topK={topK}
          onTopKChange={setTopK}
          isPending={ask.isPending}
          onSubmit={submit}
          autoFocus
        />
      </section>

      {showExamples && (
        <div className="mb-8 space-y-6">
          <EmptyState />
          <ExampleQuestions
            onPick={handlePickExample}
            disabled={ask.isPending}
          />
        </div>
      )}

      {ask.isPending && (
        <section className="mt-8">
          <AnswerLoadingState />
        </section>
      )}

      {ask.isError && (
        <section className="mt-8">
          <ErrorState
            error={ask.error}
            onRetry={() => {
              if (question.trim().length >= 3) submit();
            }}
          />
        </section>
      )}

      {ask.data && !ask.isPending && (
        <section className="mt-8 space-y-6">
          <AnswerCard data={ask.data} />
          <CitationList citations={ask.data.citations} />
        </section>
      )}
    </div>
  );
}
