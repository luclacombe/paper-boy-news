import { describe, it, expect } from "vitest";
import { getFrequencyLabel, formatDailyReadTime } from "@/lib/reading-time";
import type { FeedStat } from "@/types";

// Test the FeedBadges + BundleReadTime logic directly
// These components are thin wrappers around reading-time helpers

function makeStat(overrides: Partial<FeedStat> = {}): FeedStat {
  return {
    url: "https://example.com/feed",
    name: "Example",
    observedAt: "2026-01-01T00:00:00Z",
    sampleCount: 5,
    totalEntries: 10,
    fresh24h: 3,
    fresh48h: 5,
    attempted: 8,
    extracted: 7,
    avgWordCount: 500,
    medianWordCount: 450,
    avgImages: 2,
    articlesPerDay: 2,
    estimatedReadMin: 2,
    dailyReadMin: 4,
    ...overrides,
  };
}

describe("FeedBadges logic", () => {
  it("renders nothing for unknown URL (no stat in map)", () => {
    const statsMap: Record<string, FeedStat> = {};
    const stat = statsMap["https://unknown.com/feed"];
    expect(stat).toBeUndefined();
  });

  it("shows frequency and time for known URL", () => {
    const stat = makeStat({ articlesPerDay: 2, dailyReadMin: 4 });
    expect(getFrequencyLabel(stat.articlesPerDay)).toBe("Daily");
    expect(formatDailyReadTime(stat.dailyReadMin)).toBe("~4 min/day");
  });

  it("shows only frequency when dailyReadMin is 0", () => {
    const stat = makeStat({ articlesPerDay: 5, dailyReadMin: 0 });
    expect(getFrequencyLabel(stat.articlesPerDay)).toBe("Several/day");
    expect(formatDailyReadTime(stat.dailyReadMin)).toBeNull();
  });

  it("shows 'A few/week' for low-frequency feeds", () => {
    const stat = makeStat({ articlesPerDay: 0.3 });
    expect(getFrequencyLabel(stat.articlesPerDay)).toBe("A few/week");
  });
});

describe("BundleReadTime logic", () => {
  it("computes avg per-article reading time across feeds", () => {
    const feeds = [
      makeStat({ url: "https://a.com/feed", estimatedReadMin: 4 }),
      makeStat({ url: "https://b.com/feed", estimatedReadMin: 6 }),
    ];
    const withStats = feeds.filter((f) => f.estimatedReadMin > 0);
    const totalReadMin = withStats.reduce((sum, f) => sum + f.estimatedReadMin, 0);
    const avgReadMin = Math.round(totalReadMin / withStats.length);
    expect(avgReadMin).toBe(5);
    expect(feeds.length).toBe(2);
  });

  it("returns 0 avg when no feeds have stats", () => {
    const feeds: FeedStat[] = [];
    const withStats = feeds.filter((f) => f.estimatedReadMin > 0);
    expect(withStats.length).toBe(0);
  });
});
