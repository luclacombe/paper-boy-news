import { getAllFeedStats } from "@/actions/feed-stats";
import {
  getBundles,
  getCategories,
  getFeedsForBundle,
} from "@/lib/feed-catalog";
import { OnboardingWizard } from "@/components/onboarding-wizard";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const [feedStats, bundles, categories] = await Promise.all([
    getAllFeedStats(),
    Promise.resolve(getBundles()),
    Promise.resolve(getCategories()),
  ]);

  // Pre-compute bundle → feeds map (avoids N client-side round trips)
  const bundleFeedEntries = bundles.map((b) => [
    b.name,
    getFeedsForBundle(b.name),
  ] as const);
  const bundleFeedMap: Record<string, { id: string; name: string; url: string; description: string }[]> =
    Object.fromEntries(bundleFeedEntries);

  return (
    <OnboardingWizard
      feedStats={feedStats}
      bundles={bundles}
      categories={categories}
      bundleFeedMap={bundleFeedMap}
    />
  );
}
