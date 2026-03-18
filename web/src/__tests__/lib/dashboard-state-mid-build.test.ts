/**
 * Tests for dashboard state machine behavior during active builds,
 * specifically covering scenarios where users change settings mid-build.
 *
 * These tests verify the fix where build-in-progress was being overridden
 * by setup-incomplete when a user changed delivery method mid-build.
 */
import { describe, it, expect } from "vitest";
import { getDashboardState } from "@/components/dashboard-client";
import type { SetupStatus, DeliveryRecord } from "@/types";

// ─── Fixtures ──────────────────────────────────────────────────────

const CONFIGURED: SetupStatus = {
  isFirstVisit: false,
  needsDriveAuth: false,
  needsRecipientEmail: false,
  isFullyConfigured: true,
};

const NEEDS_DRIVE: SetupStatus = {
  ...CONFIGURED,
  needsDriveAuth: true,
  isFullyConfigured: false,
};

const NEEDS_EMAIL: SetupStatus = {
  ...CONFIGURED,
  needsRecipientEmail: true,
  isFullyConfigured: false,
};

const BUILDING_EDITION: DeliveryRecord = {
  id: "1",
  userId: "u1",
  status: "building",
  editionNumber: 1,
  editionDate: "2026-03-09",
  articleCount: 0,
  sourceCount: 5,
  fileSize: "0 KB",
  fileSizeBytes: 0,
  deliveryMethod: "google_drive",
  deliveryMessage: "",
  errorMessage: null,
  epubStoragePath: null,
  sections: null,
  createdAt: "2026-03-09T06:00:00Z",
};

const BUILT_EDITION: DeliveryRecord = {
  ...BUILDING_EDITION,
  status: "built",
  articleCount: 10,
  fileSize: "1 MB",
  fileSizeBytes: 1000000,
  epubStoragePath: "auth-1/My-Paper-2026-03-09.epub",
  sections: [{ name: "World", headlines: ["Headline 1"] }],
};

const DELIVERED_EDITION: DeliveryRecord = {
  ...BUILT_EDITION,
  status: "delivered",
};

const FAILED_EDITION: DeliveryRecord = {
  ...BUILDING_EDITION,
  status: "failed",
  errorMessage: "Delivery failed: SMTP connection refused",
};

// ─── Mid-build settings change scenarios ───────────────────────────

describe("getDashboardState — mid-build settings changes", () => {
  describe("delivery method changed to unconfigured method during client-side fetch", () => {
    it("shows build-in-progress when user switches to Drive (no auth) while fetching", () => {
      expect(getDashboardState(NEEDS_DRIVE, "fetching", false, false, null, 1))
        .toBe("build-in-progress");
    });

    it("shows build-in-progress when user switches to email (no recipient) while fetching", () => {
      expect(getDashboardState(NEEDS_EMAIL, "fetching", false, false, null, 1))
        .toBe("build-in-progress");
    });
  });

  describe("delivery method changed during DB-tracked build", () => {
    it("shows build-in-progress when DB says building, even if setup is incomplete (Drive)", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, BUILDING_EDITION, 1))
        .toBe("build-in-progress");
    });

    it("shows build-in-progress when DB says building, even if setup is incomplete (email)", () => {
      expect(getDashboardState(NEEDS_EMAIL, "idle", false, false, BUILDING_EDITION, 1))
        .toBe("build-in-progress");
    });
  });

  describe("build completes while setup is incomplete", () => {
    it("shows awaiting-delivery when built, even if setup is now incomplete", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, BUILT_EDITION, 1))
        .toBe("awaiting-delivery");
    });

    it("shows delivered when delivered, even if setup is now incomplete", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, DELIVERED_EDITION, 1))
        .toBe("delivered");
    });

    it("shows failed when failed, even if setup is now incomplete", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, FAILED_EDITION, 1))
        .toBe("failed");
    });
  });

  describe("setup-incomplete only shown when no active/completed edition", () => {
    it("shows setup-incomplete when idle with no edition and setup incomplete", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, null, 0))
        .toBe("setup-incomplete");
    });

    it("shows setup-incomplete when idle with no edition (has history but no today)", () => {
      expect(getDashboardState(NEEDS_EMAIL, "idle", false, false, null, 5))
        .toBe("setup-incomplete");
    });

    it("shows setup-incomplete before cutoff with no edition", () => {
      expect(getDashboardState(NEEDS_DRIVE, "idle", true, true, null, 3))
        .toBe("setup-incomplete");
    });
  });
});

// ─── State priority ordering ───────────────────────────────────────

describe("getDashboardState — state priority ordering", () => {
  it("client fetching beats DB building", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, BUILDING_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("client fetching beats DB built", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, BUILT_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("client fetching beats DB delivered", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, DELIVERED_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("client fetching beats DB failed", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, FAILED_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("client fetching beats setup-incomplete", () => {
    expect(getDashboardState(NEEDS_DRIVE, "fetching", false, false, null, 0))
      .toBe("build-in-progress");
  });

  it("DB building beats setup-incomplete", () => {
    expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, BUILDING_EDITION, 0))
      .toBe("build-in-progress");
  });

  it("DB building beats client error (build may still be running server-side)", () => {
    // If the client timed out but DB still says building, the build may still
    // be running server-side. The error state will show once the DB record
    // transitions to "failed" or the user retries.
    expect(getDashboardState(CONFIGURED, "error", false, false, BUILDING_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("client done beats DB status", () => {
    expect(getDashboardState(CONFIGURED, "done", false, false, null, 1))
      .toBe("fetched-early");
  });

  it("DB built (awaiting-delivery) beats time-based states", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, BUILT_EDITION, 1))
      .toBe("awaiting-delivery");
  });

  it("DB delivered beats time-based states", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, DELIVERED_EDITION, 1))
      .toBe("delivered");
  });

  it("DB failed beats time-based states", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, FAILED_EDITION, 1))
      .toBe("failed");
  });
});

// ─── Navigation away and back scenarios ────────────────────────────

describe("getDashboardState — navigation away and back", () => {
  it("returns build-in-progress from DB after navigating back (earlyState resets to idle)", () => {
    // When user navigates to settings and back, React remounts the component.
    // earlyState resets to "idle", but the DB record still says "building".
    expect(getDashboardState(CONFIGURED, "idle", false, false, BUILDING_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("returns build-in-progress from DB even if settings changed during navigation", () => {
    // User went to settings, changed delivery to unconfigured method, came back.
    // DB still says building — should show progress, not setup-incomplete.
    expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, BUILDING_EDITION, 1))
      .toBe("build-in-progress");
  });

  it("returns delivered if build completed while user was in settings", () => {
    // User was in settings, build completed in background.
    // On return, earlyState is "idle" but DB says "delivered".
    expect(getDashboardState(CONFIGURED, "idle", false, false, DELIVERED_EDITION, 1))
      .toBe("delivered");
  });

  it("returns awaiting-delivery if build completed but not yet delivered while in settings", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, false, BUILT_EDITION, 1))
      .toBe("awaiting-delivery");
  });

  it("returns failed if build failed while user was in settings", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, false, FAILED_EDITION, 1))
      .toBe("failed");
  });
});

// ─── Edge cases ────────────────────────────────────────────────────

describe("getDashboardState — edge cases", () => {
  it("handles all setup flags being incomplete simultaneously", () => {
    const ALL_INCOMPLETE: SetupStatus = {
      isFirstVisit: true,
      needsDriveAuth: true,
      needsRecipientEmail: true,
      isFullyConfigured: false,
    };
    // With building edition, should still show build-in-progress
    expect(getDashboardState(ALL_INCOMPLETE, "idle", false, false, BUILDING_EDITION, 0))
      .toBe("build-in-progress");
    // Without edition, should show setup-incomplete
    expect(getDashboardState(ALL_INCOMPLETE, "idle", false, false, null, 0))
      .toBe("setup-incomplete");
  });

  it("first-time user with fetching state", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, null, 0))
      .toBe("build-in-progress");
  });

  it("first-time user with incomplete setup and building edition", () => {
    expect(getDashboardState(NEEDS_DRIVE, "idle", false, false, BUILDING_EDITION, 0))
      .toBe("build-in-progress");
  });

  it("all setup-incomplete variants fall through when no edition exists", () => {
    for (const status of [NEEDS_DRIVE, NEEDS_EMAIL]) {
      expect(getDashboardState(status, "idle", false, false, null, 0))
        .toBe("setup-incomplete");
    }
  });
});
