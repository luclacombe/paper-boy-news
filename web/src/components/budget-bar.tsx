"use client";

interface BudgetBarProps {
  /** Raw total daily output from all selected sources (sum of dailyReadMin). */
  sourceOutputMinutes: number;
  budgetMinutes: number;
  hasStats: boolean;
}

/**
 * Budget bar showing whether selected sources can fill the reading time budget.
 * Capped display: shows min(sourceOutput, budget) as "Your paper" estimate.
 */
export function BudgetBar({
  sourceOutputMinutes,
  budgetMinutes,
  hasStats,
}: BudgetBarProps) {
  if (!hasStats) return null;

  const canFill = budgetMinutes > 0 && sourceOutputMinutes >= budgetMinutes;
  const paperMinutes = canFill
    ? budgetMinutes
    : Math.round(sourceOutputMinutes);
  const ratio =
    budgetMinutes > 0 ? sourceOutputMinutes / budgetMinutes : 0;
  const pct = Math.min(ratio * 100, 100);

  const barColor =
    ratio >= 0.8
      ? "bg-delivered"
      : ratio >= 0.5
        ? "bg-building"
        : "bg-edition-red";

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between font-mono text-xs">
        <span className="text-ink">
          Your paper: ~{paperMinutes} min/day
        </span>
        <span className="text-caption">of {budgetMinutes}m budget</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-rule-gray">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {ratio > 0 && ratio < 0.8 && (
        <p className="font-body text-xs italic text-caption">
          Add more sources to fill your {budgetMinutes}m paper.
        </p>
      )}
    </div>
  );
}
