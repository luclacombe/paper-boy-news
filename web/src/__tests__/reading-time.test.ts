import { describe, it, expect } from "vitest";
import {
  readingTimeToArticleBudget,
  recommendedSourceRange,
  getFrequencyLabel,
  formatDailyReadTime,
  totalSourceDailyOutput,
  hasAnyStats,
  getFrequencyBucket,
  formatChipReadTime,
} from "@/lib/reading-time";
import type { FeedStat } from "@/types";

// ── Existing helpers ──

describe("readingTimeToArticleBudget", () => {
  it("maps known values", () => {
    expect(readingTimeToArticleBudget(5)).toBe(2);
    expect(readingTimeToArticleBudget(30)).toBe(10);
    expect(readingTimeToArticleBudget(60)).toBe(20);
  });

  it("returns default for unknown values", () => {
    expect(readingTimeToArticleBudget(99)).toBe(7);
  });
});

describe("recommendedSourceRange", () => {
  it("returns [min, max] range", () => {
    const [min, max] = recommendedSourceRange(10);
    expect(min).toBeGreaterThanOrEqual(1);
    expect(max).toBeLessThanOrEqual(20);
    expect(min).toBeLessThanOrEqual(max);
  });
});

// ── New helpers ──

describe("getFrequencyLabel", () => {
  it("returns 'Several/day' for ≥3", () => {
    expect(getFrequencyLabel(3)).toBe("Several/day");
    expect(getFrequencyLabel(10)).toBe("Several/day");
  });

  it("returns 'Daily' for ≥1 and <3", () => {
    expect(getFrequencyLabel(1)).toBe("Daily");
    expect(getFrequencyLabel(2.9)).toBe("Daily");
  });

  it("returns 'A few/week' for ≥0.15 and <1", () => {
    expect(getFrequencyLabel(0.15)).toBe("A few/week");
    expect(getFrequencyLabel(0.5)).toBe("A few/week");
    expect(getFrequencyLabel(0.99)).toBe("A few/week");
  });

  it("returns 'Weekly' for >0 and <0.15", () => {
    expect(getFrequencyLabel(0.01)).toBe("Weekly");
    expect(getFrequencyLabel(0.14)).toBe("Weekly");
  });

  it("returns null for 0", () => {
    expect(getFrequencyLabel(0)).toBeNull();
  });
});

describe("formatDailyReadTime", () => {
  it("returns null for 0 or negative", () => {
    expect(formatDailyReadTime(0)).toBeNull();
    expect(formatDailyReadTime(-1)).toBeNull();
  });

  it("returns '<1 min/day' for very small values", () => {
    expect(formatDailyReadTime(0.3)).toBe("<1 min/day");
  });

  it("returns rounded value for normal amounts", () => {
    expect(formatDailyReadTime(5.4)).toBe("~5 min/day");
    expect(formatDailyReadTime(12.7)).toBe("~13 min/day");
  });

  it("handles large values", () => {
    expect(formatDailyReadTime(120)).toBe("~120 min/day");
  });
});

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
    articlesPerDay: 1.5,
    estimatedReadMin: 2,
    dailyReadMin: 3,
    ...overrides,
  };
}

describe("totalSourceDailyOutput", () => {
  it("returns 0 for empty set", () => {
    const stats = { "https://a.com/feed": makeStat({ url: "https://a.com/feed", dailyReadMin: 5 }) };
    expect(totalSourceDailyOutput(new Set(), stats)).toBe(0);
  });

  it("sums matching URLs", () => {
    const stats = {
      "https://a.com/feed": makeStat({ url: "https://a.com/feed", dailyReadMin: 5 }),
      "https://b.com/feed": makeStat({ url: "https://b.com/feed", dailyReadMin: 3 }),
    };
    const selected = new Set(["https://a.com/feed", "https://b.com/feed"]);
    expect(totalSourceDailyOutput(selected, stats)).toBe(8);
  });

  it("ignores URLs without stats", () => {
    const stats = {
      "https://a.com/feed": makeStat({ url: "https://a.com/feed", dailyReadMin: 5 }),
    };
    const selected = new Set(["https://a.com/feed", "https://unknown.com/feed"]);
    expect(totalSourceDailyOutput(selected, stats)).toBe(5);
  });

  it("returns 0 when no stats exist", () => {
    expect(totalSourceDailyOutput(new Set(["https://a.com/feed"]), {})).toBe(0);
  });
});

describe("hasAnyStats", () => {
  it("returns false for empty object", () => {
    expect(hasAnyStats({})).toBe(false);
  });

  it("returns true when populated", () => {
    expect(hasAnyStats({ "https://a.com/feed": makeStat() })).toBe(true);
  });
});

// ── Step 5: Chip grid helpers ──

describe("getFrequencyBucket", () => {
  it("returns 'Prolific' for ≥3/day", () => {
    expect(getFrequencyBucket(3)).toBe("Prolific");
    expect(getFrequencyBucket(10)).toBe("Prolific");
  });

  it("returns 'Daily' for ≥1 and <3", () => {
    expect(getFrequencyBucket(1)).toBe("Daily");
    expect(getFrequencyBucket(2.99)).toBe("Daily");
  });

  it("returns 'A few/week' for ≥0.15 and <1", () => {
    expect(getFrequencyBucket(0.15)).toBe("A few/week");
    expect(getFrequencyBucket(0.99)).toBe("A few/week");
  });

  it("returns 'Weekly or less' for <0.15", () => {
    expect(getFrequencyBucket(0)).toBe("Weekly or less");
    expect(getFrequencyBucket(0.14)).toBe("Weekly or less");
  });
});

describe("formatChipReadTime", () => {
  it("returns null for 0 or negative", () => {
    expect(formatChipReadTime(0)).toBeNull();
    expect(formatChipReadTime(-1)).toBeNull();
  });

  it("returns '<1m' for very small values", () => {
    expect(formatChipReadTime(0.3)).toBe("<1m");
  });

  it("returns rounded value", () => {
    expect(formatChipReadTime(1)).toBe("1m");
    expect(formatChipReadTime(3.4)).toBe("3m");
    expect(formatChipReadTime(15)).toBe("15m");
  });
});
