import { getUserConfig } from "@/actions/user-config";
import { getFeeds, cleanOrphanedFeeds } from "@/actions/feeds";
import { getCatalogData } from "@/actions/feed-catalog";
import { getAllFeedStats } from "@/actions/feed-stats";
import { hasDriveScope } from "@/actions/google-oauth";
import { hasActiveBuild } from "@/actions/delivery-history";
import { getAuthUser } from "@/lib/auth";
import { getEditionDate } from "@/lib/edition-date";
import { SettingsClient } from "@/components/settings-client";
import { redirect } from "next/navigation";
import type { AuthProvider } from "@/actions/account";
import type { SettingsSection } from "@/components/settings-accordion";

const VALID_SECTIONS: SettingsSection[] = [
  "sources",
  "delivery",
  "schedule",
  "paper",
  "account",
];

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [config, feeds, catalogData, feedStats, hasDrive, authUser, params] =
    await Promise.all([
      getUserConfig(),
      getFeeds(),
      getCatalogData(),
      getAllFeedStats(),
      hasDriveScope(),
      getAuthUser(),
      searchParams,
      cleanOrphanedFeeds(),
    ]);

  if (!config) redirect("/login");

  const editionDate = getEditionDate(config.timezone);
  const buildInProgress = await hasActiveBuild(editionDate);

  const userEmail = authUser?.email ?? "";
  const authProvider: AuthProvider =
    authUser?.app_metadata?.provider === "google" ? "google" : "email";

  const opdsUrl = config.opdsToken
    ? `${process.env.NEXT_PUBLIC_APP_URL}/api/opds/${config.opdsToken}/feed.xml`
    : null;

  const openParam = typeof params.open === "string" ? params.open : null;
  const initialOpen =
    openParam && VALID_SECTIONS.includes(openParam as SettingsSection)
      ? (openParam as SettingsSection)
      : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <SettingsClient
        config={config}
        feeds={feeds}
        categories={catalogData.categories}
        bundles={catalogData.bundles}
        feedStats={feedStats}
        hasDrive={hasDrive}
        initialOpen={initialOpen}
        userEmail={userEmail}
        authProvider={authProvider}
        buildInProgress={buildInProgress}
        opdsUrl={opdsUrl}
      />
    </main>
  );
}
