"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronRight } from "lucide-react";
import { addFeed, removeFeed } from "@/actions/feeds";
import { getBundleFeeds } from "@/actions/feed-catalog";
import { BundleCard } from "@/components/bundle-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { Feed, CatalogCategory, CatalogBundle, CatalogFeed } from "@/types";

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
  onDirtyChange: (dirty: boolean) => void;
  saveRef: React.RefObject<(() => Promise<void>) | null>;
}

export function SourcesSection({
  feeds,
  categories,
  bundles,
  onDirtyChange,
  saveRef,
}: SourcesSectionProps) {
  const router = useRouter();
  const [customUrl, setCustomUrl] = useState("");
  const [customUrlError, setCustomUrlError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [bundleFeedMap, setBundleFeedMap] = useState<Map<string, CatalogFeed[]>>(new Map());

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

  // Persist all pending changes
  const persistChanges = useCallback(async () => {
    if (!dirty) return;
    try {
      // Removals first
      for (const feedId of pendingRemoves) {
        await removeFeed(feedId);
      }
      // Then additions
      for (const add of pendingAdds) {
        await addFeed(add.name, add.url, add.category);
      }
      setPendingAdds([]);
      setPendingRemoves(new Set());
      router.refresh();
    } catch {
      toast.error("Failed to save sources");
    }
  }, [dirty, pendingAdds, pendingRemoves, router]);

  // Expose save function to parent (for auto-save on collapse)
  useEffect(() => {
    saveRef.current = persistChanges;
  }, [persistChanges, saveRef]);

  // Effective feed count
  const effectiveCount = effectiveUrls.size;

  return (
    <div className="space-y-4">
      {/* Quick add bundles */}
      {bundles.length > 0 && (
        <div className="space-y-2">
          <h3 className="font-headline text-sm font-bold text-ink">
            Quick add
          </h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {bundles.map((bundle) => (
              <BundleCard
                key={bundle.name}
                name={bundle.name}
                description={bundle.description}
                selected={selectedBundles.has(bundle.name)}
                onClick={() => handleToggleBundle(bundle.name)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Edit your sources (catalog) */}
      <div className="space-y-2">
        <h3 className="font-headline text-sm font-bold text-ink">
          Edit your sources
          <span className="ml-2 font-mono text-xs font-normal text-caption">
            {effectiveCount} selected
          </span>
        </h3>
        {categories.map((cat) => {
          const selectedCount = cat.feeds.filter((f) => effectiveUrls.has(f.url)).length;
          return (
            <details key={cat.name} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between border border-rule-gray bg-card px-4 py-2.5 font-headline text-sm font-bold text-ink hover:bg-warm-gray [&::-webkit-details-marker]:hidden">
                <span className="flex items-center gap-2">
                  <ChevronRight className="h-3 w-3 text-caption transition-transform duration-200 group-open:rotate-90" />
                  {cat.name}
                </span>
                <span className="font-mono text-xs text-caption">
                  {selectedCount}/{cat.feeds.length}
                </span>
              </summary>
              <div className="mt-1 space-y-1 pl-1">
                {cat.feeds.map((feed) => (
                  <label
                    key={feed.id}
                    className="flex items-start gap-3 px-3 py-2 hover:bg-card"
                  >
                    <Checkbox
                      checked={effectiveUrls.has(feed.url)}
                      onCheckedChange={() =>
                        handleToggleCatalogFeed({
                          name: feed.name,
                          url: feed.url,
                          category: cat.name,
                        })
                      }
                      className="mt-0.5"
                    />
                    <div>
                      <span className="font-headline text-sm font-bold text-ink">
                        {feed.name}
                      </span>
                      <span className="ml-2 font-body text-xs text-caption">
                        {feed.description}
                      </span>
                    </div>
                  </label>
                ))}
              </div>
            </details>
          );
        })}
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
