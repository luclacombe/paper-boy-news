import { describe, it, expect } from "vitest";
import { groupByCategory, groupByFrequency } from "@/components/feed-chip-grid";
import type { CatalogCategory, FeedStat } from "@/types";

const categories: CatalogCategory[] = [
  {
    name: "News",
    feeds: [
      { id: "bbc", name: "BBC", url: "https://bbc.com/feed", description: "BBC news" },
      { id: "nyt", name: "NYT", url: "https://nyt.com/feed", description: "NYT news" },
    ],
  },
  {
    name: "Tech",
    feeds: [
      { id: "ars", name: "Ars Technica", url: "https://ars.com/feed", description: "Tech analysis" },
    ],
  },
  {
    name: "Science",
    feeds: [
      { id: "nature", name: "Nature", url: "https://nature.com/feed", description: "Research" },
      { id: "quanta", name: "Quanta", url: "https://quanta.com/feed", description: "Math + physics" },
    ],
  },
];

function makeStat(url: string, articlesPerDay: number, dailyReadMin: number): FeedStat {
  return {
    url,
    name: "",
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
    articlesPerDay,
    estimatedReadMin: 2,
    dailyReadMin,
  };
}

// ── groupByCategory ──

describe("groupByCategory", () => {
  it("returns all categories when no filter", () => {
    const groups = groupByCategory(categories, null);
    expect(groups).toHaveLength(3);
    expect(groups.map((g) => g.label)).toEqual(["News", "Tech", "Science"]);
  });

  it("filters to a single category", () => {
    const groups = groupByCategory(categories, "Tech");
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Tech");
    expect(groups[0].feeds).toHaveLength(1);
    expect(groups[0].feeds[0].name).toBe("Ars Technica");
  });

  it("returns empty when filter matches no category", () => {
    const groups = groupByCategory(categories, "Sports");
    expect(groups).toHaveLength(0);
  });

  it("attaches category name to each feed", () => {
    const groups = groupByCategory(categories, null);
    expect(groups[0].feeds[0].category).toBe("News");
    expect(groups[1].feeds[0].category).toBe("Tech");
  });
});

// ── groupByFrequency ──

describe("groupByFrequency", () => {
  const stats: Record<string, FeedStat> = {
    "https://bbc.com/feed": makeStat("https://bbc.com/feed", 5, 10),      // Prolific
    "https://nyt.com/feed": makeStat("https://nyt.com/feed", 1.5, 5),     // Daily
    "https://ars.com/feed": makeStat("https://ars.com/feed", 0.5, 2),     // A few/week
    // nature + quanta have no stats → "No data"
  };

  it("groups feeds into frequency buckets", () => {
    const groups = groupByFrequency(categories, stats, null);
    const labels = groups.map((g) => g.label);
    expect(labels).toContain("Prolific");
    expect(labels).toContain("Daily");
    expect(labels).toContain("A few/week");
    expect(labels).toContain("No data");
  });

  it("puts prolific feeds in correct bucket", () => {
    const groups = groupByFrequency(categories, stats, null);
    const prolific = groups.find((g) => g.label === "Prolific");
    expect(prolific?.feeds.map((f) => f.name)).toEqual(["BBC"]);
  });

  it("puts feeds without stats in 'No data'", () => {
    const groups = groupByFrequency(categories, stats, null);
    const noData = groups.find((g) => g.label === "No data");
    expect(noData?.feeds.map((f) => f.name)).toEqual(["Nature", "Quanta"]);
  });

  it("filters to a single frequency bucket", () => {
    const groups = groupByFrequency(categories, stats, "Prolific");
    expect(groups).toHaveLength(1);
    expect(groups[0].feeds).toHaveLength(1);
    expect(groups[0].feeds[0].name).toBe("BBC");
  });

  it("preserves original category on each feed", () => {
    const groups = groupByFrequency(categories, stats, null);
    const prolific = groups.find((g) => g.label === "Prolific");
    expect(prolific?.feeds[0].category).toBe("News");
  });

  it("puts all feeds in 'No data' when stats are empty", () => {
    const groups = groupByFrequency(categories, {}, null);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("No data");
    expect(groups[0].feeds).toHaveLength(5);
  });

  it("skips empty buckets", () => {
    // All feeds are prolific
    const allProlific: Record<string, FeedStat> = {};
    for (const cat of categories) {
      for (const feed of cat.feeds) {
        allProlific[feed.url] = makeStat(feed.url, 5, 10);
      }
    }
    const groups = groupByFrequency(categories, allProlific, null);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Prolific");
  });
});
