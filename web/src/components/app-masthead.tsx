"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

interface AppMastheadProps {
  newspaperTitle: string;
  userEmail?: string;
}

function formatDate(): string {
  const now = new Date();
  return now.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function AppMasthead({ newspaperTitle, userEmail }: AppMastheadProps) {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <header className="mx-auto max-w-3xl px-6 pt-6">
      {/* Top double rule */}
      <div className="border-t-[3px] border-ink" />
      <div className="mt-[3px] border-t border-ink" />

      {/* Nameplate row */}
      <div className="flex items-center justify-between py-3">
        <div>
          <Link
            href="/dashboard"
            className="ink-bleed font-display text-xl font-black uppercase leading-none tracking-[0.15em] text-ink sm:text-2xl"
          >
            Paper Boy
          </Link>
          <p className="mt-0.5 font-mono text-[10px] text-caption">
            &ldquo;{newspaperTitle}&rdquo; &middot; {formatDate()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {userEmail && (
            <span className="hidden font-mono text-[10px] text-caption sm:inline truncate max-w-[180px]">
              {userEmail}
            </span>
          )}
          <button
            onClick={handleSignOut}
            className="font-mono text-sm text-caption transition-colors hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Bottom double rule */}
      <div className="border-t border-ink" />
      <div className="mt-[3px] border-t-[3px] border-ink" />
    </header>
  );
}
