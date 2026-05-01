import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function AnswerLoadingState() {
  return (
    <div
      className="space-y-4"
      role="status"
      aria-live="polite"
      aria-label="Generating answer"
    >
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex gap-2">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-5 w-20" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-[95%]" />
          <Skeleton className="h-4 w-[88%]" />
          <Skeleton className="h-4 w-[70%]" />
          <div className="flex gap-3 pt-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-24" />
          </div>
        </CardContent>
      </Card>
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="space-y-2 rounded-lg border border-border/60 bg-card p-4"
          >
            <div className="flex gap-2">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-16" />
            </div>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
          </div>
        ))}
      </div>
    </div>
  );
}
