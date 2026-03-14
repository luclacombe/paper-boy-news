"use client";

import { cn } from "@/lib/utils";
import { formatChipReadTime } from "@/lib/reading-time";

interface FeedChipProps {
  name: string;
  description: string;
  estimatedReadMin: number | null;
  selected: boolean;
  onChange: () => void;
}

export function FeedChip({
  name,
  description,
  estimatedReadMin,
  selected,
  onChange,
}: FeedChipProps) {
  const timeLabel =
    estimatedReadMin != null ? formatChipReadTime(estimatedReadMin) : null;

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      title={description}
      onClick={onChange}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 transition-colors",
        "min-h-[36px] cursor-pointer select-none",
        selected
          ? "border-ink bg-ink text-newsprint"
          : "border-rule-gray bg-card text-ink hover:border-caption"
      )}
    >
      <span className="font-headline text-xs font-bold leading-tight">
        {name}
      </span>
      {timeLabel && (
        <span
          className={cn(
            "font-mono text-[10px] leading-none",
            selected ? "text-newsprint/70" : "text-caption"
          )}
        >
          {timeLabel}
        </span>
      )}
    </button>
  );
}
