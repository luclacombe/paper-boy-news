"use client";

import { getFrequencyLabel, formatDailyReadTime } from "@/lib/reading-time";
import type { FeedStat, CatalogFeed } from "@/types";

interface FeedBadgesProps {
  url: string;
  statsMap: Record<string, FeedStat>;
}

/** Inline frequency + reading time badges for a single feed row. */
export function FeedBadges({ url, statsMap }: FeedBadgesProps) {
  const stat = statsMap[url];
  if (!stat) return null;

  const freq = getFrequencyLabel(stat.articlesPerDay);
  const time = formatDailyReadTime(stat.dailyReadMin);

  if (!freq && !time) return null;

  return (
    <span className="ml-auto flex shrink-0 items-center gap-1.5">
      {freq && (
        <span className="font-mono text-[10px] text-caption">{freq}</span>
      )}
      {time && (
        <span className="font-mono text-[10px] text-caption">{time}</span>
      )}
    </span>
  );
}

interface BundleReadTimeProps {
  bundleName: string;
  bundleFeedMap: Map<string, CatalogFeed[]>;
  statsMap: Record<string, FeedStat>;
}

/** Aggregate reading time badge for a bundle card: source count + avg per-article time. */
export function BundleReadTime({
  bundleName,
  bundleFeedMap,
  statsMap,
}: BundleReadTimeProps) {
  const feeds = bundleFeedMap.get(bundleName);
  if (!feeds || feeds.length === 0) return null;

  let totalReadMin = 0;
  let withStats = 0;
  for (const feed of feeds) {
    const stat = statsMap[feed.url];
    if (stat && stat.estimatedReadMin > 0) {
      totalReadMin += stat.estimatedReadMin;
      withStats++;
    }
  }

  const avgReadMin = withStats > 0 ? Math.round(totalReadMin / withStats) : 0;

  return (
    <span className="font-mono text-[10px] text-caption">
      {feeds.length} sources{avgReadMin > 0 ? ` · ~${avgReadMin}m/article` : ""}
    </span>
  );
}
