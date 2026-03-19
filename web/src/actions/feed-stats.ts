"use server";

import { db } from "@/db";
import { feedStats } from "@/db/schema";
import type { FeedStat } from "@/types";

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
