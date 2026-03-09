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
