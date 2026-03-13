"use server";

import { db } from "@/db";
import { feedStats } from "@/db/schema";
import { inArray } from "drizzle-orm";
import type { FeedStat } from "@/types";

/**
 * Fetch feed stats for a list of feed URLs.
 * Returns stats keyed by URL for easy lookup.
 */
export async function getFeedStats(
  urls: string[]
): Promise<Record<string, FeedStat>> {
  if (urls.length === 0) return {};

  const rows = await db
    .select({
      url: feedStats.url,
      name: feedStats.name,
      observedAt: feedStats.observedAt,
      sampleCount: feedStats.sampleCount,
      totalEntries: feedStats.totalEntries,
      fresh24h: feedStats.fresh24h,
      fresh48h: feedStats.fresh48h,
      attempted: feedStats.attempted,
      extracted: feedStats.extracted,
      avgWordCount: feedStats.avgWordCount,
      medianWordCount: feedStats.medianWordCount,
      avgImages: feedStats.avgImages,
      articlesPerDay: feedStats.articlesPerDay,
      estimatedReadMin: feedStats.estimatedReadMin,
      dailyReadMin: feedStats.dailyReadMin,
    })
    .from(feedStats)
    .where(inArray(feedStats.url, urls));

  const result: Record<string, FeedStat> = {};
  for (const row of rows) {
    result[row.url] = {
      ...row,
      observedAt: row.observedAt.toISOString(),
    };
  }
  return result;
}

/**
 * Fetch all feed stats. Used for catalog display where all stats are needed.
 */
export async function getAllFeedStats(): Promise<Record<string, FeedStat>> {
  const rows = await db
    .select({
      url: feedStats.url,
      name: feedStats.name,
      observedAt: feedStats.observedAt,
      sampleCount: feedStats.sampleCount,
      totalEntries: feedStats.totalEntries,
      fresh24h: feedStats.fresh24h,
      fresh48h: feedStats.fresh48h,
      attempted: feedStats.attempted,
      extracted: feedStats.extracted,
      avgWordCount: feedStats.avgWordCount,
      medianWordCount: feedStats.medianWordCount,
      avgImages: feedStats.avgImages,
      articlesPerDay: feedStats.articlesPerDay,
      estimatedReadMin: feedStats.estimatedReadMin,
      dailyReadMin: feedStats.dailyReadMin,
    })
    .from(feedStats);

  const result: Record<string, FeedStat> = {};
  for (const row of rows) {
    result[row.url] = {
      ...row,
      observedAt: row.observedAt.toISOString(),
    };
  }
  return result;
}
