"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-newsprint px-6">
      <div className="max-w-sm space-y-6 text-center">
        <h1 className="font-display text-2xl font-black uppercase tracking-wider text-ink">
          Something went wrong
        </h1>
        <p className="font-body text-sm text-caption">
          We hit an unexpected error. You can try again or sign out and start
          fresh.
        </p>
        <div className="flex flex-col gap-3">
          <Button
            onClick={reset}
            className="w-full bg-ink font-body text-sm font-semibold uppercase tracking-wider text-newsprint hover:bg-ink/90"
          >
            Try Again
          </Button>
          <Button
            onClick={handleSignOut}
            variant="outline"
            className="w-full font-body text-sm font-semibold uppercase tracking-wider"
          >
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  );
}
