"use client";

import { cn } from "@/lib/utils";

const VALUES = [3, 5, 8, 10] as const;
type Value = (typeof VALUES)[number];

interface Props {
  value: Value;
  onChange: (v: Value) => void;
  disabled?: boolean;
}

export function TopKSelector({ value, onChange, disabled }: Props) {
  return (
    <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <span className="font-medium">top-k</span>
      <div
        role="radiogroup"
        aria-label="Number of chunks to retrieve"
        className="inline-flex items-center rounded-md border border-input bg-background p-0.5"
      >
        {VALUES.map((v) => {
          const active = v === value;
          return (
            <button
              key={v}
              role="radio"
              aria-checked={active}
              type="button"
              disabled={disabled}
              onClick={() => onChange(v)}
              className={cn(
                "min-w-[2rem] rounded-[5px] px-2 py-1 font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              {v}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type TopKValue = Value;
export const TOP_K_VALUES = VALUES;
