/**
 * Maps reading time (minutes) to max articles per feed.
 * Mirrors the slider in web/pages/onboarding.py and delivery.py.
 */
const READING_TIME_MAP: Record<number, number> = {
  5: 3,
  10: 5,
  15: 8,
  20: 10,
  30: 15,
};

export const READING_TIME_OPTIONS = [5, 10, 15, 20, 30];

export function readingTimeToArticleCount(minutes: number): number {
  return READING_TIME_MAP[minutes] ?? 10;
}

export function articleCountToReadingTime(count: number): number {
  for (const [minutes, articles] of Object.entries(READING_TIME_MAP)) {
    if (articles === count) return Number(minutes);
  }
  return 20; // default
}

export function formatReadingTime(minutes: number): string {
  return `${minutes} min`;
}
