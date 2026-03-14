"use client";

import { useState, useMemo } from "react";
import { FeedChip } from "@/components/feed-chip";
import { getFrequencyBucket, FREQUENCY_BUCKETS } from "@/lib/reading-time";
import { cn } from "@/lib/utils";
import type { CatalogCategory, CatalogFeed, FeedStat } from "@/types";

type GroupMode = "category" | "frequency";

interface FeedChipGridProps {
  categories: CatalogCategory[];
  feedStats: Record<string, FeedStat>;
  selectedUrls: Set<string>;
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
  onToggleFeed,
}: FeedChipGridProps) {
  const [groupMode, setGroupMode] = useState<GroupMode>("category");
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  // Reset filter when switching group mode
  function handleGroupModeChange(mode: GroupMode) {
    setGroupMode(mode);
    setActiveFilter(null);
  }

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
      {/* Group mode toggle */}
      <div className="flex items-center justify-end gap-1 font-mono text-[10px] text-caption">
        <button
          type="button"
          onClick={() => handleGroupModeChange("category")}
          className={cn(
            "px-1.5 py-0.5 transition-colors",
            groupMode === "category" ? "font-bold text-ink" : "hover:text-ink"
          )}
        >
          By category
        </button>
        <span className="text-rule-gray">|</span>
        <button
          type="button"
          onClick={() => handleGroupModeChange("frequency")}
          className={cn(
            "px-1.5 py-0.5 transition-colors",
            groupMode === "frequency" ? "font-bold text-ink" : "hover:text-ink"
          )}
        >
          By frequency
        </button>
      </div>

      {/* Filter bar */}
      <div className="scrollbar-hide -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        <button
          type="button"
          onClick={() => setActiveFilter(null)}
          className={cn(
            "shrink-0 rounded-sm border px-2.5 py-1 font-mono text-[11px] transition-colors",
            activeFilter === null
              ? "border-ink bg-ink text-newsprint"
              : "border-rule-gray bg-card text-caption hover:border-caption hover:text-ink"
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
              "shrink-0 whitespace-nowrap rounded-sm border px-2.5 py-1 font-mono text-[11px] transition-colors",
              activeFilter === label
                ? "border-ink bg-ink text-newsprint"
                : "border-rule-gray bg-card text-caption hover:border-caption hover:text-ink"
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
                    dailyReadMin={stat ? stat.dailyReadMin : null}
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
