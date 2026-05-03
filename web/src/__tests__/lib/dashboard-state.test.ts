import { describe, it, expect } from "vitest";
import { getDashboardState } from "@/components/dashboard-client";
import type { SetupStatus, DeliveryRecord } from "@/types";

const CONFIGURED: SetupStatus = {
  isFirstVisit: false,
  needsDriveAuth: false,
  needsRecipientEmail: false,
  isFullyConfigured: true,
};

const INCOMPLETE: SetupStatus = {
  ...CONFIGURED,
  needsDriveAuth: true,
  isFullyConfigured: false,
};

const DELIVERED_EDITION: DeliveryRecord = {
  id: "1",
  userId: "u1",
  status: "delivered",
  editionNumber: 1,
  editionDate: "2026-03-08",
  articleCount: 10,
  sourceCount: 5,
  fileSize: "1 MB",
  fileSizeBytes: 1000000,
  deliveryMethod: "local",
  deliveryMessage: "",
  errorMessage: null,
  epubStoragePath: "path/to/epub",
  resendMessageId: null,
  sections: null,
  createdAt: "2026-03-08T06:00:00Z",
};

const FAILED_EDITION: DeliveryRecord = {
  ...DELIVERED_EDITION,
  status: "failed",
  errorMessage: "Build failed",
};

describe("getDashboardState", () => {
  it("returns setup-incomplete when not fully configured", () => {
    expect(getDashboardState(INCOMPLETE, "idle", false, false, null, 0))
      .toBe("setup-incomplete");
  });

  it("returns build-in-progress when fetching", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, null, 1))
      .toBe("build-in-progress");
  });

  it("returns build-error when error", () => {
    expect(getDashboardState(CONFIGURED, "error", false, false, null, 1))
      .toBe("build-error");
  });

  it("returns fetched-early when done", () => {
    expect(getDashboardState(CONFIGURED, "done", false, false, null, 1))
      .toBe("fetched-early");
  });

  it("returns pre-build-first before cutoff with no history", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, null, 0))
      .toBe("pre-build-first");
  });

  it("returns pre-build before cutoff with history", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, null, 3))
      .toBe("pre-build");
  });

  it("returns delivered when today's edition is delivered", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, false, DELIVERED_EDITION, 3))
      .toBe("delivered");
  });

  it("returns failed when today's edition failed", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, false, FAILED_EDITION, 3))
      .toBe("failed");
  });

  it("returns ready-first after cutoff with no history and no edition", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, true, null, 0))
      .toBe("ready-first");
  });

  it("returns ready after cutoff with history but no today's edition", () => {
    expect(getDashboardState(CONFIGURED, "idle", false, true, null, 3))
      .toBe("ready");
  });

  it("returns delivered even before cutoff (edition exists)", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, DELIVERED_EDITION, 3))
      .toBe("delivered");
  });

  it("returns failed even before cutoff (failed edition exists)", () => {
    expect(getDashboardState(CONFIGURED, "idle", true, true, FAILED_EDITION, 3))
      .toBe("failed");
  });

  it("prioritizes setup-incomplete over pre-build", () => {
    expect(getDashboardState(INCOMPLETE, "idle", true, true, null, 0))
      .toBe("setup-incomplete");
  });

  it("prioritizes fetching over delivered edition", () => {
    expect(getDashboardState(CONFIGURED, "fetching", false, false, DELIVERED_EDITION, 3))
      .toBe("build-in-progress");
  });

  it("returns build-in-progress when today's edition is building (from DB)", () => {
    const BUILDING_EDITION: DeliveryRecord = {
      ...DELIVERED_EDITION,
      status: "building",
      articleCount: 0,
    };
    expect(getDashboardState(CONFIGURED, "idle", false, false, BUILDING_EDITION, 3))
      .toBe("build-in-progress");
  });

  it("returns build-in-progress for building even before cutoff", () => {
    const BUILDING_EDITION: DeliveryRecord = {
      ...DELIVERED_EDITION,
      status: "building",
      articleCount: 0,
    };
    expect(getDashboardState(CONFIGURED, "idle", true, true, BUILDING_EDITION, 3))
      .toBe("build-in-progress");
  });

  it("returns awaiting-delivery when today's edition is built", () => {
    const BUILT_EDITION: DeliveryRecord = {
      ...DELIVERED_EDITION,
      status: "built",
    };
    expect(getDashboardState(CONFIGURED, "idle", false, false, BUILT_EDITION, 3))
      .toBe("awaiting-delivery");
  });

  it("returns awaiting-delivery for built even before cutoff", () => {
    const BUILT_EDITION: DeliveryRecord = {
      ...DELIVERED_EDITION,
      status: "built",
    };
    expect(getDashboardState(CONFIGURED, "idle", true, true, BUILT_EDITION, 3))
      .toBe("awaiting-delivery");
  });

  it("prioritizes fetching over built edition", () => {
    const BUILT_EDITION: DeliveryRecord = {
      ...DELIVERED_EDITION,
      status: "built",
    };
    expect(getDashboardState(CONFIGURED, "fetching", false, false, BUILT_EDITION, 3))
      .toBe("build-in-progress");
  });
});
