"use client";

import { AlertCircle, RotateCcw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiCallError } from "@/lib/api";

interface Props {
  error: unknown;
  onRetry?: () => void;
}

function describe(error: unknown): { title: string; body: string } {
  if (error instanceof ApiCallError) {
    if (error.status === 0) {
      return {
        title: "Backend unreachable",
        body:
          "The regrag API at NEXT_PUBLIC_API_URL did not respond. Make sure docker compose up is running and the API is healthy at /health.",
      };
    }
    if (error.status === 503) {
      return {
        title: "Service not ready",
        body:
          "The pipeline is not ready yet — usually the database has no chunks ingested. Run `python -m scripts.ingest_cli` and retry.",
      };
    }
    return {
      title: `Request failed (${error.status})`,
      body: error.message,
    };
  }
  return {
    title: "Something went wrong",
    body: error instanceof Error ? error.message : "Unknown error.",
  };
}

export function ErrorState({ error, onRetry }: Props) {
  const { title, body } = describe(error);
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="mt-1">
        <p>{body}</p>
        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-3"
          >
            <RotateCcw className="h-3 w-3" />
            Retry
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}
