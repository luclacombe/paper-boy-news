"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Settings, ChevronRight, ChevronDown, Download, Usb } from "lucide-react";
import { getItNow } from "@/actions/build";
import { getGoogleAuthUrl } from "@/actions/google-oauth";
import {
  downloadEpub,
  sendToDevice,
  supportsDirectoryPicker,
  pickDeviceFolder,
  getDeviceFolderName,
  clearDeviceFolder,
} from "@/lib/download-epub";
import {
  getDeliveryPastTense,
  getNextDeliverySentence,
  getPreBuildSentence,
  getReadySentence,
  getEarlyDeliveryDescription,
} from "@/lib/next-delivery";
import { BuildProgress } from "@/components/build-progress";
import { Button } from "@/components/ui/button";
import { DEVICES, DELIVERY_TIMES } from "@/lib/constants";
import type {
  UserConfig,
  Feed,
  DeliveryRecord,
  SetupStatus,
  BuildResult,
} from "@/types";

// ─── State machine ───────────────────────────────────────────────

export type DashboardState =
  | "setup-incomplete"
  | "build-in-progress"
  | "build-error"
  | "awaiting-delivery"
  | "pre-build-first"
  | "pre-build"
  | "ready-first"
  | "ready"
  | "fetched-early"
  | "delivered"
  | "failed";

type EarlyFetchState = "idle" | "fetching" | "done" | "error";

export function getDashboardState(
  setupStatus: SetupStatus,
  earlyState: EarlyFetchState,
  isBeforeCutoff: boolean,
  isBeforeDelivery: boolean,
  todaysEdition: DeliveryRecord | null,
  historyCount: number
): DashboardState {
  // Active build states always take priority — even if the user changed
  // settings mid-build (e.g. switched delivery method, making setup "incomplete")
  if (earlyState === "fetching") return "build-in-progress";
  if (todaysEdition?.status === "building") return "build-in-progress";
  if (earlyState === "error") return "build-error";
  if (earlyState === "done") return "fetched-early";

  // Current edition exists — show its status regardless of time of day
  if (todaysEdition?.status === "built") return "awaiting-delivery";
  if (todaysEdition?.status === "delivered") return "delivered";
  if (todaysEdition?.status === "failed") return "failed";

  // No active build — now check setup completeness
  if (!setupStatus.isFullyConfigured) return "setup-incomplete";

  // No edition yet — are we before or after the 5 AM cutoff?
  if (isBeforeCutoff) {
    return historyCount === 0 ? "pre-build-first" : "pre-build";
  }

  // After cutoff, no edition yet — paper is ready to fetch
  return historyCount === 0 ? "ready-first" : "ready";
}

// ─── Component ───────────────────────────────────────────────────

interface DashboardClientProps {
  config: UserConfig;
  feeds: Feed[];
  history: DeliveryRecord[];
  setupStatus: SetupStatus;
  editionDate: string;
  isBeforeCutoff: boolean;
  isBeforeDelivery: boolean;
  todaysEdition: DeliveryRecord | null;
}

export function DashboardClient({
  config,
  feeds,
  history,
  setupStatus,
  editionDate,
  isBeforeCutoff,
  isBeforeDelivery,
  todaysEdition,
}: DashboardClientProps) {
  const router = useRouter();
  const [earlyState, setEarlyState] = useState<EarlyFetchState>("idle");
  const [earlyStep, setEarlyStep] = useState(0);
  const [earlyResult, setEarlyResult] = useState<BuildResult | null>(null);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const [deviceFolderName, setDeviceFolderName] = useState<string | null>(null);
  const supportsDevice = supportsDirectoryPicker();

  // Load saved device folder name on mount
  useEffect(() => {
    if (!supportsDevice) return;
    getDeviceFolderName().then(setDeviceFolderName);
  }, [supportsDevice]);

  // Advance progress step while fetching (async: slower pace, more steps)
  useEffect(() => {
    if (earlyState !== "fetching") return;
    const interval = setInterval(() => {
      setEarlyStep((s) => (s < 19 ? s + 1 : s));
    }, earlyStep < 5 ? 3000 : 18000);
    return () => clearInterval(interval);
  }, [earlyState, earlyStep]);

  // Poll for build completion when in async building state
  useEffect(() => {
    if (earlyState !== "fetching") return;
    const interval = setInterval(() => {
      router.refresh();
    }, 5000);
    // Timeout after 5 minutes — do one final refresh before showing error,
    // since the build may have completed while polling was in-flight
    const timeout = setTimeout(() => {
      router.refresh();
      // Give the refresh a moment to propagate, then check if still building
      setTimeout(() => {
        setEarlyState((current) => {
          if (current !== "fetching") return current; // already resolved
          setEarlyResult({
            success: false,
            editionDate,
            totalArticles: 0,
            sections: [],
            fileSize: "0 KB",
            fileSizeBytes: 0,
            epubStoragePath: null,
            error:
              "Taking longer than expected. The build may still be running — try again to check.",
          });
          return "error";
        });
      }, 3000);
    }, 300_000);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [earlyState, router, editionDate]);

  // Detect when server data changes from "building" to "delivered", "built", or "failed"
  useEffect(() => {
    if (earlyState !== "fetching") return;
    if (todaysEdition?.status === "delivered" || todaysEdition?.status === "built") {
      setEarlyState("done");
      setEarlyResult({
        success: true,
        editionDate,
        totalArticles: todaysEdition.articleCount,
        sections: todaysEdition.sections ?? [],
        fileSize: todaysEdition.fileSize,
        fileSizeBytes: todaysEdition.fileSizeBytes,
        epubStoragePath: todaysEdition.epubStoragePath,
        error: null,
      });
      setFetchedAt(new Date());
      toast.success(
        todaysEdition.status === "delivered"
          ? "Your paper has been delivered"
          : "Your paper is ready"
      );
    } else if (todaysEdition?.status === "failed") {
      setEarlyState("error");
      setEarlyResult({
        success: false,
        editionDate,
        totalArticles: 0,
        sections: [],
        fileSize: "0 KB",
        fileSizeBytes: 0,
        epubStoragePath: null,
        error: todaysEdition.errorMessage ?? "Something went wrong",
      });
      toast.error(todaysEdition.errorMessage ?? "Something went wrong");
    }
  }, [earlyState, todaysEdition, editionDate]);

  const handleGetItNow = useCallback(async () => {
    setEarlyState("fetching");
    setEarlyStep(0);
    setEarlyResult(null);

    try {
      const result = await getItNow();
      if (result.building) {
        // Async build started — stay in fetching state, polling will detect completion
        return;
      }
      setEarlyResult(result);
      if (result.success) {
        setEarlyState("done");
        setFetchedAt(new Date());
        toast.success("Your paper is ready");
        router.refresh();
      } else {
        setEarlyState("error");
        toast.error(result.error ?? "Something went wrong");
      }
    } catch {
      setEarlyState("error");
      toast.error("Something went wrong");
    }
  }, [router]);

  async function handleDownload(record: DeliveryRecord) {
    if (!record.epubStoragePath) return;
    try {
      const filename = `${config.title.replace(/\s+/g, "-")}-${record.editionDate}.epub`;
      await downloadEpub(record.epubStoragePath, filename);
    } catch {
      toast.error("Download failed");
    }
  }

  async function handleDownloadResult(result: BuildResult) {
    if (!result.epubStoragePath) return;
    try {
      const filename = `${config.title.replace(/\s+/g, "-")}-${result.editionDate}.epub`;
      await downloadEpub(result.epubStoragePath, filename);
    } catch {
      toast.error("Download failed");
    }
  }

  async function handleSendToDevice(
    storagePath: string,
    editionDate: string
  ) {
    try {
      const filename = `${config.title.replace(/\s+/g, "-")}-${editionDate}.epub`;
      await sendToDevice(storagePath, filename);
      toast.success("Sent to device");
    } catch {
      toast.error("Failed to send — try downloading instead");
    }
  }

  async function handlePickFolder() {
    try {
      await pickDeviceFolder();
      const name = await getDeviceFolderName();
      setDeviceFolderName(name);
      toast.success(`Device folder set: ${name}`);
    } catch {
      // User cancelled picker — do nothing
    }
  }

  async function handleForgetDevice() {
    await clearDeviceFolder();
    setDeviceFolderName(null);
    toast.success("Device folder removed");
  }

  async function handleGoogleConnect() {
    try {
      const url = await getGoogleAuthUrl();
      window.location.href = url;
    } catch {
      toast.error("Failed to start Google authorization");
    }
  }

  const categories = [
    ...new Set(feeds.map((f) => f.category).filter(Boolean)),
  ];
  const pastTense = getDeliveryPastTense(config);
  const nextSentence = getNextDeliverySentence(config);
  const isDownloadMethod = config.deliveryMethod === "local";

  const state = getDashboardState(
    setupStatus,
    earlyState,
    isBeforeCutoff,
    isBeforeDelivery,
    todaysEdition,
    history.length
  );

  // Should we show the schedule nudge? Only for auto-delivery users
  // who fetched 30+ minutes before their scheduled delivery time.
  const showScheduleNudge =
    fetchedAt !== null && !isDownloadMethod && isBeforeDelivery;

  return (
    <div className="space-y-4">
      {renderStatusCard()}

      {/* Settings */}
      <Link
        href="/settings"
        className="newsprint-card flex items-center justify-between overflow-hidden border border-rule-gray bg-card px-4 py-3 transition-colors hover:border-caption"
      >
        <div className="flex items-center gap-3">
          <Settings className="h-4 w-4 text-caption" />
          <div>
            <span className="font-headline text-sm font-bold text-ink">
              Settings
            </span>
            <p className="font-body text-xs text-caption">
              Sources, delivery, and preferences
            </p>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-caption" />
      </Link>

      {/* Past editions */}
      {history.length > 0 && (
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between py-2 [&::-webkit-details-marker]:hidden">
            <span className="font-headline text-sm font-bold text-ink">
              Past editions
            </span>
            <span className="flex items-center gap-1 font-mono text-xs text-caption">
              {history.length} edition{history.length !== 1 ? "s" : ""}
              <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
            </span>
          </summary>
          <div className="mt-1">
            {history.slice(0, 5).map((record) => (
              <div
                key={record.id}
                className="flex items-center justify-between border-b border-rule-gray py-2"
              >
                <div className="flex items-center gap-3">
                  <span className="font-headline text-sm text-ink">
                    {new Date(record.editionDate).toLocaleDateString("en-US", {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <span
                    className={`font-mono text-[10px] ${
                      record.status === "delivered"
                        ? "text-delivered"
                        : record.status === "failed"
                          ? "text-edition-red"
                          : "text-building"
                    }`}
                  >
                    {record.status === "delivered"
                      ? "Delivered"
                      : record.status === "failed"
                        ? "Failed"
                        : record.status === "built"
                          ? "Ready"
                          : "Building"}
                  </span>
                  <span className="font-mono text-[10px] text-caption">
                    {record.articleCount} articles
                  </span>
                </div>
                {record.epubStoragePath && (record.status === "delivered" || record.status === "built") && (
                  deviceFolderName ? (
                    <button
                      onClick={() =>
                        handleSendToDevice(
                          record.epubStoragePath!,
                          record.editionDate
                        )
                      }
                      className="flex items-center gap-1 text-caption hover:text-ink"
                      title="Send to device"
                    >
                      <Usb className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleDownload(record)}
                      className="text-caption hover:text-ink"
                    >
                      <Download className="h-3.5 w-3.5" />
                    </button>
                  )
                )}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );

  // ─── Status card renderer ──────────────────────────────────────

  function renderStatusCard() {
    switch (state) {
      case "setup-incomplete":
        return renderSetupIncomplete();
      case "build-in-progress":
        return renderBuildInProgress();
      case "build-error":
        return renderBuildError();
      case "awaiting-delivery":
        return renderAwaitingDelivery();
      case "pre-build-first":
        return renderPreBuild(true);
      case "pre-build":
        return renderPreBuild(false);
      case "ready-first":
        return renderReady(true);
      case "ready":
        return renderReady(false);
      case "fetched-early":
        return renderFetchedEarly();
      case "delivered":
        return renderDelivered();
      case "failed":
        return renderFailed();
    }
  }

  // ─── State 1: Setup incomplete ─────────────────────────────────

  function renderSetupIncomplete() {
    const deviceLabel =
      DEVICES.find((d) => d.value === config.device)?.label ?? config.device;

    let description = "";
    let cta: React.ReactNode = null;

    if (setupStatus.needsDriveAuth) {
      description = `Connect Google Drive so your paper can be delivered to your ${deviceLabel} each morning.`;
      cta = (
        <Button
          onClick={handleGoogleConnect}
          className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
          size="sm"
        >
          Connect Google Drive
        </Button>
      );
    } else if (setupStatus.needsGmailAuth) {
      description = `Connect Gmail so your paper can be emailed to your ${deviceLabel} each morning.`;
      cta = (
        <Button
          onClick={handleGoogleConnect}
          className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
          size="sm"
        >
          Connect Gmail
        </Button>
      );
    } else if (setupStatus.needsSmtpConfig) {
      description =
        "Configure your email server so your paper can be delivered each morning.";
      cta = (
        <Link
          href="/settings?open=delivery"
          className="letterpress inline-block rounded-md bg-ink px-3 py-1.5 text-sm text-newsprint hover:bg-ink/90"
        >
          Open delivery settings
        </Link>
      );
    } else if (setupStatus.needsKindleEmail) {
      description =
        "Add your Kindle email address so your paper can be delivered each morning.";
      cta = (
        <Link
          href="/settings?open=delivery"
          className="letterpress inline-block rounded-md bg-ink px-3 py-1.5 text-sm text-newsprint hover:bg-ink/90"
        >
          Open delivery settings
        </Link>
      );
    }

    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-building bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            One more step to get your morning paper
          </p>
          <p className="mt-2 font-body text-sm text-caption">{description}</p>
        </div>
        <div className="border-t border-rule-gray px-5 py-3">{cta}</div>
        <div className="border-t border-rule-gray bg-warm-gray/30 px-5 py-3">
          <p className="font-body text-xs text-caption">
            Rather download manually?{" "}
            <Link
              href="/settings?open=delivery"
              className="font-semibold text-ink underline hover:text-caption"
            >
              Switch to downloads in Settings
            </Link>
          </p>
        </div>
      </div>
    );
  }

  // ─── State 2: Build in progress ────────────────────────────────

  function renderBuildInProgress() {
    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-building bg-card">
        <div className="px-5 pt-5 pb-2">
          <p className="font-headline text-lg font-bold text-ink">
            Getting your paper&hellip;
          </p>
          <p className="mt-1 font-body text-sm text-caption">
            Fetching the latest articles from your sources.
          </p>
        </div>
        <div className="px-5 pb-5">
          <BuildProgress step={earlyStep} async />
        </div>
      </div>
    );
  }

  // ─── State 3: Build error ──────────────────────────────────────

  function renderBuildError() {
    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-edition-red bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            Something went wrong
          </p>
          <p className="mt-2 font-body text-sm text-caption">
            {earlyResult?.error ??
              "Your paper couldn\u2019t be prepared. This is usually temporary."}
          </p>
        </div>
        <div className="border-t border-rule-gray px-5 py-3">
          <Button
            onClick={handleGetItNow}
            size="sm"
            className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
          >
            Try again
          </Button>
        </div>
        {renderScheduleFooter()}
      </div>
    );
  }

  // ─── State 4: Awaiting delivery (built but not yet delivered) ──

  function renderAwaitingDelivery() {
    const edition = todaysEdition!;
    const timeLabel =
      DELIVERY_TIMES.find((t) => t.value === config.deliveryTime)?.label ??
      config.deliveryTime;
    const deviceLabel =
      DEVICES.find((d) => d.value === config.device)?.label ?? config.device;

    let deliveryDesc = `will be ready at ${timeLabel}`;
    if (config.deliveryMethod === "google_drive") {
      deliveryDesc = `will be delivered to your ${deviceLabel} via Google Drive at ${timeLabel}`;
    } else if (config.deliveryMethod === "email") {
      deliveryDesc = `will be emailed to your ${deviceLabel} at ${timeLabel}`;
    }

    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-building bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            Your paper has been prepared
          </p>
          <p className="mt-1 font-body text-sm text-caption">
            {edition.articleCount} articles from {edition.sourceCount} sources
            &middot;{" "}
            {new Date(edition.editionDate).toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
          <p className="mt-2 font-body text-sm text-caption">
            It {deliveryDesc}.
          </p>
        </div>
        <div className="border-t border-rule-gray px-5 py-3">
          <div className="flex items-center gap-3">
            <Button
              onClick={handleGetItNow}
              size="sm"
              className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
            >
              Deliver now
            </Button>
            {edition.epubStoragePath && (
              deviceFolderName ? (
                <button
                  onClick={() =>
                    handleSendToDevice(
                      edition.epubStoragePath!,
                      edition.editionDate
                    )
                  }
                  className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
                >
                  <Usb className="h-3.5 w-3.5" />
                  Send to device
                </button>
              ) : (
                <button
                  onClick={() => handleDownload(edition)}
                  className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download
                </button>
              )
            )}
          </div>
        </div>
        {renderScheduleFooter()}
      </div>
    );
  }

  // ─── State 5: Pre-build (before 5 AM) ─────────────────────────

  function renderPreBuild(isFirst: boolean) {
    const description = getPreBuildSentence(config, isFirst);
    const borderColor = isFirst ? "border-l-delivered" : "border-l-building";

    return (
      <div
        className={`newsprint-card overflow-hidden border border-rule-gray border-l-4 ${borderColor} bg-card`}
      >
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            {isFirst ? "You\u2019re all set" : "Your next edition is on its way"}
          </p>
          <p className="mt-2 font-body text-sm text-caption">{description}</p>
          {isFirst && (
            <p className="mt-3 font-mono text-xs text-caption">
              {feeds.length} source{feeds.length !== 1 ? "s" : ""} &middot;{" "}
              {categories.length} section{categories.length !== 1 ? "s" : ""}
            </p>
          )}
          <p className="mt-2 font-body text-xs text-caption">
            You can always change your schedule in{" "}
            <Link
              href="/settings?open=schedule"
              className="font-semibold text-ink underline hover:text-caption"
            >
              Settings
            </Link>
            .
          </p>
        </div>
      </div>
    );
  }

  // ─── State 5: Edition ready (after 5 AM, not yet delivered) ────

  function renderReady(isFirst: boolean) {
    const readySentence = getReadySentence(config);
    const earlyDesc = getEarlyDeliveryDescription(config);

    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-delivered bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            {isFirst ? "You\u2019re all set" : "Today\u2019s paper is ready"}
          </p>
          {isFirst ? (
            <>
              <p className="mt-2 font-body text-sm text-caption">
                {readySentence}
              </p>
              <p className="mt-3 font-mono text-xs text-caption">
                {feeds.length} source{feeds.length !== 1 ? "s" : ""} &middot;{" "}
                {categories.length} section{categories.length !== 1 ? "s" : ""}
              </p>
            </>
          ) : (
            <p className="mt-1 font-body text-sm text-caption">
              {new Date(editionDate).toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </p>
          )}
        </div>
        <div className="border-t border-rule-gray bg-warm-gray/30 px-5 py-3">
          <p className="font-body text-sm text-caption">
            {isFirst ? "Can\u2019t wait? " : ""}
            <button
              onClick={handleGetItNow}
              disabled={feeds.length === 0}
              className="font-semibold text-ink underline hover:text-caption disabled:opacity-50"
            >
              {isFirst ? "Get today\u2019s edition now" : "Get it now"}
            </button>
            {!isFirst && (
              <>
                {" "}
                &mdash; {earlyDesc.toLowerCase()}.
              </>
            )}
          </p>
          {!isFirst && (
            <p className="mt-1 font-body text-xs text-caption">
              {readySentence}
            </p>
          )}
        </div>
      </div>
    );
  }

  // ─── State 6: Fetched early ────────────────────────────────────

  function renderFetchedEarly() {
    if (!earlyResult) return null;

    if (isDownloadMethod) {
      return (
        <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-delivered bg-card">
          <div className="px-5 pt-5 pb-4">
            <p className="font-headline text-lg font-bold text-ink">
              Your paper is ready
            </p>
            <p className="mt-1 font-body text-sm text-caption">
              {earlyResult.totalArticles} articles from{" "}
              {earlyResult.sections.length} sources
            </p>
          </div>
          <div className="border-t border-rule-gray px-5 py-4">
            {earlyResult.epubStoragePath ? (
              <>
                {deviceFolderName ? (
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() =>
                        handleSendToDevice(
                          earlyResult.epubStoragePath!,
                          earlyResult.editionDate
                        )
                      }
                      className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
                    >
                      <Usb className="mr-2 h-4 w-4" />
                      Send to device
                    </Button>
                    <Button
                      onClick={() => handleDownloadResult(earlyResult)}
                      variant="outline"
                      size="icon"
                      className="h-9 w-9"
                      title="Download file"
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={() => handleDownloadResult(earlyResult)}
                    className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download EPUB
                  </Button>
                )}
                {renderDeviceFolderInfo()}
              </>
            ) : (
              <p className="font-body text-sm text-caption">
                Your edition was built but the file is not available for
                download.
              </p>
            )}
          </div>
          {renderScheduleFooter()}
        </div>
      );
    }

    // Auto-delivery (Drive/email)
    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-delivered bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            Your paper was {pastTense}
          </p>
          <p className="mt-1 font-body text-sm text-caption">
            {earlyResult.totalArticles} articles from{" "}
            {earlyResult.sections.length} sources
          </p>
        </div>
        {earlyResult.epubStoragePath && (
          <div className="border-t border-rule-gray px-5 py-3">
            {deviceFolderName ? (
              <button
                onClick={() =>
                  handleSendToDevice(
                    earlyResult.epubStoragePath!,
                    earlyResult.editionDate
                  )
                }
                className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
              >
                <Usb className="h-3.5 w-3.5" />
                Send to device
              </button>
            ) : (
              <button
                onClick={() => handleDownloadResult(earlyResult)}
                className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
              >
                <Download className="h-3.5 w-3.5" />
                Download a copy
              </button>
            )}
          </div>
        )}
        {showScheduleNudge && (
          <div className="border-t border-rule-gray px-5 py-3">
            <p className="font-body text-xs text-caption">
              Want it this early every day?{" "}
              <Link
                href="/settings?open=schedule"
                className="font-semibold text-ink underline hover:text-caption"
              >
                Update your schedule
              </Link>
            </p>
          </div>
        )}
        {renderScheduleFooter()}
      </div>
    );
  }

  // ─── State 7: Delivered on schedule ────────────────────────────

  function renderDelivered() {
    const edition = todaysEdition!;

    if (isDownloadMethod) {
      return (
        <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-delivered bg-card">
          <div className="px-5 pt-5 pb-4">
            <p className="font-headline text-lg font-bold text-ink">
              Your morning paper is ready
            </p>
            <p className="mt-1 font-body text-sm text-caption">
              {edition.articleCount} articles from {edition.sourceCount} sources
              &middot;{" "}
              {new Date(edition.editionDate).toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>

          <div className="border-t border-rule-gray px-5 py-4">
            {edition.epubStoragePath ? (
              <>
                {deviceFolderName ? (
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() =>
                        handleSendToDevice(
                          edition.epubStoragePath!,
                          edition.editionDate
                        )
                      }
                      className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
                    >
                      <Usb className="mr-2 h-4 w-4" />
                      Send to device
                    </Button>
                    <Button
                      onClick={() => handleDownload(edition)}
                      variant="outline"
                      size="icon"
                      className="h-9 w-9"
                      title="Download file"
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={() => handleDownload(edition)}
                    className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download EPUB
                  </Button>
                )}
                {renderDeviceFolderInfo()}
              </>
            ) : (
              <p className="font-body text-sm text-caption">
                The EPUB file for this edition is no longer available.
              </p>
            )}
          </div>

          {renderScheduleFooter()}
        </div>
      );
    }

    // Auto-delivery
    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-delivered bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            Your morning paper was {pastTense}
          </p>
          <p className="mt-1 font-body text-sm text-caption">
            {edition.articleCount} articles from {edition.sourceCount} sources
            &middot;{" "}
            {new Date(edition.editionDate).toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>

        {edition.epubStoragePath && (
          <div className="border-t border-rule-gray px-5 py-3">
            {deviceFolderName ? (
              <button
                onClick={() =>
                  handleSendToDevice(
                    edition.epubStoragePath!,
                    edition.editionDate
                  )
                }
                className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
              >
                <Usb className="h-3.5 w-3.5" />
                Send to device
              </button>
            ) : (
              <button
                onClick={() => handleDownload(edition)}
                className="flex items-center gap-1.5 font-body text-xs text-caption hover:text-ink"
              >
                <Download className="h-3.5 w-3.5" />
                Download a copy
              </button>
            )}
          </div>
        )}

        {renderScheduleFooter()}
      </div>
    );
  }

  // ─── State 8: Today's delivery failed ──────────────────────────

  function renderFailed() {
    const edition = todaysEdition!;

    return (
      <div className="newsprint-card overflow-hidden border border-rule-gray border-l-4 border-l-edition-red bg-card">
        <div className="px-5 pt-5 pb-4">
          <p className="font-headline text-lg font-bold text-ink">
            {isDownloadMethod
              ? "Today\u2019s paper couldn\u2019t be prepared"
              : "Today\u2019s paper couldn\u2019t be delivered"}
          </p>
          <p className="mt-2 font-body text-sm text-caption">
            {edition.errorMessage ??
              "Something went wrong. This is usually temporary."}
          </p>
        </div>
        <div className="border-t border-rule-gray px-5 py-3">
          <Button
            onClick={handleGetItNow}
            size="sm"
            className="letterpress bg-ink text-sm text-newsprint hover:bg-ink/90"
          >
            Try again
          </Button>
        </div>
        {renderScheduleFooter()}
      </div>
    );
  }

  // ─── Device folder info (shown under primary download buttons) ──

  function renderDeviceFolderInfo() {
    if (deviceFolderName) {
      return (
        <p className="mt-2 font-body text-xs text-caption">
          Saving to <span className="font-semibold text-ink">{deviceFolderName}</span>
          <span className="mx-1">&middot;</span>
          <button
            onClick={handlePickFolder}
            className="text-ink underline hover:text-caption"
          >
            Change folder
          </button>
          <span className="mx-1">&middot;</span>
          <button
            onClick={handleForgetDevice}
            className="text-ink underline hover:text-caption"
          >
            Forget device
          </button>
        </p>
      );
    }

    if (supportsDevice) {
      return (
        <p className="mt-2 font-body text-xs text-caption">
          Transfer via USB or your reading app.{" "}
          <button
            onClick={handlePickFolder}
            className="font-semibold text-ink underline hover:text-caption"
          >
            Set up one-click transfer
          </button>
        </p>
      );
    }

    return (
      <p className="mt-2 font-body text-xs text-caption">
        Transfer this file to your e-reader via USB or your reading app.
      </p>
    );
  }

  // ─── Footers ───────────────────────────────────────────────────

  function renderScheduleFooter() {
    return (
      <div className="border-t border-rule-gray bg-warm-gray/30 px-5 py-3">
        <p className="font-body text-xs text-caption">
          {nextSentence}.{" "}
          <Link
            href="/settings?open=schedule"
            className="text-ink underline hover:text-caption"
          >
            Change schedule
          </Link>
        </p>
      </div>
    );
  }
}
