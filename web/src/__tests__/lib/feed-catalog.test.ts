import { describe, it, expect } from "vitest";
import {
  getAllCatalogFeedUrls,
  getAllFeeds,
  getBundles,
  getCategories,
  getFeedsForBundle,
} from "@/lib/feed-catalog";

describe("feed catalog integrity", () => {
  it("every bundle feed id resolves to a catalog feed", () => {
    // getFeedsForBundle() silently drops unknown ids, so a renamed or removed
    // feed would quietly shrink a starter bundle without this check.
    const allFeeds = getAllFeeds();
    for (const bundle of getBundles()) {
      for (const id of bundle.feeds) {
        expect(allFeeds.has(id), `bundle "${bundle.name}" references unknown feed "${id}"`).toBe(true);
      }
      expect(getFeedsForBundle(bundle.name)).toHaveLength(bundle.feeds.length);
    }
  });

  it("feed ids and urls are unique", () => {
    const feeds = getCategories().flatMap((c) => c.feeds);
    const ids = feeds.map((f) => f.id);
    const urls = feeds.map((f) => f.url);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(urls).size).toBe(urls.length);
    expect(getAllCatalogFeedUrls().size).toBe(urls.length);
  });
});
