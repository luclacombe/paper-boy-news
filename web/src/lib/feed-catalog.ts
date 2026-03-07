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

