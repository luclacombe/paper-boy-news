"use client";

interface BudgetBarProps {
  estimatedMinutes: number;
  budgetMinutes: number;
  hasStats: boolean;
}

/** Thin progress bar showing estimated daily reading vs budget. */
export function BudgetBar({
  estimatedMinutes,
  budgetMinutes,
  hasStats,
}: BudgetBarProps) {
  if (!hasStats) return null;

  const rounded = Math.round(estimatedMinutes);
  const ratio = budgetMinutes > 0 ? estimatedMinutes / budgetMinutes : 0;
  const pct = Math.min(ratio * 100, 100);

  const barColor =
    ratio <= 0.8
      ? "bg-delivered"
      : ratio <= 1.2
        ? "bg-building"
        : "bg-edition-red";

  const showWarning = ratio > 2 && rounded > 0;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between font-mono text-xs">
        <span className="text-ink">
          Your paper: ~{rounded} min/day
        </span>
        <span className="text-caption">of {budgetMinutes}m budget</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-rule-gray">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showWarning && (
        <p className="font-body text-xs italic text-caption">
          These sources typically produce ~{rounded} min/day. Your paper is
          set to {budgetMinutes} min, so some articles will be trimmed.
        </p>
      )}
    </div>
  );
}
