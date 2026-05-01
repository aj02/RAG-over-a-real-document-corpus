"use client";

import { Building2, Landmark, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Regulator } from "@/lib/schemas";

export type RegulatorChoice = Regulator | "ALL";

interface Option {
  value: RegulatorChoice;
  label: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const OPTIONS: Option[] = [
  { value: "ALL", label: "Both", Icon: Layers },
  { value: "SEBI", label: "SEBI", Icon: Building2 },
  { value: "RBI", label: "RBI", Icon: Landmark },
];

interface Props {
  value: RegulatorChoice;
  onChange: (v: RegulatorChoice) => void;
  disabled?: boolean;
}

export function RegulatorFilter({ value, onChange, disabled }: Props) {
  return (
    <div
      role="group"
      aria-label="Regulator filter"
      className="inline-flex items-center rounded-md border border-input bg-background p-0.5 text-xs"
    >
      {OPTIONS.map(({ value: v, label, Icon }) => {
        const active = v === value;
        return (
          <button
            type="button"
            key={v}
            disabled={disabled}
            aria-pressed={active}
            onClick={() => onChange(v)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[5px] px-2.5 py-1 font-medium transition-colors",
              active
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
