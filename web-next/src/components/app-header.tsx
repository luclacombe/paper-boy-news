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
        <div className="flex flex-col items-start">
          <Link
            href="/dashboard"
            className="ink-bleed font-display text-xl font-black uppercase leading-none tracking-[0.2em] text-ink"
          >
            Paper Boy
          </Link>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-caption">
            Morning Edition
          </p>
        </div>
        <button
          onClick={handleSignOut}
          className="small-caps font-mono text-xs text-caption transition-colors hover:text-ink"
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
                "small-caps px-3 py-2 font-headline text-sm tracking-wider transition-colors",
                isActive
                  ? "border-b-[3px] border-edition-red font-bold text-ink"
                  : "text-caption hover:text-ink"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Double rule */}
      <div className="section-rule mt-0 border-t-0" />
    </header>
  );
}
