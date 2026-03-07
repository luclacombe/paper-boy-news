"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  completeOnboarding,
  getOnboardingStatus,
} from "@/actions/onboarding";
import {
  getOnboardingStorage,
  clearOnboardingStorage,
} from "@/hooks/use-onboarding-state";
import type { OnboardingData } from "@/types";

export default function OnboardingCompletePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    async function save() {
      const stored = getOnboardingStorage();
      const hasValidData = stored && stored.device && stored.feeds.length > 0;

      // Defense-in-depth: if user is already onboarded and has no new
      // onboarding data, they're a returning user who signed in via the
      // onboarding page — redirect to dashboard
      const { isOnboarded } = await getOnboardingStatus();
      if (isOnboarded && !hasValidData) {
        clearOnboardingStorage();
        router.push("/dashboard");
        return;
      }

      if (!stored || !stored.device || stored.feeds.length === 0) {
        setError("missing");
        return;
      }

      const data: OnboardingData = {
        device: stored.device,
        deliveryMethod: stored.deliveryMethod,
        feeds: stored.feeds,
        title: stored.title || "The Morning Paper",
        readingTime: stored.readingTime,
        maxArticlesPerFeed: stored.maxArticlesPerFeed,
        includeImages: stored.includeImages,
        deliveryTime: stored.deliveryTime,
        timezone: stored.timezone,
        googleDriveFolder: stored.googleDriveFolder,
        kindleEmail: stored.kindleEmail,
        emailMethod: stored.emailMethod,
      };

      // Retry once in case the profile trigger hasn't fired yet
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          await completeOnboarding(data);
          clearOnboardingStorage();
          router.push("/dashboard");
          return;
        } catch (err) {
          if (
            attempt === 0 &&
            err instanceof Error &&
            err.message === "Profile not found"
          ) {
            await new Promise((r) => setTimeout(r, 1000));
            continue;
          }
          setError(
            err instanceof Error ? err.message : "Something went wrong"
          );
          return;
        }
      }
    }

    save();
  }, [router]);

  if (error === "missing") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-newsprint px-6">
        <div className="max-w-sm space-y-4 text-center">
          <h1 className="font-display text-xl font-bold text-ink">
            Settings Not Found
          </h1>
          <p className="font-body text-sm text-caption">
            We couldn&apos;t find your onboarding settings. This can happen if
            you used a different browser or cleared your data.
          </p>
          <Link
            href="/onboarding"
            className="inline-block font-body text-sm font-semibold text-ink underline hover:no-underline"
          >
            Start over
          </Link>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-newsprint px-6">
        <div className="max-w-sm space-y-4 text-center">
          <h1 className="font-display text-xl font-bold text-ink">
            Something Went Wrong
          </h1>
          <p className="font-body text-sm text-edition-red">{error}</p>
          <Link
            href="/onboarding"
            className="inline-block font-body text-sm font-semibold text-ink underline hover:no-underline"
          >
            Try again
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-newsprint px-6">
      <div className="space-y-4 text-center">
        <h1 className="font-display text-xl font-bold text-ink">
          Saving your settings...
        </h1>
        <p className="font-body text-sm text-caption">
          Setting up your newspaper. Just a moment.
        </p>
      </div>
    </div>
  );
}
