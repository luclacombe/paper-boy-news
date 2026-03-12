"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import {
  SettingsAccordion,
  type SettingsSection,
} from "@/components/settings-accordion";
import type { AuthProvider } from "@/actions/account";
import type { UserConfig, Feed, CatalogCategory, CatalogBundle } from "@/types";

interface SettingsClientProps {
  config: UserConfig;
  feeds: Feed[];
  categories: CatalogCategory[];
  bundles: CatalogBundle[];
  hasDrive: boolean;
  hasGmail: boolean;
  initialOpen: SettingsSection | null;
  userEmail: string;
  authProvider: AuthProvider;
  buildInProgress: boolean;
  opdsUrl: string | null;
}

export function SettingsClient({
  config,
  feeds,
  categories,
  bundles,
  hasDrive,
  hasGmail,
  initialOpen,
  userEmail,
  authProvider,
  buildInProgress,
  opdsUrl,
}: SettingsClientProps) {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <div className="space-y-6">
      {/* Compact settings header */}
      <div className="flex items-center justify-between border-b border-rule-gray pb-3">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 font-headline text-sm font-bold text-ink hover:text-caption transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Settings
        </Link>
        <button
          onClick={handleSignOut}
          className="font-mono text-sm text-caption transition-colors hover:text-ink"
        >
          Sign out
        </button>
      </div>

      <SettingsAccordion
        config={config}
        feeds={feeds}
        categories={categories}
        bundles={bundles}
        hasDrive={hasDrive}
        hasGmail={hasGmail}
        initialOpen={initialOpen}
        userEmail={userEmail}
        authProvider={authProvider}
        buildInProgress={buildInProgress}
        opdsUrl={opdsUrl}
      />
    </div>
  );
}
