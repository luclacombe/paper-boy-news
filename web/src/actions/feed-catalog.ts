"use server";

import {
  getBundles,
  getCategories,
  getFeedsForBundle,
} from "@/lib/feed-catalog";
import type { CatalogBundle, CatalogCategory, CatalogFeed } from "@/types";

export async function getCatalogData(): Promise<{
  bundles: CatalogBundle[];
  categories: CatalogCategory[];
}> {
  return { bundles: getBundles(), categories: getCategories() };
}

export async function getBundleFeeds(
  bundleName: string
): Promise<CatalogFeed[]> {
  return getFeedsForBundle(bundleName);
}
