import { describe, it, expect } from "vitest";
import {
  getSourcesSummary,
  getDeliverySummary,
  getScheduleSummary,
  getPaperSummary,
  getAccountSummary,
} from "@/components/settings-accordion";
import type { Feed } from "@/types";

function makeFeed(overrides: Partial<Feed> = {}): Feed {
  return {
    id: "1",
    userId: "u1",
    name: "Test Feed",
    url: "https://example.com/feed",
    category: "Tech",
    position: 0,
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

describe("getSourcesSummary", () => {
  it("returns 'No sources yet' for empty feeds", () => {
    expect(getSourcesSummary([])).toBe("No sources yet");
  });

  it("returns singular forms for 1 source, 1 category", () => {
    const feeds = [makeFeed({ category: "Tech" })];
    expect(getSourcesSummary(feeds)).toBe("1 source · 1 category");
  });

  it("returns plural forms for multiple sources and categories", () => {
    const feeds = [
      makeFeed({ id: "1", category: "Tech" }),
      makeFeed({ id: "2", category: "Tech" }),
      makeFeed({ id: "3", category: "World" }),
    ];
    expect(getSourcesSummary(feeds)).toBe("3 sources · 2 categories");
  });

  it("ignores feeds with empty category", () => {
    const feeds = [
      makeFeed({ id: "1", category: "Tech" }),
      makeFeed({ id: "2", category: "" }),
    ];
    expect(getSourcesSummary(feeds)).toBe("2 sources · 1 category");
  });

  it("uses override counts when provided", () => {
    const feeds = [makeFeed({ category: "Tech" })];
    expect(getSourcesSummary(feeds, { count: 5, categoryCount: 3 })).toBe(
      "5 sources · 3 categories"
    );
  });

  it("returns 'No sources yet' when override count is 0", () => {
    const feeds = [makeFeed({ category: "Tech" })];
    expect(getSourcesSummary(feeds, { count: 0, categoryCount: 0 })).toBe(
      "No sources yet"
    );
  });
});

describe("getDeliverySummary", () => {
  it("shows Kindle + Send-to-Kindle for kindle/email", () => {
    expect(getDeliverySummary("kindle", "email")).toBe(
      "Kindle · Send-to-Kindle"
    );
  });

  it("shows Kobo + Google Drive", () => {
    expect(getDeliverySummary("kobo", "google_drive")).toBe(
      "Kobo · Google Drive"
    );
  });

  it("shows Other + Download", () => {
    expect(getDeliverySummary("other", "local")).toBe("Other · Download");
  });

  it("shows reMarkable + Email", () => {
    expect(getDeliverySummary("remarkable", "email")).toBe(
      "reMarkable · Email"
    );
  });
});

describe("getScheduleSummary", () => {
  it("formats time and timezone labels", () => {
    expect(getScheduleSummary("07:00", "America/New_York")).toBe(
      "7:00 AM · US Eastern (EST)"
    );
  });

  it("normalizes legacy timezone values", () => {
    expect(getScheduleSummary("07:00", "US/Eastern")).toBe(
      "7:00 AM · US Eastern (EST)"
    );
  });

  it("falls back to raw values for unknown entries", () => {
    expect(getScheduleSummary("03:00", "Mars/Olympus")).toBe(
      "03:00 · Mars/Olympus"
    );
  });
});

describe("getPaperSummary", () => {
  it("formats title, reading time, and images on", () => {
    expect(
      getPaperSummary({ title: "The Morning Paper", readingTime: 15, includeImages: true })
    ).toBe('"The Morning Paper" · ~15 min · Images on');
  });

  it("shows Images off when disabled", () => {
    expect(
      getPaperSummary({ title: "Daily", readingTime: 5, includeImages: false })
    ).toBe('"Daily" · ~5 min · Images off');
  });

  it("shows Untitled for empty title", () => {
    expect(
      getPaperSummary({ title: "", readingTime: 10, includeImages: true })
    ).toBe('"Untitled" · ~10 min · Images on');
  });
});

describe("getAccountSummary", () => {
  it("shows email and Google provider", () => {
    expect(getAccountSummary("user@gmail.com", "google")).toBe(
      "user@gmail.com · Google"
    );
  });

  it("shows email and Email provider", () => {
    expect(getAccountSummary("user@example.com", "email")).toBe(
      "user@example.com · Email"
    );
  });
});
