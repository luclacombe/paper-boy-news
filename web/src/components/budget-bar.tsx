"use client";

import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { READING_TIME_OPTIONS } from "@/lib/reading-time";

interface BudgetBarProps {
  /** Raw total daily output from all selected sources (sum of dailyReadMin). */
  sourceOutputMinutes: number;
  /** User's reading time budget. */
  budgetMinutes: number;
  /** Number of selected sources. */
  sourceCount: number;
  /** Average per-article reading time across selected sources. */
  avgArticleMin: number;
  /** Total estimated articles per day across selected sources. */
  dailyArticles: number;
  hasStats: boolean;
  /** Callback to change reading time (steps through READING_TIME_OPTIONS). */
  onReadingTimeChange?: (minutes: number) => void;
}

/**
 * Budget bar with stepper and pipeline messaging.
 *
 * Shows:
 * 1. Reading time stepper: [-] 20m [+]
 * 2. Fill bar (color-coded)
 * 3. Pipeline: "~25 articles → best 7 picked → 20m paper"
 */
export function BudgetBar({
  sourceOutputMinutes,
  budgetMinutes,
  sourceCount,
  avgArticleMin,
  dailyArticles,
  hasStats,
  onReadingTimeChange,
}: BudgetBarProps) {
  // Stepper logic
  const currentIdx = READING_TIME_OPTIONS.indexOf(budgetMinutes);
  const canDecrease = currentIdx > 0;
  const canIncrease = currentIdx < READING_TIME_OPTIONS.length - 1;

  function handleDecrease() {
    if (canDecrease && onReadingTimeChange) {
      onReadingTimeChange(READING_TIME_OPTIONS[currentIdx - 1]);
    }
  }

  function handleIncrease() {
    if (canIncrease && onReadingTimeChange) {
      onReadingTimeChange(READING_TIME_OPTIONS[currentIdx + 1]);
    }
  }

  // Bar + pipeline calculations
  // The build pipeline allows up to 5 min overshoot so the last article
  // isn't awkwardly cut. maxArticles reflects what will actually be served.
  const OVERSHOOT_CAP = 5;
  const canFill = budgetMinutes > 0 && sourceOutputMinutes >= budgetMinutes;
  const maxArticles =
    avgArticleMin > 0
      ? Math.floor((budgetMinutes + OVERSHOOT_CAP) / avgArticleMin)
      : 0;
  const paperMinutes = canFill ? budgetMinutes : Math.round(sourceOutputMinutes);
  const ratio = budgetMinutes > 0 ? sourceOutputMinutes / budgetMinutes : 0;
  const pct = Math.min(ratio * 100, 100);

  const barColor =
    ratio >= 0.8
      ? "bg-delivered"
      : ratio >= 0.5
        ? "bg-building"
        : "bg-edition-red";

  const showBar = hasStats && sourceCount > 0;

  // Warning: sources that won't fit
  const sourcesWithoutRoom =
    showBar && canFill && sourceCount > maxArticles
      ? sourceCount - maxArticles
      : 0;

  // Pipeline text segments
  function getPipeline(): { articles: string; picked: string; paper: string } | null {
    if (!showBar || dailyArticles === 0) return null;

    const articles = `~${dailyArticles} article${dailyArticles !== 1 ? "s" : ""}`;

    let picked: string;
    if (!canFill || dailyArticles <= maxArticles) {
      picked = "all picked";
    } else {
      picked = `best ${maxArticles} picked`;
    }

    const paper = canFill
      ? `${budgetMinutes}m paper`
      : `${paperMinutes}m of ${budgetMinutes}m`;

    return { articles, picked, paper };
  }

  const pipeline = getPipeline();

  return (
    <div className="space-y-2">
      {/* Stepper row */}
      {onReadingTimeChange && (
        <div className="flex items-center justify-between">
          <h3 className="font-headline text-sm font-bold text-ink">
            Reading time
          </h3>
          <div className="flex items-center">
            <button
              type="button"
              onClick={handleDecrease}
              disabled={!canDecrease}
              className={cn(
                "flex h-7 w-7 items-center justify-center border border-rule-gray transition-colors",
                canDecrease
                  ? "bg-card text-ink hover:bg-warm-gray"
                  : "bg-warm-gray/50 text-caption/40 cursor-not-allowed"
              )}
              aria-label="Decrease reading time"
            >
              <Minus className="h-3 w-3" />
            </button>
            <span className="flex h-7 w-10 items-center justify-center border-y border-rule-gray bg-ink font-mono text-xs font-bold text-newsprint letterpress">
              {budgetMinutes}m
            </span>
            <button
              type="button"
              onClick={handleIncrease}
              disabled={!canIncrease}
              className={cn(
                "flex h-7 w-7 items-center justify-center border border-rule-gray transition-colors",
                canIncrease
                  ? "bg-card text-ink hover:bg-warm-gray"
                  : "bg-warm-gray/50 text-caption/40 cursor-not-allowed"
              )}
              aria-label="Increase reading time"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      {/* Fill bar */}
      {showBar && (
        <div className="h-2 w-full overflow-hidden rounded-full bg-rule-gray">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              barColor
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {/* Pipeline */}
      {pipeline && (
        <p className="font-mono text-xs text-caption">
          <span>{pipeline.articles}</span>
          <span className="mx-1 text-rule-gray">→</span>
          <span>{pipeline.picked}</span>
          <span className="mx-1 text-rule-gray">→</span>
          <span className="text-ink">{pipeline.paper}</span>
        </p>
      )}

      {/* Warning: some sources won't fit */}
      {sourcesWithoutRoom > 0 && (
        <p className="font-body text-xs text-building">
          {sourcesWithoutRoom} of your {sourceCount} sources won&apos;t have
          room in a {budgetMinutes}m paper
        </p>
      )}
    </div>
  );
}
