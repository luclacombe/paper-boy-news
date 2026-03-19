import { describe, it, expect } from "vitest";
import { GOOGLE_DRIVE_DISABLED } from "@/lib/constants";
import { computeSetupStatus } from "@/lib/setup-status";
import type { UserConfig } from "@/types";

const BASE_CONFIG: UserConfig = {
  id: "1",
  authId: "auth-1",
  title: "Test Paper",
  language: "en",
  totalArticleBudget: 7,
  readingTime: "15",
  includeImages: true,
  device: "kobo",
  deliveryMethod: "google_drive",
  googleDriveFolder: "Rakuten Kobo",
  recipientEmail: "",
  deliveryTime: "07:00",
  timezone: "America/New_York",
  opdsToken: null,
  opdsTokenExpiresAt: null,
  googleTokens: null,
  onboardingComplete: true,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

describe("GOOGLE_DRIVE_DISABLED flag", () => {
  it("is set to true", () => {
    expect(GOOGLE_DRIVE_DISABLED).toBe(true);
  });
});

describe("computeSetupStatus with Google Drive", () => {
  it("reports needsDriveAuth when google_drive selected without tokens", () => {
    // computeSetupStatus is unaware of GOOGLE_DRIVE_DISABLED —
    // the flag is a UI-only concern. The function still correctly
    // reports that Drive auth is needed.
    const status = computeSetupStatus(BASE_CONFIG, 0, false);
    expect(status.needsDriveAuth).toBe(true);
    expect(status.isFullyConfigured).toBe(false);
  });

  it("reports fully configured when google_drive has tokens", () => {
    const status = computeSetupStatus(BASE_CONFIG, 0, true);
    expect(status.needsDriveAuth).toBe(false);
    expect(status.isFullyConfigured).toBe(true);
  });

  it("does not flag needsDriveAuth for non-Drive methods", () => {
    const emailConfig = { ...BASE_CONFIG, deliveryMethod: "email" as const, recipientEmail: "test@example.com" };
    const status = computeSetupStatus(emailConfig, 0, false);
    expect(status.needsDriveAuth).toBe(false);
    expect(status.isFullyConfigured).toBe(true);
  });
});
