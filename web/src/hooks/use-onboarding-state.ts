"use client";

import { useSyncExternalStore, useCallback } from "react";
import type { Device, DeliveryMethod, EmailMethod } from "@/types";

const STORAGE_KEY = "paperboy_onboarding";

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
  kindleEmail: string;
  emailMethod: EmailMethod;
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
  timezone: "US/Eastern",
  googleDriveFolder: "Rakuten Kobo",
  kindleEmail: "",
  emailMethod: "gmail",
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
    },
    []
  );

  return { state, update, goToStep, loaded };
}
