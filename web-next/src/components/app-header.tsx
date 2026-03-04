"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Home", href: "/dashboard" },
  { label: "Sources", href: "/sources" },
  { label: "Delivery", href: "/delivery" },
  { label: "Editions", href: "/editions" },
];

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <header className="mx-auto max-w-2xl px-6 pt-6">
      {/* Title */}
      <div className="mb-3 flex items-center justify-between">
        <Link
          href="/dashboard"
          className="font-display text-lg font-black uppercase tracking-[0.15em] text-ink"
        >
          Paper Boy
        </Link>
        <button
          onClick={handleSignOut}
          className="font-body text-xs text-caption transition-colors hover:text-ink"
        >
          Sign out
        </button>
      </div>

      {/* Navigation tabs */}
      <nav className="flex gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "px-3 py-2 font-body text-sm transition-colors",
                isActive
                  ? "border-b-[3px] border-edition-red font-semibold text-ink"
                  : "text-caption hover:text-ink"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Rule */}
      <div className="mt-0 h-px bg-rule-gray" />
    </header>
  );
}
