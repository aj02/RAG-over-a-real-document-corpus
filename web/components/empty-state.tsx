import { Search } from "lucide-react";

export function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-border/60 bg-muted/20 px-6 py-10 text-center">
      <div className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-muted">
        <Search className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="mt-3 text-sm font-medium text-foreground">
        Ask a question to get started
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Answers are drawn only from the indexed SEBI and RBI corpus, with
        citations to the source document and page.
      </p>
    </div>
  );
}
