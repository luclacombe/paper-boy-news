import yaml from "js-yaml";
import fs from "fs";
import path from "path";
import type { CatalogBundle, CatalogCategory, CatalogFeed } from "@/types";

interface CatalogData {
  bundles: {
    name: string;
    description: string;
    feeds: string[];
  }[];
  categories: {
    name: string;
    feeds: {
      id: string;
      name: string;
      url: string;
      description: string;
    }[];
  }[];
}

let catalog: CatalogData | null = null;

function loadCatalog(): CatalogData {
  if (catalog) return catalog;
  const filePath = path.join(process.cwd(), "src/data/feed-catalog.yaml");
  const raw = fs.readFileSync(filePath, "utf-8");
  catalog = yaml.load(raw) as CatalogData;
  return catalog;
}

export function getBundles(): CatalogBundle[] {
  const data = loadCatalog();
  return data.bundles.map((b) => ({
    name: b.name,
    description: b.description,
    feeds: b.feeds,
  }));
}

export function getCategories(): CatalogCategory[] {
  const data = loadCatalog();
  return data.categories.map((c) => ({
    name: c.name,
    feeds: c.feeds.map((f) => ({
      id: f.id,
      name: f.name,
      url: f.url,
      description: f.description,
    })),
  }));
}

export function getAllFeeds(): Map<string, CatalogFeed> {
  const data = loadCatalog();
  const map = new Map<string, CatalogFeed>();
  for (const category of data.categories) {
    for (const feed of category.feeds) {
      map.set(feed.id, {
        id: feed.id,
        name: feed.name,
        url: feed.url,
        description: feed.description,
      });
    }
  }
  return map;
}

export function getFeedsForBundle(bundleName: string): CatalogFeed[] {
  const bundles = getBundles();
  const bundle = bundles.find((b) => b.name === bundleName);
  if (!bundle) return [];

  const allFeeds = getAllFeeds();
  return bundle.feeds
    .map((id) => allFeeds.get(id))
    .filter((f): f is CatalogFeed => f !== undefined);
}

/**
 * Human-readable description of the user's feed selection.
 * Mirrors web/services/feed_catalog.py::describe_feed_selection()
 */
export function describeFeedSelection(feedUrls: Set<string>): string {
  if (feedUrls.size === 0) return "No sources selected";

  const bundles = getBundles();
  const allFeeds = getAllFeeds();

  // Build a set of URLs per bundle
  const bundleUrlSets = new Map<string, Set<string>>();
  for (const bundle of bundles) {
    const urls = new Set<string>();
    for (const feedId of bundle.feeds) {
      const feed = allFeeds.get(feedId);
      if (feed) urls.add(feed.url);
    }
    bundleUrlSets.set(bundle.name, urls);
  }

  // Find which bundles are fully contained in the selection
  const matchedBundles: string[] = [];
  const coveredUrls = new Set<string>();
  for (const [name, urls] of bundleUrlSets) {
    const allIncluded = [...urls].every((url) => feedUrls.has(url));
    if (allIncluded) {
      matchedBundles.push(name);
      for (const url of urls) coveredUrls.add(url);
    }
  }

  const extraCount = feedUrls.size - coveredUrls.size;

  if (matchedBundles.length === 0) {
    return `${feedUrls.size} source${feedUrls.size === 1 ? "" : "s"}`;
  }

  const bundleStr = matchedBundles.join(" and ");
  if (extraCount > 0) {
    return `${bundleStr} + ${extraCount} extra source${extraCount === 1 ? "" : "s"}`;
  }
  return bundleStr;
}

/**
 * Basic RSS URL validation.
 * Mirrors web/services/feed_catalog.py::validate_rss_url()
 */
export function validateRssUrl(url: string): boolean {
  if (!url) return false;
  const trimmed = url.trim().toLowerCase();
  return (
    (trimmed.startsWith("http://") || trimmed.startsWith("https://")) &&
    trimmed.includes(".")
  );
}
