"use client";

import { cn } from "@/lib/utils";
import { formatChipReadTime, getChipFrequencyLabel } from "@/lib/reading-time";

interface FeedChipProps {
  name: string;
  description: string;
  estimatedReadMin: number | null;
  articlesPerDay: number | null;
  selected: boolean;
  onChange: () => void;
}

export function FeedChip({
  name,
  description,
  estimatedReadMin,
  articlesPerDay,
  selected,
  onChange,
}: FeedChipProps) {
  const timeLabel =
    estimatedReadMin != null ? formatChipReadTime(estimatedReadMin) : null;
  const freqLabel =
    articlesPerDay != null ? getChipFrequencyLabel(articlesPerDay) : null;

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
      {(freqLabel || timeLabel) && (
        <span
          className={cn(
            "flex items-center gap-1 font-mono text-[10px] leading-none",
            selected ? "text-newsprint/70" : "text-caption"
          )}
        >
          {freqLabel && <span>{freqLabel}</span>}
          {freqLabel && timeLabel && (
            <span className={selected ? "text-newsprint/40" : "text-rule-gray"}>·</span>
          )}
          {timeLabel && <span>{timeLabel}</span>}
        </span>
      )}
    </button>
  );
}
