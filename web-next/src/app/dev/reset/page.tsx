"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { clearOnboardingStorage } from "@/hooks/use-onboarding-state";

const isDev = process.env.NODE_ENV === "development";

export default function DevResetPage() {
  const [status, setStatus] = useState<"resetting" | "done" | "error">(
    isDev ? "resetting" : "error"
  );

  useEffect(() => {
    if (!isDev) return;

    async function reset() {
      try {
        clearOnboardingStorage();

        const supabase = createClient();
        await supabase.auth.signOut();

        setStatus("done");

        setTimeout(() => {
          window.location.href = "/login";
        }, 1500);
      } catch {
        setStatus("error");
      }
    }

    reset();
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center font-mono text-sm">
        {status === "resetting" && <p>Resetting client state...</p>}
        {status === "done" && (
          <>
            <p>Cleared localStorage + signed out.</p>
            <p className="mt-1 text-muted-foreground">
              Redirecting to /login...
            </p>
          </>
        )}
        {status === "error" && (
          <p className="text-destructive">
            Dev reset is only available in development mode.
          </p>
        )}
      </div>
    </div>
  );
}
