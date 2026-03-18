"use client";

import { useSyncExternalStore, useCallback } from "react";
import { TIMEZONES } from "@/lib/constants";
import type { Device, DeliveryMethod } from "@/types";

const STORAGE_KEY = "paperboy_onboarding";

function detectTimezone(): string {
  try {
    const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
    // Exact match in our list
    if (TIMEZONES.some((tz) => tz.value === detected)) return detected;
    // Legacy US/ aliases → IANA mapping
    const legacyMap: Record<string, string> = {
      "US/Eastern": "America/New_York",
      "US/Central": "America/Chicago",
      "US/Pacific": "America/Los_Angeles",
      "US/Mountain": "America/Denver",
      "US/Hawaii": "Pacific/Honolulu",
      "US/Alaska": "America/Anchorage",
    };
    for (const [legacy, iana] of Object.entries(legacyMap)) {
      if (detected === legacy && TIMEZONES.some((tz) => tz.value === iana)) {
        return iana;
      }
    }
    // Match by UTC offset as fallback
    const now = new Date();
    const detectedOffset = -now.getTimezoneOffset(); // minutes east of UTC
    function getOffset(tz: string): number {
      const fmt = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        timeZoneName: "shortOffset",
      });
      const parts = fmt.formatToParts(now);
      const tzPart = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
      const match = tzPart.match(/GMT([+-]\d+(?::(\d+))?)?/);
      if (!match) return 0;
      if (!match[1]) return 0;
      const hours = parseInt(match[1], 10);
      const mins = match[2] ? parseInt(match[2], 10) : 0;
      return hours * 60 + (hours < 0 ? -mins : mins);
    }
    let best = TIMEZONES[0].value;
    let bestDiff = Infinity;
    for (const tz of TIMEZONES) {
      const diff = Math.abs(getOffset(tz.value) - detectedOffset);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = tz.value;
      }
    }
    return best;
  } catch {
    return "America/New_York";
  }
}

export interface OnboardingState {
  step: number;
  maxStepVisited: number;
  device: Device | null;
  feeds: { name: string; url: string; category: string }[];
  deliveryMethod: DeliveryMethod;
  title: string;
  readingTime: string;
  totalArticleBudget: number;
  includeImages: boolean;
  deliveryTime: string;
  timezone: string;
  googleDriveFolder: string;
  recipientEmail: string;
}

const DEFAULTS: OnboardingState = {
  step: 1,
  maxStepVisited: 1,
  device: null,
  feeds: [],
  deliveryMethod: "local",
  title: "The Morning Paper",
  readingTime: "15",
  totalArticleBudget: 5,
  includeImages: true,
  deliveryTime: "06:00",
  timezone: typeof window !== "undefined" ? detectTimezone() : "America/New_York",
  googleDriveFolder: "Paper Boy News",
  recipientEmail: "",
};

// ── Module-level external store for onboarding state ──

let currentState: OnboardingState = DEFAULTS;
const listeners = new Set<() => void>();

function emitChange() {
  for (const listener of listeners) listener();
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

function getSnapshot(): OnboardingState {
  return currentState;
}

function getServerSnapshot(): OnboardingState {
  return DEFAULTS;
}

// Initialize from localStorage on module load (client-only)
if (typeof window !== "undefined") {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      currentState = { ...DEFAULTS, ...JSON.parse(raw) };
    }
  } catch {
    // Storage unavailable — use defaults
  }
}

function saveToStorage(state: OnboardingState) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full or unavailable — continue without persistence
  }
}

// ── Exported helpers (used by onboarding/complete page) ──

export function clearOnboardingStorage() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  currentState = DEFAULTS;
  emitChange();
}

export function getOnboardingStorage(): OnboardingState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return null;
  }
}

// ── Hook ──

export function useOnboardingState() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // On the server, loaded is false (renders loading screen to avoid hydration mismatch)
  // On the client, loaded is true (localStorage already read at module init)
  const loaded = useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );

  const update = useCallback(
    (partial: Partial<OnboardingState>) => {
      currentState = { ...currentState, ...partial };
      saveToStorage(currentState);
      emitChange();
    },
    []
  );

  const goToStep = useCallback(
    (step: number) => {
      currentState = {
        ...currentState,
        step,
        maxStepVisited: Math.max(currentState.maxStepVisited, step),
      };
      saveToStorage(currentState);
      emitChange();
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    []
  );

  return { state, update, goToStep, loaded };
}
