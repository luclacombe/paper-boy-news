/** Maps reading time (minutes) to total article budget. */
const READING_TIME_MAP: Record<number, number> = {
  5: 2,
  10: 3,
  15: 5,
  20: 7,
  30: 10,
  45: 15,
  60: 20,
};

export const READING_TIME_OPTIONS = [5, 10, 15, 20, 30, 45, 60];

export function readingTimeToArticleBudget(minutes: number): number {
  return READING_TIME_MAP[minutes] ?? 7;
}

/** Returns recommended source count range [min, max] for a given budget. */
export function recommendedSourceRange(
  budget: number
): [number, number] {
  return [Math.max(1, Math.ceil(budget * 0.5)), Math.min(20, Math.max(2, budget * 2))];
}

import type { FeedStat } from "@/types";

/** Human-readable publishing frequency label. */
export function getFrequencyLabel(articlesPerDay: number): string | null {
  if (articlesPerDay >= 3) return "Several/day";
  if (articlesPerDay >= 1) return "Daily";
  if (articlesPerDay >= 0.15) return "A few/week";
  if (articlesPerDay > 0) return "Weekly";
  return null;
}

/** Format daily reading time as a short label. */
export function formatDailyReadTime(dailyReadMin: number): string | null {
  if (dailyReadMin <= 0) return null;
  if (Math.round(dailyReadMin) === 0) return "<1 min/day";
  return `~${Math.round(dailyReadMin)} min/day`;
}

/** Sum of dailyReadMin for all selected URLs that have stats. */
export function estimateTotalDailyReading(
  selectedUrls: Set<string>,
  statsMap: Record<string, FeedStat>
): number {
  let total = 0;
  for (const url of selectedUrls) {
    const stat = statsMap[url];
    if (stat) total += stat.dailyReadMin;
  }
  return total;
}

/** Whether the stats map contains any entries. */
export function hasAnyStats(statsMap: Record<string, FeedStat>): boolean {
  return Object.keys(statsMap).length > 0;
}
