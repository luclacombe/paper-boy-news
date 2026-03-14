"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { setFeeds } from "@/actions/feeds";
import { getBundleFeeds } from "@/actions/feed-catalog";
import { BundleCard } from "@/components/bundle-card";
import { FeedChipGrid, type GroupMode } from "@/components/feed-chip-grid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  readingTimeToArticleBudget,
  recommendedSourceRange,
  READING_TIME_OPTIONS,
  totalSourceDailyOutput,
  avgEstimatedReadMin,
  hasAnyStats,
} from "@/lib/reading-time";
import { BundleReadTime } from "@/components/feed-badges";
import { BudgetBar } from "@/components/budget-bar";
import { cn } from "@/lib/utils";
import type { Feed, CatalogCategory, CatalogBundle, CatalogFeed, FeedStat } from "@/types";

// Pending addition — not yet saved to DB
interface PendingAdd {
  name: string;
  url: string;
  category: string;
}

interface SourcesSectionProps {
  feeds: Feed[];
  categories: CatalogCategory[];
  bundles: CatalogBundle[];
  feedStats: Record<string, FeedStat>;
  readingTime: number;
  onReadingTimeChange: (minutes: number) => void;
  onDirtyChange: (dirty: boolean) => void;
  onEffectiveCountChange?: (count: number, categoryCount: number) => void;
  saveRef: React.RefObject<(() => Promise<void>) | null>;
}

export function SourcesSection({
  feeds,
  categories,
  bundles,
  feedStats,
  readingTime,
  onReadingTimeChange,
  onDirtyChange,
  onEffectiveCountChange,
  saveRef,
}: SourcesSectionProps) {
  const router = useRouter();
  const [customUrl, setCustomUrl] = useState("");
  const [customUrlError, setCustomUrlError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [bundleFeedMap, setBundleFeedMap] = useState<Map<string, CatalogFeed[]>>(new Map());
  const [groupMode, setGroupMode] = useState<GroupMode>("category");

  // Pending changes (local only, not yet persisted)
  const [pendingAdds, setPendingAdds] = useState<PendingAdd[]>([]);
  const [pendingRemoves, setPendingRemoves] = useState<Set<string>>(new Set());

  // The "effective" set of feed URLs = server feeds minus removes plus adds
  const effectiveUrls = useMemo(() => {
    const urls = new Set(
      feeds.filter((f) => !pendingRemoves.has(f.id)).map((f) => f.url)
    );
    for (const add of pendingAdds) urls.add(add.url);
    return urls;
  }, [feeds, pendingAdds, pendingRemoves]);

  // Dirty = any pending changes
  const dirty = pendingAdds.length > 0 || pendingRemoves.size > 0;

  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  // Report effective count to parent for summary accuracy
  useEffect(() => {
    if (!onEffectiveCountChange) return;
    // Compute effective categories from the effective URL set
    const effectiveFeeds = [
      ...feeds.filter((f) => !pendingRemoves.has(f.id)),
      ...pendingAdds,
    ];
    const cats = new Set(effectiveFeeds.map((f) => f.category).filter(Boolean));
    onEffectiveCountChange(effectiveUrls.size, cats.size);
  }, [effectiveUrls, feeds, pendingAdds, pendingRemoves, onEffectiveCountChange]);

  // Pre-load bundle feed mappings
  useEffect(() => {
    Promise.all(
      bundles.map(async (bundle) => {
        const feeds = await getBundleFeeds(bundle.name);
        return [bundle.name, feeds] as const;
      })
    ).then((entries) => {
      setBundleFeedMap(new Map(entries));
    });
  }, [bundles]);

  // Derived: which bundles are fully selected (including pending changes)
  const selectedBundles = useMemo(() => {
    if (bundleFeedMap.size === 0) return new Set<string>();
    const result = new Set<string>();
    for (const [name, bundleFeeds] of bundleFeedMap) {
      if (bundleFeeds.length > 0 && bundleFeeds.every((f) => effectiveUrls.has(f.url))) {
        result.add(name);
      }
    }
    return result;
  }, [bundleFeedMap, effectiveUrls]);

  // Toggle a single catalog feed
  function handleToggleCatalogFeed(feed: {
    name: string;
    url: string;
    category: string;
  }) {
    if (effectiveUrls.has(feed.url)) {
      // Remove: either cancel a pending add, or mark existing feed for removal
      const pendingIdx = pendingAdds.findIndex((a) => a.url === feed.url);
      if (pendingIdx >= 0) {
        setPendingAdds((prev) => prev.filter((_, i) => i !== pendingIdx));
      } else {
        const existing = feeds.find((f) => f.url === feed.url);
        if (existing) {
          setPendingRemoves((prev) => new Set(prev).add(existing.id));
        }
      }
    } else {
      // Add: either cancel a pending remove, or add as pending
      const existing = feeds.find((f) => f.url === feed.url);
      if (existing && pendingRemoves.has(existing.id)) {
        setPendingRemoves((prev) => {
          const next = new Set(prev);
          next.delete(existing.id);
          return next;
        });
      } else {
        setPendingAdds((prev) => [...prev, { name: feed.name, url: feed.url, category: feed.category }]);
      }
    }
  }

  // Toggle a bundle
  function handleToggleBundle(bundleName: string) {
    const bundleFeeds = bundleFeedMap.get(bundleName);
    if (!bundleFeeds) return;

    if (selectedBundles.has(bundleName)) {
      // Remove all bundle feeds
      for (const bf of bundleFeeds) {
        const pendingIdx = pendingAdds.findIndex((a) => a.url === bf.url);
        if (pendingIdx >= 0) {
          setPendingAdds((prev) => prev.filter((_, i) => i !== pendingIdx));
        } else {
          const existing = feeds.find((f) => f.url === bf.url);
          if (existing) {
            setPendingRemoves((prev) => new Set(prev).add(existing.id));
          }
        }
      }
    } else {
      // Add all bundle feeds that aren't already effective
      const categoryMap = new Map<string, string>();
      for (const cat of categories) {
        for (const f of cat.feeds) {
          categoryMap.set(f.url, cat.name);
        }
      }
      for (const bf of bundleFeeds) {
        if (!effectiveUrls.has(bf.url)) {
          const existing = feeds.find((f) => f.url === bf.url);
          if (existing && pendingRemoves.has(existing.id)) {
            setPendingRemoves((prev) => {
              const next = new Set(prev);
              next.delete(existing.id);
              return next;
            });
          } else {
            setPendingAdds((prev) => [...prev, {
              name: bf.name,
              url: bf.url,
              category: categoryMap.get(bf.url) ?? "General",
            }]);
          }
        }
      }
    }
  }

  // Custom feed — validate then add to pending
  async function handleAddCustomFeed() {
    setCustomUrlError(null);
    const trimmed = customUrl.trim();
    if (!trimmed) return;
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
      setCustomUrlError("URL must start with http:// or https://");
      return;
    }
    if (effectiveUrls.has(trimmed)) {
      setCustomUrlError("This feed is already added");
      return;
    }

    setValidating(true);
    try {
      const res = await fetch("/api/feeds/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });
      const data = await res.json();

      if (!data.valid) {
        setCustomUrlError(data.error ?? "Invalid feed URL");
        setValidating(false);
        return;
      }

      setPendingAdds((prev) => [...prev, {
        name: data.name ?? trimmed,
        url: trimmed,
        category: "Custom",
      }]);
      setCustomUrl("");
    } catch {
      setCustomUrlError("Failed to validate feed");
    } finally {
      setValidating(false);
    }
  }

  // Persist all pending changes in a single bulk operation
  const persistChanges = useCallback(async () => {
    if (!dirty) return;
    try {
      const finalFeeds = [
        ...feeds
          .filter((f) => !pendingRemoves.has(f.id))
          .map((f) => ({ name: f.name, url: f.url, category: f.category })),
        ...pendingAdds,
      ];
      await setFeeds(finalFeeds);
      setPendingAdds([]);
      setPendingRemoves(new Set());
      router.refresh();
    } catch {
      toast.error("Failed to save sources");
    }
  }, [dirty, feeds, pendingAdds, pendingRemoves, router]);

  // Expose save function to parent (for auto-save on collapse)
  useEffect(() => {
    saveRef.current = persistChanges;
  }, [persistChanges, saveRef]);

  // Effective feed count + recommendation
  const effectiveCount = effectiveUrls.size;
  const budget = readingTimeToArticleBudget(readingTime);
  const [recMin, recMax] = recommendedSourceRange(budget);

  const statsAvailable = hasAnyStats(feedStats);
  const sourceOutput = totalSourceDailyOutput(effectiveUrls, feedStats);
  const avgArticleMin = avgEstimatedReadMin(effectiveUrls, feedStats);

  return (
    <div className="space-y-4">
      {/* Inline reading time picker */}
      <div className="space-y-1.5">
        <h3 className="font-headline text-sm font-bold text-ink">
          Reading time
        </h3>
        <div className="flex border border-rule-gray">
          {READING_TIME_OPTIONS.map((minutes) => {
            const isSelected = readingTime === minutes;
            return (
              <button
                key={minutes}
                type="button"
                onClick={() => onReadingTimeChange(minutes)}
                className={cn(
                  "flex-1 py-2.5 font-mono text-xs transition-colors",
                  "border-r border-rule-gray last:border-r-0",
                  isSelected
                    ? "letterpress bg-ink font-bold text-newsprint"
                    : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
                )}
              >
                {minutes}m
              </button>
            );
          })}
        </div>
      </div>

      {/* Budget bar */}
      <BudgetBar
        sourceOutputMinutes={sourceOutput}
        budgetMinutes={readingTime}
        sourceCount={effectiveCount}
        avgArticleMin={avgArticleMin}
        hasStats={statsAvailable}
      />

      {/* Quick add bundles */}
      {bundles.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-headline text-sm font-bold text-ink">
            Quick add
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {bundles.map((bundle) => (
              <div key={bundle.name} className="flex flex-col">
                <BundleCard
                  name={bundle.name}
                  description={bundle.description}
                  selected={selectedBundles.has(bundle.name)}
                  onClick={() => handleToggleBundle(bundle.name)}
                />
                <div className="px-1 pt-1">
                  <BundleReadTime
                    bundleName={bundle.name}
                    bundleFeedMap={bundleFeedMap}
                    statsMap={feedStats}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edit your sources (catalog) */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <h3 className="font-headline text-sm font-bold text-ink">
            Edit your sources
            <span className="ml-2 font-mono text-xs font-normal text-caption">
              {statsAvailable
                ? `${effectiveCount} selected`
                : `${effectiveCount} selected · ${recMin}–${recMax} recommended for ${readingTime}m`}
            </span>
          </h3>
          <div className="flex shrink-0 items-center rounded-sm border border-rule-gray">
            <button
              type="button"
              onClick={() => setGroupMode("category")}
              className={cn(
                "px-2.5 py-1 font-mono text-[11px] transition-colors",
                "border-r border-rule-gray",
                groupMode === "category"
                  ? "bg-ink font-bold text-newsprint"
                  : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
              )}
            >
              By category
            </button>
            <button
              type="button"
              onClick={() => setGroupMode("frequency")}
              className={cn(
                "px-2.5 py-1 font-mono text-[11px] transition-colors",
                groupMode === "frequency"
                  ? "bg-ink font-bold text-newsprint"
                  : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
              )}
            >
              By frequency
            </button>
          </div>
        </div>
        <FeedChipGrid
          categories={categories}
          feedStats={feedStats}
          selectedUrls={effectiveUrls}
          groupMode={groupMode}
          onToggleFeed={handleToggleCatalogFeed}
        />
      </div>

      {/* Custom RSS */}
      <div className="space-y-1.5">
        <Label className="font-headline text-sm text-ink">
          Paste a feed URL
        </Label>
        <div className="flex gap-2">
          <Input
            type="url"
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            placeholder="https://example.com/feed.xml"
            onKeyDown={(e) =>
              e.key === "Enter" &&
              (e.preventDefault(), handleAddCustomFeed())
            }
          />
          <Button
            type="button"
            onClick={handleAddCustomFeed}
            variant="outline"
            disabled={validating}
            className="letterpress shrink-0 font-body text-sm"
          >
            {validating ? "Checking..." : "Add"}
          </Button>
        </div>
        {customUrlError && (
          <p className="font-body text-xs text-edition-red">
            {customUrlError}
          </p>
        )}
      </div>

      {/* Pending changes indicator */}
      {dirty && (
        <p className="font-mono text-xs text-building">
          {pendingAdds.length > 0 &&
            `+${pendingAdds.length} to add`}
          {pendingAdds.length > 0 && pendingRemoves.size > 0 && " · "}
          {pendingRemoves.size > 0 &&
            `${pendingRemoves.size} to remove`}
        </p>
      )}
    </div>
  );
}
