/**
 * E2E integration test: signup → onboarding → build → deliver.
 *
 * Exercises the full server-action sequence with mocked DB and API layers.
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

// Mock API client
const mockBuildNewspaper = vi.fn();
const mockDeliverNewspaper = vi.fn();
vi.mock("@/lib/api-client", () => ({
  buildNewspaper: (...args: unknown[]) => mockBuildNewspaper(...args),
  deliverNewspaper: (...args: unknown[]) => mockDeliverNewspaper(...args),
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
vi.mock("@/db", () => ({
  db: {
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
        } else if (data && typeof data === "object" && "status" in (data as Record<string, unknown>)) {
          historyRows.push(data as Record<string, unknown>);
        } else if (data && typeof data === "object") {
          feedRows.push(data as Record<string, unknown>);
        }
        return Promise.resolve(undefined);
      }),
    })),
    delete: vi.fn().mockReturnValue({
      where: vi.fn().mockImplementation(() => {
        feedRows.length = 0;
        return Promise.resolve(undefined);
      }),
    }),
  },
}));

describe("E2E: signup → onboarding → build → deliver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Start with a fresh profile (just signed up, pre-onboarding)
    profileRow = { id: "profile-1", authId: "auth-1", onboardingComplete: false };
    feedRows = [];
    historyRows = [];
  });

  it("completes the full user journey", async () => {
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
      maxArticlesPerFeed: 8,
      includeImages: true,
      deliveryTime: "06:00",
      timezone: "UTC",
      googleDriveFolder: "Rakuten Kobo",
      kindleEmail: "",
      emailMethod: "gmail",
    });

    // Verify onboarding set the flag
    expect(profileRow!.onboardingComplete).toBe(true);
    expect(profileRow!.device).toBe("kobo");
    expect(feedRows.length).toBeGreaterThanOrEqual(1);

    // 3. Build newspaper
    mockBuildNewspaper.mockResolvedValue({
      success: true,
      epub_base64: "UEsDBBQ=",
      total_articles: 5,
      sections: [{ name: "Technology", headlines: ["New chip announced"] }],
      file_size: "22 KB",
      file_size_bytes: 22000,
      error: null,
    });

    // Ensure profile now has all needed fields for build
    Object.assign(profileRow!, {
      title: "My Paper",
      language: "en",
      maxArticlesPerFeed: 8,
      includeImages: true,
      deliveryMethod: "local",
      googleDriveFolder: "Rakuten Kobo",
      kindleEmail: "",
      emailSmtpHost: "smtp.gmail.com",
      emailSmtpPort: 465,
      emailSender: "",
      emailPassword: "",
      googleTokens: null,
    });

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    // 4. Verify build succeeded
    expect(result.success).toBe(true);
    expect(result.totalArticles).toBe(5);
    expect(result.sections).toHaveLength(1);
    expect(result.fileSize).toBe("22 KB");

    // 5. Verify delivery history was recorded
    expect(historyRows.length).toBeGreaterThanOrEqual(1);
    const lastRecord = historyRows[historyRows.length - 1];
    expect(lastRecord.status).toBe("delivered");
    expect(lastRecord.articleCount).toBe(5);

    // 6. Local delivery → deliverNewspaper should NOT have been called
    expect(mockDeliverNewspaper).not.toHaveBeenCalled();
  });

  it("handles build failure gracefully", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    Object.assign(profileRow!, {
      title: "My Paper",
      language: "en",
      maxArticlesPerFeed: 8,
      includeImages: true,
      device: "kobo",
      deliveryMethod: "local",
      googleDriveFolder: "Rakuten Kobo",
      kindleEmail: "",
      emailSmtpHost: "smtp.gmail.com",
      emailSmtpPort: 465,
      emailSender: "",
      emailPassword: "",
      googleTokens: null,
    });
    mockGetUserProfile.mockImplementation(() => Promise.resolve(profileRow));

    // Add a feed so the build proceeds
    feedRows.push({ id: "f1", userId: "profile-1", name: "Feed", url: "https://example.com/rss", category: "News", position: 0 });

    mockBuildNewspaper.mockRejectedValue(new Error("API down"));

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(false);
    expect(result.error).toBe("API down");

    // History should record the failure
    expect(historyRows.length).toBeGreaterThanOrEqual(1);
    expect(historyRows[historyRows.length - 1].status).toBe("failed");
  });
});
