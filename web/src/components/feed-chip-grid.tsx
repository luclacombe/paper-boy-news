"use client";

import { useState, useMemo } from "react";
import { FeedChip } from "@/components/feed-chip";
import { getFrequencyBucket, FREQUENCY_BUCKETS } from "@/lib/reading-time";
import { cn } from "@/lib/utils";
import type { CatalogCategory, CatalogFeed, FeedStat } from "@/types";

export type GroupMode = "category" | "frequency";

interface FeedChipGridProps {
  categories: CatalogCategory[];
  feedStats: Record<string, FeedStat>;
  selectedUrls: Set<string>;
  groupMode: GroupMode;
  onToggleFeed: (feed: {
    name: string;
    url: string;
    category: string;
  }) => void;
}

interface FeedGroup {
  label: string;
  feeds: (CatalogFeed & { category: string })[];
}

/** Group feeds by category, optionally filtering to one category. */
export function groupByCategory(
  categories: CatalogCategory[],
  activeFilter: string | null
): FeedGroup[] {
  return categories
    .filter((cat) => !activeFilter || cat.name === activeFilter)
    .map((cat) => ({
      label: cat.name,
      feeds: cat.feeds.map((f) => ({ ...f, category: cat.name })),
    }))
    .filter((g) => g.feeds.length > 0);
}

/** Group feeds by frequency bucket, optionally filtering to one bucket. */
export function groupByFrequency(
  categories: CatalogCategory[],
  feedStats: Record<string, FeedStat>,
  activeFilter: string | null
): FeedGroup[] {
  const bucketMap = new Map<string, (CatalogFeed & { category: string })[]>();
  for (const bucket of FREQUENCY_BUCKETS) {
    bucketMap.set(bucket, []);
  }

  for (const cat of categories) {
    for (const feed of cat.feeds) {
      const stat = feedStats[feed.url];
      const bucket =
        stat && stat.articlesPerDay > 0
          ? getFrequencyBucket(stat.articlesPerDay)
          : "No data";
      bucketMap.get(bucket)?.push({ ...feed, category: cat.name });
    }
  }

  return [...FREQUENCY_BUCKETS]
    .filter((bucket) => !activeFilter || bucket === activeFilter)
    .map((bucket) => ({
      label: bucket,
      feeds: bucketMap.get(bucket) ?? [],
    }))
    .filter((g) => g.feeds.length > 0);
}

export function FeedChipGrid({
  categories,
  feedStats,
  selectedUrls,
  groupMode,
  onToggleFeed,
}: FeedChipGridProps) {
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  // Filter pill labels
  const filterLabels = useMemo(() => {
    if (groupMode === "category") {
      return categories.map((c) => c.name);
    }
    return [...FREQUENCY_BUCKETS].filter((bucket) => {
      // Only show buckets that have feeds
      for (const cat of categories) {
        for (const feed of cat.feeds) {
          const stat = feedStats[feed.url];
          const feedBucket =
            stat && stat.articlesPerDay > 0
              ? getFrequencyBucket(stat.articlesPerDay)
              : "No data";
          if (feedBucket === bucket) return true;
        }
      }
      return false;
    });
  }, [groupMode, categories, feedStats]);

  // Grouped feeds
  const groups = useMemo(() => {
    if (groupMode === "category") {
      return groupByCategory(categories, activeFilter);
    }
    return groupByFrequency(categories, feedStats, activeFilter);
  }, [groupMode, categories, feedStats, activeFilter]);

  const showHeaders = activeFilter === null && groups.length > 1;

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="scrollbar-hide -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        <button
          type="button"
          onClick={() => setActiveFilter(null)}
          className={cn(
            "shrink-0 border-b-2 px-2 py-0.5 font-body text-[10px] uppercase tracking-wider transition-colors",
            activeFilter === null
              ? "border-ink text-ink"
              : "border-transparent text-caption hover:text-ink"
          )}
        >
          All
        </button>
        {filterLabels.map((label) => (
          <button
            key={label}
            type="button"
            onClick={() =>
              setActiveFilter((prev) => (prev === label ? null : label))
            }
            className={cn(
              "shrink-0 whitespace-nowrap border-b-2 px-2 py-0.5 font-body text-[10px] uppercase tracking-wider transition-colors",
              activeFilter === label
                ? "border-ink text-ink"
                : "border-transparent text-caption hover:text-ink"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Chip grid */}
      <div className="space-y-3">
        {groups.map((group) => (
          <div key={group.label}>
            {showHeaders && (
              <h4 className="mb-1.5 font-headline text-xs font-bold text-caption">
                {group.label}
              </h4>
            )}
            <div className="flex flex-wrap gap-1.5">
              {group.feeds.map((feed) => {
                const stat = feedStats[feed.url];
                return (
                  <FeedChip
                    key={feed.id}
                    name={feed.name}
                    description={feed.description}
                    estimatedReadMin={stat ? stat.estimatedReadMin : null}
                    selected={selectedUrls.has(feed.url)}
                    onChange={() =>
                      onToggleFeed({
                        name: feed.name,
                        url: feed.url,
                        category: feed.category,
                      })
                    }
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
