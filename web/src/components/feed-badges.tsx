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

/** Aggregate reading time badge for a bundle card. */
export function BundleReadTime({
  bundleName,
  bundleFeedMap,
  statsMap,
}: BundleReadTimeProps) {
  const feeds = bundleFeedMap.get(bundleName);
  if (!feeds) return null;

  let total = 0;
  for (const feed of feeds) {
    const stat = statsMap[feed.url];
    if (stat) total += stat.dailyReadMin;
  }

  if (total === 0) return null;

  return (
    <span className="font-mono text-[10px] text-caption">
      ~{Math.round(total)} min/day
    </span>
  );
}
