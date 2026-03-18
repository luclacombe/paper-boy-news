/**
 * E2E integration test: signup → onboarding → build → deliver.
 *
 * Exercises the full server-action sequence with mocked DB and GitHub dispatch.
 * Validates the action orchestration logic, not browser UI.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// --- Shared state simulating the DB ---

let profileRow: Record<string, unknown> | null = null;
let feedRows: Record<string, unknown>[] = [];
let historyRows: Record<string, unknown>[] = [];

// Mock auth
const mockGetAuthUser = vi.fn();
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock GitHub dispatch
const mockDispatchBuild = vi.fn().mockResolvedValue(undefined);
vi.mock("@/lib/github-dispatch", () => ({
  dispatchBuild: (...args: unknown[]) => mockDispatchBuild(...args),
}));

// Mock getEditionForDate (one-per-day guard)
vi.mock("@/actions/delivery-history", () => ({
  getEditionForDate: vi.fn().mockResolvedValue(null),
}));

// Mock Supabase client
vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn().mockResolvedValue({
    auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: "auth-1" } } }) },
    storage: {
      from: vi.fn().mockReturnValue({
        upload: vi.fn().mockResolvedValue({ error: null }),
      }),
    },
  }),
}));

// Mock DB — captures mutations so we can inspect them
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockDb: any = {
  select: vi.fn().mockImplementation((fields?: unknown) => ({
    from: vi.fn().mockReturnValue({
      where: vi.fn().mockImplementation(() => {
        // Count query
        if (fields && typeof fields === "object" && "value" in (fields as Record<string, unknown>)) {
          return [{ value: historyRows.length }];
        }
        // Profile lookup (limit chain)
        return {
          limit: vi.fn().mockImplementation(() => {
            return profileRow ? [profileRow] : [];
          }),
          orderBy: vi.fn().mockImplementation(() => feedRows),
        };
      }),
    }),
  })),
  update: vi.fn().mockReturnValue({
    set: vi.fn().mockImplementation((data: Record<string, unknown>) => {
      // Apply update to profileRow
      if (profileRow) Object.assign(profileRow, data);
      return { where: vi.fn().mockResolvedValue(undefined) };
    }),
  }),
  insert: vi.fn().mockImplementation(() => ({
    values: vi.fn().mockImplementation((data: unknown) => {
      // Track inserts for feeds and history
      if (Array.isArray(data)) {
        feedRows.push(...data);
        return { returning: vi.fn().mockReturnValue(data.map((d, i) => ({ ...d, id: `id-${i}` }))) };
      } else if (data && typeof data === "object" && "status" in (data as Record<string, unknown>)) {
        const record = { ...(data as Record<string, unknown>), id: `record-${historyRows.length}` };
        historyRows.push(record);
        return { returning: vi.fn().mockReturnValue([record]) };
      } else if (data && typeof data === "object") {
        feedRows.push(data as Record<string, unknown>);
        return { returning: vi.fn().mockReturnValue([{ ...(data as Record<string, unknown>), id: `feed-${feedRows.length}` }]) };
      }
      return { returning: vi.fn().mockReturnValue([]) };
    }),
  })),
  delete: vi.fn().mockReturnValue({
    where: vi.fn().mockImplementation(() => {
      feedRows.length = 0;
      return Promise.resolve(undefined);
    }),
  }),
};
mockDb.transaction = vi.fn().mockImplementation(
  async (cb: (tx: typeof mockDb) => Promise<void>) => cb(mockDb)
);

vi.mock("@/db", () => ({
  db: mockDb,
}));

describe("E2E: signup → onboarding → build → deliver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Start with a fresh profile (just signed up, pre-onboarding)
    profileRow = { id: "profile-1", authId: "auth-1", onboardingComplete: false };
    feedRows = [];
    historyRows = [];
  });

  it("completes the full user journey (async build)", async () => {
    // 1. User is authenticated
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockImplementation(() => Promise.resolve(profileRow));

    // 2. Complete onboarding
    const { completeOnboarding } = await import("@/actions/onboarding");
    await completeOnboarding({
      device: "kobo",
      deliveryMethod: "local",
      feeds: [
        { name: "Ars Technica", url: "https://feeds.arstechnica.com/arstechnica/index", category: "Technology" },
      ],
      title: "My Paper",
      readingTime: "15 min",
      totalArticleBudget: 8,
      includeImages: true,
      deliveryTime: "06:00",
      timezone: "UTC",
      googleDriveFolder: "Rakuten Kobo",
      recipientEmail: "",
    });

    // Verify onboarding set the flag
    expect(profileRow!.onboardingComplete).toBe(true);
    expect(profileRow!.device).toBe("kobo");
    expect(feedRows.length).toBeGreaterThanOrEqual(1);

    // 3. Trigger async build
    Object.assign(profileRow!, {
      title: "My Paper",
      language: "en",
      totalArticleBudget: 8,
      includeImages: true,
      deliveryMethod: "local",
      googleDriveFolder: "Rakuten Kobo",
      recipientEmail: "",
      googleTokens: null,
      timezone: "UTC",
    });

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    // 4. Verify async build was dispatched
    expect(result.success).toBe(true);
    expect(result.building).toBe(true);
    expect(mockDispatchBuild).toHaveBeenCalled();

    // 5. Verify a "building" record was created
    const buildingRecords = historyRows.filter((r) => r.status === "building");
    expect(buildingRecords.length).toBeGreaterThanOrEqual(1);
  });

  it("handles dispatch failure gracefully", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    Object.assign(profileRow!, {
      title: "My Paper",
      language: "en",
      totalArticleBudget: 8,
      includeImages: true,
      device: "kobo",
      deliveryMethod: "local",
      googleDriveFolder: "Rakuten Kobo",
      recipientEmail: "",
      googleTokens: null,
      timezone: "UTC",
    });
    mockGetUserProfile.mockImplementation(() => Promise.resolve(profileRow));

    // Add a feed so the build proceeds
    feedRows.push({ id: "f1", userId: "profile-1", name: "Feed", url: "https://example.com/rss", category: "News", position: 0 });

    mockDispatchBuild.mockRejectedValue(new Error("GitHub PAT invalid"));

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    expect(result.success).toBe(false);
    expect(result.error).toBe("GitHub PAT invalid");
  });
});
