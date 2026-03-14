"use client";

import { cn } from "@/lib/utils";

interface BudgetBarProps {
  /** Raw total daily output from all selected sources (sum of dailyReadMin). */
  sourceOutputMinutes: number;
  /** User's reading time budget. */
  budgetMinutes: number;
  /** Number of selected sources. */
  sourceCount: number;
  /** Average per-article reading time across selected sources. */
  avgArticleMin: number;
  hasStats: boolean;
}

/**
 * Budget bar with contextual messaging about how the paper is curated.
 *
 * Three states:
 * 1. Enough sources → bar full, reassuring curation message
 * 2. Too many sources for budget → bar full, note about rotation
 * 3. Not enough sources → bar partial, prompt to add more
 */
export function BudgetBar({
  sourceOutputMinutes,
  budgetMinutes,
  sourceCount,
  avgArticleMin,
  hasStats,
}: BudgetBarProps) {
  if (!hasStats || sourceCount === 0) return null;

  // How many articles can roughly fit in the budget?
  const maxArticles = avgArticleMin > 0 ? Math.floor(budgetMinutes / avgArticleMin) : 0;

  // Can the selected sources fill the budget?
  const canFill = budgetMinutes > 0 && sourceOutputMinutes >= budgetMinutes;
  const paperMinutes = canFill
    ? budgetMinutes
    : Math.round(sourceOutputMinutes);
  const ratio =
    budgetMinutes > 0 ? sourceOutputMinutes / budgetMinutes : 0;
  const pct = Math.min(ratio * 100, 100);

  // More sources than the paper can fit articles from
  const tooManySources = sourceCount > maxArticles && maxArticles > 0;

  const barColor =
    ratio >= 0.8
      ? "bg-delivered"
      : ratio >= 0.5
        ? "bg-building"
        : "bg-edition-red";

  // Contextual helper message
  let helperMessage: string | null = null;
  if (ratio === 0) {
    // no output (edge case)
  } else if (!canFill) {
    helperMessage = "Add more sources to fill your reading time.";
  } else if (tooManySources) {
    helperMessage = `Your paper fits ~${maxArticles} articles — sources are rotated so each gets featured.`;
  } else {
    helperMessage =
      "Articles are curated from your sources to match your reading time.";
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between font-mono text-xs">
        <span className="text-ink">
          Your paper: ~{paperMinutes}m
        </span>
        <span className="text-caption">of {budgetMinutes}m</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-rule-gray">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-300",
            barColor
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {helperMessage && (
        <p className="font-body text-xs italic text-caption">
          {helperMessage}
        </p>
      )}
    </div>
  );
}
