"use client";

import { useState, useEffect, useRef, useTransition, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ChevronRight } from "lucide-react";
import { showSaveToast } from "@/components/save-toast";
import { updateUserConfig } from "@/actions/user-config";
import { setFeeds } from "@/actions/feeds";
import { SourcesSection } from "@/components/settings/sources-section";
import {
  DeliverySection,
  type DeliveryValues,
} from "@/components/settings/delivery-section";
import {
  ScheduleSection,
  type ScheduleValues,
} from "@/components/settings/schedule-section";
import {
  PaperSection,
  type PaperValues,
} from "@/components/settings/paper-section";
import { AccountSection } from "@/components/settings/account-section";
import { Button } from "@/components/ui/button";
import { LoadingDots } from "@/components/ui/loading-dots";
import { readingTimeToArticleBudget } from "@/lib/reading-time";
import { DEVICES, DELIVERY_TIMES, TIMEZONES, normalizeTimezone } from "@/lib/constants";
import type { AuthProvider } from "@/actions/account";
import type {
  UserConfig,
  Feed,
  CatalogCategory,
  CatalogBundle,
  FeedStat,
  Device,
  DeliveryMethod,
} from "@/types";

// ─── Types ───────────────────────────────────────────────────────

export type SettingsSection = "sources" | "delivery" | "schedule" | "paper" | "account";

const SECTION_TOAST: Record<SettingsSection, string> = {
  sources: "Sources",
  delivery: "Delivery",
  schedule: "Schedule",
  paper: "Your paper",
  account: "Account",
};

const SECTION_COLORS: Record<SettingsSection, string> = {
  sources: "border-l-edition-red",
  delivery: "border-l-ink",
  schedule: "border-l-building",
  paper: "border-l-delivered",
  account: "border-l-caption",
};

// ─── Summary generators (pure, exported for testing) ─────────────

export function getSourcesSummary(
  feeds: Feed[],
  overrideCounts?: { count: number; categoryCount: number }
): string {
  const count = overrideCounts?.count ?? feeds.length;
  const categoryCount =
    overrideCounts?.categoryCount ??
    new Set(feeds.map((f) => f.category).filter(Boolean)).size;
  if (count === 0) return "No sources yet";
  return `${count} source${count !== 1 ? "s" : ""} · ${categoryCount} categor${categoryCount !== 1 ? "ies" : "y"}`;
}

export function getDeliverySummary(
  device: Device,
  method: DeliveryMethod
): string {
  const deviceLabel =
    DEVICES.find((d) => d.value === device)?.label ?? device;

  const methodLabels: Record<string, Record<DeliveryMethod, string>> = {
    kindle: { email: "Send-to-Kindle", local: "Download", google_drive: "Google Drive", koreader: "Wireless sync" },
    kobo: { email: "Email", local: "Download", google_drive: "Google Drive", koreader: "Wireless sync" },
    remarkable: { email: "Email", local: "Download", google_drive: "Google Drive", koreader: "Wireless sync" },
    other: { email: "Email", local: "Download", google_drive: "Google Drive", koreader: "Wireless sync" },
  };

  const methodLabel = methodLabels[device]?.[method] ?? method;
  return `${deviceLabel} · ${methodLabel}`;
}

export function getScheduleSummary(time: string, timezone: string): string {
  const timeLabel =
    DELIVERY_TIMES.find((t) => t.value === time)?.label ?? time;
  const normalized = normalizeTimezone(timezone);
  const tzLabel =
    TIMEZONES.find((tz) => tz.value === normalized)?.label ?? timezone;
  return `${timeLabel} · ${tzLabel}`;
}

export function getPaperSummary(values: PaperValues): string {
  const title = values.title || "Untitled";
  return `"${title}" · ~${values.readingTime} min`;
}

export function getAccountSummary(
  email: string,
  provider: AuthProvider
): string {
  const providerLabel = provider === "google" ? "Google" : "Email";
  return `${email} · ${providerLabel}`;
}

// ─── Component ───────────────────────────────────────────────────

interface SettingsAccordionProps {
  config: UserConfig;
  feeds: Feed[];
  categories: CatalogCategory[];
  bundles: CatalogBundle[];
  feedStats: Record<string, FeedStat>;
  hasDrive: boolean;
  initialOpen: SettingsSection | null;
  userEmail: string;
  authProvider: AuthProvider;
  buildInProgress: boolean;
  opdsUrl: string | null;
}

export function SettingsAccordion({
  config,
  feeds,
  categories,
  bundles,
  feedStats,
  hasDrive,
  initialOpen,
  userEmail,
  authProvider,
  buildInProgress,
  opdsUrl,
}: SettingsAccordionProps) {
  const router = useRouter();
  const [isSaving, startSave] = useTransition();
  const [openSection, setOpenSection] = useState<SettingsSection | null>(
    initialOpen
  );

  // ── Per-section state + saved snapshots for dirty tracking ──

  const initDelivery: DeliveryValues = {
    device: config.device,
    deliveryMethod: config.deliveryMethod,
    recipientEmail: config.recipientEmail,
    googleDriveFolder: config.googleDriveFolder,
  };

  // OPDS URL tracked separately (immediate actions, not batch-saved)
  const [currentOpdsUrl, setCurrentOpdsUrl] = useState(opdsUrl ?? "");

  const initSchedule: ScheduleValues = {
    deliveryTime: config.deliveryTime,
    timezone: config.timezone,
  };

  const initPaper: PaperValues = {
    title: config.title,
    readingTime: Number(config.readingTime) || 15,
  };

  const [deliveryValues, setDeliveryValues] =
    useState<DeliveryValues>(initDelivery);
  const [deliverySaved, setDeliverySaved] =
    useState<DeliveryValues>(initDelivery);

  const [scheduleValues, setScheduleValues] =
    useState<ScheduleValues>(initSchedule);
  const [scheduleSaved, setScheduleSaved] =
    useState<ScheduleValues>(initSchedule);

  const [paperValues, setPaperValues] = useState<PaperValues>(initPaper);
  const [paperSaved, setPaperSaved] = useState<PaperValues>(initPaper);

  // ── Sources dirty state + save ref ──

  const [sourcesDirty, setSourcesDirty] = useState(false);
  const sourcesSaveRef = useRef<(() => Promise<void>) | null>(null);
  const [effectiveCounts, setEffectiveCounts] = useState<{
    count: number;
    categoryCount: number;
  } | null>(null);

  // Track whether reading time was changed from Sources section
  const [paperDirtyFromSources, setPaperDirtyFromSources] = useState(false);

  const handleReadingTimeChange = useCallback((minutes: number) => {
    setPaperValues(prev => ({ ...prev, readingTime: minutes }));
    setPaperDirtyFromSources(true);
  }, []);

  const handleSourcesDirtyChange = useCallback((dirty: boolean) => {
    setSourcesDirty(dirty);
  }, []);

  const handleEffectiveCountChange = useCallback(
    (count: number, categoryCount: number) => {
      setEffectiveCounts({ count, categoryCount });
    },
    []
  );

  // ── Dirty checks ──

  function isDirty(section: SettingsSection): boolean {
    switch (section) {
      case "sources":
        return sourcesDirty || paperDirtyFromSources;
      case "delivery":
        return JSON.stringify(deliveryValues) !== JSON.stringify(deliverySaved);
      case "schedule":
        return JSON.stringify(scheduleValues) !== JSON.stringify(scheduleSaved);
      case "paper":
        return JSON.stringify(paperValues) !== JSON.stringify(paperSaved);
      default:
        return false;
    }
  }

  // ── Save helpers ──

  function getFieldsForSection(
    section: SettingsSection
  ): Partial<UserConfig> {
    switch (section) {
      case "delivery":
        return {
          device: deliveryValues.device,
          deliveryMethod: deliveryValues.deliveryMethod,
          recipientEmail: deliveryValues.recipientEmail,
          googleDriveFolder: deliveryValues.googleDriveFolder,
        };
      case "schedule":
        return {
          deliveryTime: scheduleValues.deliveryTime,
          timezone: scheduleValues.timezone,
        };
      case "paper":
        return {
          title: paperValues.title,
          readingTime: String(paperValues.readingTime),
          totalArticleBudget: readingTimeToArticleBudget(
            paperValues.readingTime
          ),
        };
      default:
        return {};
    }
  }

  function updateSavedSnapshot(section: SettingsSection) {
    switch (section) {
      case "delivery":
        setDeliverySaved({ ...deliveryValues });
        break;
      case "schedule":
        setScheduleSaved({ ...scheduleValues });
        break;
      case "paper":
        setPaperSaved({ ...paperValues });
        break;
    }
  }

  /** Save with toast + undo (used by both explicit save and auto-save on collapse) */
  function saveWithUndo(section: SettingsSection) {
    // Capture pre-save snapshot for undo
    const prevDelivery = { ...deliverySaved };
    const prevSchedule = { ...scheduleSaved };
    const prevPaper = { ...paperSaved };
    // For sources: snapshot the entire server-side feed list
    const prevFeeds = feeds.map((f) => ({
      name: f.name,
      url: f.url,
      category: f.category,
    }));

    startSave(async () => {
      try {
        if (section === "sources") {
          await sourcesSaveRef.current?.();
          // Also save paper config if reading time was changed from Sources
          if (paperDirtyFromSources) {
            await updateUserConfig(getFieldsForSection("paper"));
            updateSavedSnapshot("paper");
            setPaperDirtyFromSources(false);
          }
        } else {
          await updateUserConfig(getFieldsForSection(section));
          updateSavedSnapshot(section);
        }
        router.refresh();
        showSaveToast(`${SECTION_TOAST[section]} updated`, () =>
          handleUndo(section, prevDelivery, prevSchedule, prevPaper, prevFeeds)
        );
      } catch {
        toast.error(`Failed to save ${SECTION_TOAST[section].toLowerCase()}`);
      }
    });
  }

  /** Undo a save — revert to previous values and persist */
  function handleUndo(
    section: SettingsSection,
    prevDelivery: DeliveryValues,
    prevSchedule: ScheduleValues,
    prevPaper: PaperValues,
    prevFeeds: { name: string; url: string; category: string }[],
  ) {
    startSave(async () => {
      try {
        switch (section) {
          case "sources":
            await setFeeds(prevFeeds);
            break;
          case "delivery":
            setDeliveryValues(prevDelivery);
            setDeliverySaved(prevDelivery);
            await updateUserConfig({
              device: prevDelivery.device,
              deliveryMethod: prevDelivery.deliveryMethod,
              recipientEmail: prevDelivery.recipientEmail,
              googleDriveFolder: prevDelivery.googleDriveFolder,
            });
            break;
          case "schedule":
            setScheduleValues(prevSchedule);
            setScheduleSaved(prevSchedule);
            await updateUserConfig({
              deliveryTime: prevSchedule.deliveryTime,
              timezone: prevSchedule.timezone,
            });
            break;
          case "paper":
            setPaperValues(prevPaper);
            setPaperSaved(prevPaper);
            await updateUserConfig({
              title: prevPaper.title,
              readingTime: String(prevPaper.readingTime),
              totalArticleBudget: readingTimeToArticleBudget(prevPaper.readingTime),
            });
            break;
        }
        router.refresh();
        showSaveToast(`${SECTION_TOAST[section]} reverted`);
      } catch {
        toast.error("Failed to undo");
      }
    });
  }

  /** Explicit save — save + toast + collapse */
  function handleExplicitSave(section: SettingsSection) {
    saveWithUndo(section);
    setOpenSection(null);
  }

  // ── Section toggle (with auto-save safety net) ──

  function handleToggle(section: SettingsSection) {
    // Auto-save the currently open section if dirty
    if (openSection && isDirty(openSection)) {
      saveWithUndo(openSection);
    }
    setOpenSection((prev) => (prev === section ? null : section));
  }

  // Sections that are locked during an active build
  const lockedDuringBuild: SettingsSection[] = ["sources", "delivery", "schedule"];
  function isSectionLocked(section: SettingsSection): boolean {
    return buildInProgress && lockedDuringBuild.includes(section);
  }

  // Close the currently open section if it becomes locked by a build
  useEffect(() => {
    if (openSection && isSectionLocked(openSection)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setOpenSection(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildInProgress]);

  // ── Deep link scroll on mount ──

  const scrollRef = useRef(false);
  useEffect(() => {
    if (initialOpen && !scrollRef.current) {
      scrollRef.current = true;
      // Small delay to ensure DOM is ready
      requestAnimationFrame(() => {
        const el = document.querySelector(
          `[data-section="${initialOpen}"]`
        );
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, [initialOpen]);

  // ── Render ──

  return (
    <div className="space-y-3">
      {buildInProgress && (
        <div className="flex items-center gap-2 rounded-md border border-building/30 bg-building/10 px-4 py-3">
          <div className="h-2 w-2 animate-pulse rounded-full bg-building" />
          <p className="font-body text-sm text-ink">
            A build is in progress. Sources, delivery, and schedule settings are
            locked until the build completes.
          </p>
        </div>
      )}
      {renderCard(
        "sources",
        "Sources",
        getSourcesSummary(feeds, effectiveCounts ?? undefined),
        <SourcesSection
          feeds={feeds}
          categories={categories}
          bundles={bundles}
          feedStats={feedStats}
          readingTime={paperValues.readingTime}
          onReadingTimeChange={handleReadingTimeChange}
          onDirtyChange={handleSourcesDirtyChange}
          onEffectiveCountChange={handleEffectiveCountChange}
          saveRef={sourcesSaveRef}
        />,
        true
      )}

      {renderCard(
        "delivery",
        "Delivery",
        getDeliverySummary(deliveryValues.device, deliveryValues.deliveryMethod),
        <DeliverySection
          values={deliveryValues}
          onChange={setDeliveryValues}
          hasDrive={hasDrive}
          opdsUrl={currentOpdsUrl}
          onOpdsUrlChange={setCurrentOpdsUrl}
          userEmail={userEmail}
        />,
        true
      )}

      {renderCard(
        "schedule",
        "Schedule",
        getScheduleSummary(
          scheduleValues.deliveryTime,
          scheduleValues.timezone
        ),
        <ScheduleSection
          values={scheduleValues}
          onChange={setScheduleValues}
        />,
        true
      )}

      {renderCard(
        "paper",
        "Your Paper",
        getPaperSummary(paperValues),
        <PaperSection values={paperValues} onChange={setPaperValues} />,
        true
      )}

      {renderCard(
        "account",
        "Account",
        getAccountSummary(userEmail, authProvider),
        <AccountSection email={userEmail} authProvider={authProvider} />,
        false
      )}
    </div>
  );

  function renderCard(
    section: SettingsSection,
    title: string,
    summary: string,
    content: React.ReactNode,
    showSave?: boolean
  ) {
    const isOpen = openSection === section;
    const locked = isSectionLocked(section);

    return (
      <div
        key={section}
        data-section={section}
        className={`newsprint-card overflow-hidden border border-rule-gray border-l-[3px] bg-card ${SECTION_COLORS[section]} ${locked ? "opacity-60" : ""}`}
      >
        {/* Header — always visible */}
        <button
          type="button"
          onClick={() => !locked && handleToggle(section)}
          disabled={locked}
          className={`flex w-full items-center justify-between px-5 py-4 text-left transition-colors ${locked ? "cursor-not-allowed" : "cursor-pointer hover:bg-warm-gray/30"}`}
        >
          <h2 className="font-headline text-sm font-bold text-ink">
            {title}
          </h2>
          <span className="ml-4 flex shrink-0 items-center gap-2">
            {!isOpen && (
              <span className="font-mono text-xs text-caption">{summary}</span>
            )}
            <ChevronRight
              className={`h-3 w-3 text-caption transition-transform duration-200 ${isOpen ? "rotate-90" : ""}`}
            />
          </span>
        </button>

        {/* Expanded content */}
        {isOpen && !locked && (
          <div className="border-t border-rule-gray px-5 pb-5 pt-4">
            {content}

            {showSave && isDirty(section) && (
              <Button
                onClick={() => handleExplicitSave(section)}
                disabled={isSaving}
                className="letterpress mt-5 w-full bg-ink text-sm text-newsprint hover:bg-ink/90"
              >
                {isSaving ? <>Saving<LoadingDots /></> : "Save changes"}
              </Button>
            )}
          </div>
        )}
      </div>
    );
  }
}
