"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getCatalogData, getBundleFeeds } from "@/actions/feed-catalog";
import { getAllFeedStats } from "@/actions/feed-stats";
import { useOnboardingState } from "@/hooks/use-onboarding-state";
import {
  readingTimeToArticleBudget,
  READING_TIME_OPTIONS,
  estimateTotalDailyReading,
  hasAnyStats,
} from "@/lib/reading-time";
import { FeedBadges, BundleReadTime } from "@/components/feed-badges";
import { BudgetBar } from "@/components/budget-bar";
import { NewspaperMasthead } from "@/components/newspaper-masthead";
import { StepIndicator } from "@/components/step-indicator";
import { DeviceCard } from "@/components/device-card";
import { BundleCard } from "@/components/bundle-card";
import { MarginDecoration } from "@/components/margin-decoration";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { DEVICES, DELIVERY_TIMES, TIMEZONES } from "@/lib/constants";
import type {
  CatalogBundle,
  CatalogCategory,
  CatalogFeed,
  FeedStat,
  Device,
  DeliveryMethod,
} from "@/types";

const TOTAL_STEPS = 4;

export default function OnboardingPage() {
  const router = useRouter();
  const { state, update, goToStep, loaded } = useOnboardingState();

  // Catalog data loaded from server
  const [bundles, setBundles] = useState<CatalogBundle[]>([]);
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [bundleFeedMap, setBundleFeedMap] = useState<
    Map<string, CatalogFeed[]>
  >(new Map());
  // Feed stats for reading time intelligence
  const [feedStats, setFeedStats] = useState<Record<string, FeedStat>>({});
  useEffect(() => {
    getAllFeedStats().then(setFeedStats);
  }, []);

  // Step 2: custom RSS
  const [customUrl, setCustomUrl] = useState("");
  const [customUrlError, setCustomUrlError] = useState<string | null>(null);

  // Step 4: account creation
  const [authMode, setAuthMode] = useState<"google" | "email" | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check if user is already signed in
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      setIsAuthenticated(!!user);
    });
  }, []);

  // Load catalog on mount
  useEffect(() => {
    getCatalogData().then(({ bundles: b, categories: c }) => {
      setBundles(b);
      setCategories(c);
      // Pre-load bundle feed mappings
      Promise.all(
        b.map(async (bundle) => {
          const feeds = await getBundleFeeds(bundle.name);
          return [bundle.name, feeds] as const;
        })
      ).then((entries) => {
        setBundleFeedMap(new Map(entries));
      });
    });
  }, []);

  // Derived state: which bundles are fully selected based on current feeds
  const selectedBundles = useMemo(() => {
    if (bundleFeedMap.size === 0) return new Set<string>();
    const feedUrls = new Set(state.feeds.map((f) => f.url));
    const result = new Set<string>();
    for (const [name, feeds] of bundleFeedMap) {
      if (feeds.length > 0 && feeds.every((f) => feedUrls.has(f.url))) {
        result.add(name);
      }
    }
    return result;
  }, [state.feeds, bundleFeedMap]);

  if (!loaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-newsprint page-vignette">
        <p className="font-body text-sm italic text-caption">
          Setting the type&hellip;
        </p>
      </div>
    );
  }

  // --- Helpers ---

  function toggleFeed(feed: { name: string; url: string; category: string }) {
    const exists = state.feeds.some((f) => f.url === feed.url);
    if (exists) {
      update({ feeds: state.feeds.filter((f) => f.url !== feed.url) });
    } else {
      update({ feeds: [...state.feeds, feed] });
    }
  }

  function toggleBundle(bundleName: string) {
    const feeds = bundleFeedMap.get(bundleName);
    if (!feeds) return;

    const isSelected = selectedBundles.has(bundleName);
    if (isSelected) {
      // Remove all bundle feeds
      const bundleUrls = new Set(feeds.map((f) => f.url));
      update({
        feeds: state.feeds.filter((f) => !bundleUrls.has(f.url)),
      });
    } else {
      // Add all bundle feeds that aren't already selected
      const existingUrls = new Set(state.feeds.map((f) => f.url));
      const newFeeds = feeds
        .filter((f) => !existingUrls.has(f.url))
        .map((f) => {
          // Find category for this feed
          const cat = categories.find((c) =>
            c.feeds.some((cf) => cf.url === f.url)
          );
          return { name: f.name, url: f.url, category: cat?.name ?? "" };
        });
      update({ feeds: [...state.feeds, ...newFeeds] });
    }
  }

  function addCustomFeed() {
    setCustomUrlError(null);
    const trimmed = customUrl.trim();
    if (!trimmed) return;
    if (
      !trimmed.startsWith("http://") &&
      !trimmed.startsWith("https://")
    ) {
      setCustomUrlError("URL must start with http:// or https://");
      return;
    }
    if (!trimmed.includes(".")) {
      setCustomUrlError("Please enter a valid URL");
      return;
    }
    if (state.feeds.some((f) => f.url === trimmed)) {
      setCustomUrlError("This feed is already added");
      return;
    }
    update({
      feeds: [
        ...state.feeds,
        { name: trimmed, url: trimmed, category: "Custom" },
      ],
    });
    setCustomUrl("");
  }

  function getDeliveryMethodsForDevice(
    device: Device | null
  ): { value: DeliveryMethod; label: string; description: string }[] {
    switch (device) {
      case "kobo":
        return [
          {
            value: "koreader",
            label: "Wireless sync",
            description:
              "Your paper downloads automatically over WiFi via KOReader — no cable needed",
          },
          {
            value: "google_drive",
            label: "Google Drive",
            description: "Auto-sync via Kobo's built-in Google Drive",
          },
          {
            value: "local",
            label: "Download",
            description: "Download EPUB and transfer manually",
          },
        ];
      case "kindle":
        return [
          {
            value: "email",
            label: "Send-to-Kindle",
            description: "Deliver via email to your Kindle",
          },
          {
            value: "koreader",
            label: "Wireless sync",
            description:
              "Auto-download via KOReader (requires jailbreak)",
          },
          {
            value: "local",
            label: "Download",
            description: "Download EPUB and transfer via USB",
          },
        ];
      case "remarkable":
        return [
          {
            value: "koreader",
            label: "Wireless sync",
            description:
              "Your paper downloads automatically over WiFi via KOReader — no cable needed",
          },
          {
            value: "local",
            label: "Download",
            description: "Download EPUB and transfer via USB or app",
          },
          {
            value: "email",
            label: "Email",
            description: "Send EPUB to an email address",
          },
        ];
      default:
        return [
          {
            value: "koreader",
            label: "Wireless sync",
            description:
              "Your paper downloads automatically over WiFi via KOReader — no cable needed",
          },
          {
            value: "local",
            label: "Download",
            description: "Download EPUB and transfer to your device",
          },
          {
            value: "email",
            label: "Email",
            description: "Send EPUB to an email address",
          },
        ];
    }
  }

  async function handleGoogleSignIn() {
    setAuthLoading(true);
    setAuthError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/api/auth/callback?next=/onboarding/complete`,
      },
    });
    if (error) {
      setAuthError(error.message);
      setAuthLoading(false);
    }
    // If successful, browser redirects — no need to handle further
  }

  async function handleEmailSignUp(e: React.FormEvent) {
    e.preventDefault();
    setAuthError(null);

    if (password !== confirmPassword) {
      setAuthError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setAuthError("Password must be at least 6 characters");
      return;
    }

    setAuthLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signUp({ email, password });

    if (error) {
      if (error.message.includes("already registered")) {
        setAuthError("already_registered");
      } else {
        setAuthError(error.message);
      }
      setAuthLoading(false);
    } else {
      router.push("/onboarding/complete");
    }
  }

  // --- Step renderers ---

  function renderStep1() {
    return (
      <div className="space-y-6">
        <div className="section-rule text-center">
          <h2 className="font-display text-2xl font-bold text-ink">
            Choose Your Device
          </h2>
          <p className="mt-1 font-body text-sm italic text-caption">
            Which e-reader will you use?
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {DEVICES.map((d) => (
            <DeviceCard
              key={d.value}
              device={d.value}
              label={d.label}
              selected={state.device === d.value}
              onClick={() => {
                update({ device: d.value });
                // Set default delivery method for device
                const methods = getDeliveryMethodsForDevice(d.value);
                update({ deliveryMethod: methods[0].value });
              }}
            />
          ))}
        </div>

        {state.device && (
          <p className="text-center font-body text-xs italic text-caption">
            {DEVICES.find((d) => d.value === state.device)?.description}
          </p>
        )}

        <div className="flex justify-between">
          <Button
            onClick={() => router.push("/")}
            variant="outline"
            className="letterpress font-body text-sm uppercase tracking-wider"
          >
            Back
          </Button>
          <Button
            onClick={() => goToStep(2)}
            disabled={!state.device}
            className="letterpress bg-ink font-body text-sm uppercase tracking-wider text-newsprint hover:bg-ink/90"
          >
            Continue
          </Button>
        </div>
      </div>
    );
  }

  function renderStep2() {
    const feedUrls = new Set(state.feeds.map((f) => f.url));
    const readingMinutes = Number(state.readingTime) || 15;
    const statsAvailable = hasAnyStats(feedStats);
    const estimatedMinutes = estimateTotalDailyReading(feedUrls, feedStats);

    return (
      <div className="space-y-6">
        <div className="section-rule text-center">
          <h2 className="font-display text-2xl font-bold text-ink">
            Pick Your Sources
          </h2>
          <p className="mt-1 font-body text-sm italic text-caption">
            Start with a bundle or pick individual feeds.
          </p>
        </div>

        {/* Inline reading time picker */}
        <div className="space-y-1.5">
          <h3 className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Reading Time
          </h3>
          <div className="flex border border-rule-gray">
            {READING_TIME_OPTIONS.map((minutes) => {
              const isSelected = readingMinutes === minutes;
              return (
                <button
                  key={minutes}
                  type="button"
                  onClick={() =>
                    update({
                      readingTime: String(minutes),
                      totalArticleBudget: readingTimeToArticleBudget(minutes),
                    })
                  }
                  className={cn(
                    "flex-1 py-2.5 font-mono text-xs transition-colors",
                    "border-r border-rule-gray last:border-r-0",
                    isSelected
                      ? "letterpress bg-ink font-bold text-newsprint"
                      : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
                  )}
                >
                  {minutes}m
                </button>
              );
            })}
          </div>
        </div>

        {/* Budget bar */}
        <BudgetBar
          estimatedMinutes={estimatedMinutes}
          budgetMinutes={readingMinutes}
          hasStats={statsAvailable}
        />

        {/* Bundles */}
        <div className="space-y-3">
          <h3 className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Starter Bundles
          </h3>
          <div className="grid gap-3 sm:grid-cols-3">
            {bundles.map((b) => (
              <div key={b.name} className="space-y-1">
                <BundleCard
                  name={b.name}
                  description={b.description}
                  selected={selectedBundles.has(b.name)}
                  onClick={() => toggleBundle(b.name)}
                />
                <div className="px-1">
                  <BundleReadTime
                    bundleName={b.name}
                    bundleFeedMap={bundleFeedMap}
                    statsMap={feedStats}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Individual feeds by category */}
        <div className="space-y-4">
          <h3 className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Individual Sources
          </h3>
          {categories.map((cat) => (
            <details key={cat.name} className="group">
              <summary className="newsprint-card flex cursor-pointer items-center justify-between overflow-hidden border border-rule-gray bg-card px-4 py-2.5 font-headline text-sm font-bold text-ink hover:bg-newsprint">
                <span>{cat.name}</span>
                <span className="font-mono text-xs text-caption">
                  {cat.feeds.filter((f) => feedUrls.has(f.url)).length}/
                  {cat.feeds.length}
                </span>
              </summary>
              <div className="mt-1 space-y-1 pl-1">
                {cat.feeds.map((feed) => (
                  <label
                    key={feed.id}
                    className="flex items-center gap-3 px-3 py-2 hover:bg-card"
                  >
                    <Checkbox
                      checked={feedUrls.has(feed.url)}
                      onCheckedChange={() =>
                        toggleFeed({
                          name: feed.name,
                          url: feed.url,
                          category: cat.name,
                        })
                      }
                      className="shrink-0"
                    />
                    <div className="min-w-0">
                      <span className="font-headline text-sm font-bold text-ink">
                        {feed.name}
                      </span>
                      <span className="ml-2 font-body text-xs italic text-caption">
                        {feed.description}
                      </span>
                    </div>
                    <FeedBadges url={feed.url} statsMap={feedStats} />
                  </label>
                ))}
              </div>
            </details>
          ))}
        </div>

        {/* Custom RSS */}
        <div className="ornamental-divider" />
        <div className="space-y-2">
          <h3 className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Custom RSS Feed
          </h3>
          <div className="flex gap-2">
            <Input
              type="url"
              value={customUrl}
              onChange={(e) => setCustomUrl(e.target.value)}
              placeholder="https://example.com/feed.xml"
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomFeed())}
            />
            <Button
              type="button"
              onClick={addCustomFeed}
              variant="outline"
              className="letterpress shrink-0 font-body text-sm"
            >
              Add
            </Button>
          </div>
          {customUrlError && (
            <p className="font-body text-xs italic text-edition-red">
              {customUrlError}
            </p>
          )}
        </div>

        {/* Summary */}
        <div className="newsprint-card overflow-hidden border border-rule-gray bg-card px-4 py-3">
          <p className="font-body text-sm text-ink">
            <span className="font-headline font-bold">{state.feeds.length}</span>{" "}
            source{state.feeds.length !== 1 ? "s" : ""} selected
            {statsAvailable && estimatedMinutes > 0 && (
              <span className="font-mono text-xs text-caption">
                {" "}· ~{Math.round(estimatedMinutes)} min/day
              </span>
            )}
          </p>
        </div>

        <div className="flex justify-between">
          <Button
            onClick={() => goToStep(1)}
            variant="outline"
            className="letterpress font-body text-sm uppercase tracking-wider"
          >
            Back
          </Button>
          <Button
            onClick={() => goToStep(3)}
            disabled={state.feeds.length === 0}
            className="letterpress bg-ink font-body text-sm uppercase tracking-wider text-newsprint hover:bg-ink/90"
          >
            Continue
          </Button>
        </div>
      </div>
    );
  }

  function renderStep3() {
    const methods = getDeliveryMethodsForDevice(state.device);
    const readingMinutes = Number(state.readingTime) || 15;

    return (
      <div className="space-y-6">
        <div className="section-rule text-center">
          <h2 className="font-display text-2xl font-bold text-ink">
            Delivery Settings
          </h2>
          <p className="mt-1 font-body text-sm italic text-caption">
            How and when should your newspaper arrive?
          </p>
        </div>

        {/* Delivery method */}
        <div className="space-y-3">
          <Label className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Delivery Method
          </Label>
          <RadioGroup
            value={state.deliveryMethod}
            onValueChange={(v) =>
              update({ deliveryMethod: v as DeliveryMethod })
            }
            className="space-y-2"
          >
            {methods.map((m) => (
              <label
                key={m.value}
                className="newsprint-card flex items-start gap-3 overflow-hidden border border-rule-gray bg-card px-4 py-3 hover:border-caption"
              >
                <RadioGroupItem value={m.value} className="mt-0.5" />
                <div>
                  <span className="font-headline text-sm font-bold text-ink">
                    {m.label}
                  </span>
                  <p className="font-body text-xs italic text-caption">
                    {m.description}
                  </p>
                </div>
              </label>
            ))}
          </RadioGroup>
        </div>

        {/* Kobo setup hint */}
        {state.device === "kobo" && state.deliveryMethod === "google_drive" && (
          <div className="border-l-2 border-rule-gray/50 pl-3">
            <p className="font-headline text-xs font-bold text-ink">
              Kobo setup
            </p>
            <p className="mt-1 font-body text-xs text-caption">
              Google Drive sync is supported on{" "}
              <strong>Kobo Forma, Sage, Elipsa, Elipsa 2E, and Libra Colour</strong>{" "}
              (firmware 4.37+). Clara models and older devices don&apos;t
              support it &mdash; choose Download instead.
            </p>
            <ol className="mt-1.5 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
              <li>
                On your Kobo, tap{" "}
                <strong>More &rarr; My Google Drive &rarr; Get Started</strong>
              </li>
              <li>Note the code shown on screen</li>
              <li>
                On a computer or phone, visit{" "}
                <strong>kobo.com/googledrive</strong> and enter the code
              </li>
              <li>
                Authorize Kobo to access the same Google account you&apos;ll
                connect after creating your account
              </li>
              <li>
                Paper Boy News will place your newspaper in the folder &mdash; sync
                your Kobo over Wi-Fi to download it
              </li>
            </ol>
          </div>
        )}

        {/* Kindle email (conditional) */}
        {state.deliveryMethod === "email" && state.device === "kindle" && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="font-headline text-sm text-ink">
                Kindle Email Address
              </Label>
              <Input
                type="email"
                value={state.kindleEmail}
                onChange={(e) => update({ kindleEmail: e.target.value })}
                placeholder="your-kindle@kindle.com"
              />
            </div>
            <div className="border-l-2 border-rule-gray/50 pl-3">
              <p className="font-headline text-xs font-bold text-ink">
                Kindle setup
              </p>
              <ol className="mt-1 list-decimal space-y-0.5 pl-4 font-body text-xs text-caption">
                <li>
                  Find your Kindle email: on your Kindle, go to{" "}
                  <strong>Settings &rarr; Your Account</strong> &mdash;
                  it ends in <strong>@kindle.com</strong>
                </li>
                <li>
                  You&apos;ll also need to approve the sender email in{" "}
                  <strong>
                    amazon.com &rarr; Manage Your Content and Devices &rarr;
                    Preferences &rarr; Personal Document Settings
                  </strong>
                </li>
              </ol>
              <p className="mt-1.5 font-body text-xs text-caption">
                Works with all Kindle devices and the Kindle app.
              </p>
            </div>
          </div>
        )}

        {/* Schedule */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
              Delivery Time
            </Label>
            <Select
              value={state.deliveryTime}
              onValueChange={(v) => update({ deliveryTime: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DELIVERY_TIMES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
              Timezone
            </Label>
            <Select
              value={state.timezone}
              onValueChange={(v) => update({ timezone: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMEZONES.map((tz) => (
                  <SelectItem key={tz.value} value={tz.value}>
                    {tz.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Newspaper settings */}
        <div className="ornamental-divider" />
        <div className="space-y-4">
          <h3 className="small-caps font-headline text-xs font-bold uppercase tracking-widest text-caption">
            Newspaper Settings
          </h3>
          <div className="space-y-2">
            <Label className="font-headline text-sm text-ink">
              Newspaper Title
            </Label>
            <Input
              value={state.title}
              onChange={(e) => update({ title: e.target.value })}
              placeholder="The Morning Paper"
            />
          </div>
          <div className="space-y-2">
            <Label className="font-headline text-sm text-ink">
              Reading Time
              <span className="ml-1 font-mono text-xs text-caption">
                (~{readingTimeToArticleBudget(readingMinutes)} articles total)
              </span>
            </Label>
            <div className="flex border border-rule-gray">
              {READING_TIME_OPTIONS.map((minutes) => {
                const isSelected = readingMinutes === minutes;
                return (
                  <button
                    key={minutes}
                    type="button"
                    onClick={() =>
                      update({
                        readingTime: String(minutes),
                        totalArticleBudget:
                          readingTimeToArticleBudget(minutes),
                      })
                    }
                    className={cn(
                      "flex-1 py-2.5 font-mono text-xs transition-colors",
                      "border-r border-rule-gray last:border-r-0",
                      isSelected
                        ? "letterpress bg-ink font-bold text-newsprint"
                        : "bg-card text-caption hover:bg-warm-gray hover:text-ink"
                    )}
                  >
                    {minutes}m
                  </button>
                );
              })}
            </div>
          </div>
          <label className="flex items-center gap-3">
            <Checkbox
              checked={state.includeImages}
              onCheckedChange={(checked) =>
                update({ includeImages: checked === true })
              }
            />
            <span className="font-body text-sm text-ink">
              Include images in articles
            </span>
          </label>
        </div>

        <div className="flex justify-between">
          <Button
            onClick={() => goToStep(2)}
            variant="outline"
            className="letterpress font-body text-sm uppercase tracking-wider"
          >
            Back
          </Button>
          <Button
            onClick={() => goToStep(4)}
            className="letterpress bg-ink font-body text-sm uppercase tracking-wider text-newsprint hover:bg-ink/90"
          >
            Continue
          </Button>
        </div>
      </div>
    );
  }

  function renderStep4() {
    // User is already signed in — just need to save settings
    if (isAuthenticated) {
      return (
        <div className="space-y-6">
          <div className="section-rule text-center">
            <h2 className="font-display text-2xl font-bold text-ink">
              You&rsquo;re All Set
            </h2>
            <p className="mt-1 font-body text-sm italic text-caption">
              You&rsquo;re signed in. Save your settings to start receiving your
              newspaper.
            </p>
          </div>

          <Button
            onClick={() => router.push("/onboarding/complete")}
            disabled={authLoading}
            className="letterpress w-full bg-ink font-body text-sm uppercase tracking-wider text-newsprint hover:bg-ink/90"
          >
            Complete Setup
          </Button>

          <div className="flex justify-start">
            <Button
              onClick={() => goToStep(3)}
              variant="outline"
              className="letterpress font-body text-sm uppercase tracking-wider"
            >
              Back
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div className="section-rule text-center">
          <h2 className="font-display text-2xl font-bold text-ink">
            Create Your Account
          </h2>
          <p className="mt-1 font-body text-sm italic text-caption">
            A free account lets us save your settings and deliver your newspaper
            automatically each morning.
          </p>
        </div>

        {/* Why create an account? */}
        <div className="newsprint-card overflow-hidden border border-rule-gray bg-card px-5 py-4 space-y-2.5">
          {(state.device === "kindle" || state.device === "kobo") &&
            state.deliveryMethod !== "local" && (
              <div className="flex items-start gap-2">
                <span className="mt-0.5 font-display text-sm text-edition-red">
                  *
                </span>
                <p className="font-body text-xs text-ink">
                  <span className="font-headline font-bold">
                    Recommended: Sign in with Google.
                  </span>{" "}
                  {state.device === "kindle"
                    ? "This lets Paper Boy News deliver your newspaper via Gmail\u2019s Send-to-Kindle service\u00a0\u2014 no app passwords needed."
                    : "This lets Paper Boy News sync your newspaper to Google Drive, where your Kobo picks it up automatically."}
                </p>
              </div>
            )}
          <div className="flex items-start gap-2">
            <span className="mt-0.5 font-display text-sm text-caption">
              &bull;
            </span>
            <p className="font-body text-xs text-caption">
              Accounts keep bots out and let us save your preferences and deliver
              your newspaper each morning. No spam, ever.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <span className="mt-0.5 font-display text-sm text-caption">
              &bull;
            </span>
            <p className="font-body text-xs text-caption">
              We only store what&rsquo;s needed to build and deliver your paper.
              No tracking, no ads, no data sharing.
            </p>
          </div>
        </div>

        {/* Google sign-in (primary) */}
        <Button
          onClick={handleGoogleSignIn}
          disabled={authLoading}
          className="letterpress flex w-full items-center justify-center gap-2 bg-ink font-body text-sm text-newsprint hover:bg-ink/90"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          {authLoading ? "Redirecting..." : "Continue with Google"}
        </Button>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-rule-gray" />
          <span className="small-caps font-body text-xs text-caption">or</span>
          <div className="h-px flex-1 bg-rule-gray" />
        </div>

        {/* Email/password form */}
        {authMode !== "email" ? (
          <button
            onClick={() => setAuthMode("email")}
            className="w-full font-body text-sm italic text-caption underline hover:text-ink"
          >
            Sign up with email and password
          </button>
        ) : (
          <form onSubmit={handleEmailSignUp} className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="ob-email" className="font-headline text-sm text-ink">
                Email
              </Label>
              <Input
                id="ob-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="ob-password"
                className="font-headline text-sm text-ink"
              >
                Password
              </Label>
              <Input
                id="ob-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="ob-confirm"
                className="font-headline text-sm text-ink"
              >
                Confirm Password
              </Label>
              <Input
                id="ob-confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your password"
                required
                autoComplete="new-password"
              />
            </div>
            <Button
              type="submit"
              disabled={authLoading}
              className="letterpress w-full bg-ink font-body text-sm uppercase tracking-wider text-newsprint hover:bg-ink/90"
            >
              {authLoading ? "Creating account..." : "Create Account"}
            </Button>
          </form>
        )}

        {authError && (
          <p className="text-center font-body text-sm italic text-edition-red">
            {authError === "already_registered" ? (
              <>
                This email is already registered.{" "}
                <Link
                  href="/login"
                  className="font-semibold text-ink underline hover:no-underline"
                >
                  Sign in instead
                </Link>
              </>
            ) : (
              authError
            )}
          </p>
        )}

        <p className="text-center font-body text-sm text-caption">
          Already have an account?{" "}
          <Link
            href="/login"
            className="underline hover:no-underline"
          >
            Sign in
          </Link>
        </p>

        <div className="flex justify-start">
          <Button
            onClick={() => goToStep(3)}
            variant="outline"
            className="letterpress font-body text-sm uppercase tracking-wider"
          >
            Back
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-newsprint page-vignette">
      <div className="mx-auto flex max-w-4xl px-6 py-12">
        {/* Left margin decoration */}
        <aside className="hidden w-24 shrink-0 lg:block" aria-hidden="true">
          <MarginDecoration side="left" />
        </aside>

        <main className="mx-auto flex w-full max-w-2xl flex-col min-h-[calc(100vh-6rem)] px-0 sm:px-6">
          {/* Masthead */}
          <NewspaperMasthead
            subtitle="Your morning edition, set in type."
            showDateline
          />

          {/* Step content with animated transitions */}
          <div className="mt-8 flex-1">
              <div
                key={state.step}
                className="animate-step-in"
              >
                {state.step === 1 && renderStep1()}
                {state.step === 2 && renderStep2()}
                {state.step === 3 && renderStep3()}
                {state.step === 4 && renderStep4()}
              </div>
          </div>

          {/* Step indicator (bottom) */}
          <div className="section-rule mt-8 mb-1 text-center">
            <StepIndicator
              currentStep={state.step}
              totalSteps={TOTAL_STEPS}
              maxStepVisited={state.maxStepVisited}
              onStepClick={goToStep}
            />
            <p className="mt-2 font-mono text-xs text-caption">
              Step {state.step} of {TOTAL_STEPS}
            </p>
          </div>
        </main>

        {/* Right margin decoration */}
        <aside className="hidden w-24 shrink-0 lg:block" aria-hidden="true">
          <MarginDecoration side="right" />
        </aside>
      </div>
    </div>
  );
}

