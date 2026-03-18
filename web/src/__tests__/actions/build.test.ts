import { describe, it, expect, vi, beforeEach } from "vitest";

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
const mockGetEditionForDate = vi.fn().mockResolvedValue(null);
vi.mock("@/actions/delivery-history", () => ({
  getEditionForDate: (...args: unknown[]) => mockGetEditionForDate(...args),
}));

// Mock DB
const mockFeedRows: unknown[] = [];
const mockCountResult = [{ value: 0 }];
const mockInsertReturning = vi.fn().mockImplementation(() => [{ id: "record-1" }]);
const mockUpdateSet = vi.fn().mockReturnValue({
  where: vi.fn().mockResolvedValue(undefined),
});

vi.mock("@/db", () => ({
  db: {
    select: vi.fn().mockImplementation((fields?: unknown) => ({
      from: vi.fn().mockReturnValue({
        where: vi.fn().mockImplementation(() => {
          if (fields && typeof fields === "object" && "value" in (fields as Record<string, unknown>)) {
            return mockCountResult;
          }
          return {
            orderBy: vi.fn().mockImplementation(() => mockFeedRows),
          };
        }),
      }),
    })),
    insert: vi.fn().mockReturnValue({
      values: vi.fn().mockReturnValue({
        returning: mockInsertReturning,
      }),
    }),
    update: vi.fn().mockReturnValue({
      set: mockUpdateSet,
    }),
  },
}));

const FAKE_PROFILE = {
  id: "profile-1",
  authId: "auth-1",
  title: "Morning Digest",
  language: "en",
  totalArticleBudget: 10,
  includeImages: true,
  device: "kobo",
  deliveryMethod: "local",
  googleDriveFolder: "Rakuten Kobo",
  recipientEmail: "",
  googleTokens: null,
  timezone: "UTC",
};

describe("getItNow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFeedRows.length = 0;
    mockCountResult[0] = { value: 0 };
    mockGetEditionForDate.mockResolvedValue(null);
    mockDispatchBuild.mockResolvedValue(undefined);
    mockInsertReturning.mockReturnValue([{ id: "record-1" }]);
  });

  it("returns error when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();
    expect(result.success).toBe(false);
    expect(result.error).toBe("Not authenticated");
  });

  it("returns error when profile not found", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(null);
    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();
    expect(result.success).toBe(false);
    expect(result.error).toBe("Profile not found");
  });

  it("returns error when no feeds configured", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    // mockFeedRows stays empty
    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();
    expect(result.success).toBe(false);
    expect(result.error).toContain("No feeds");
  });

  it("returns existing edition without rebuilding", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockGetEditionForDate.mockResolvedValue({
      status: "delivered",
      articleCount: 10,
      sections: [{ name: "World", headlines: ["Headline 1"] }],
      fileSize: "1 MB",
      fileSizeBytes: 1000000,
      epubStoragePath: "path/to/epub",
    });

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    expect(result.success).toBe(true);
    expect(result.totalArticles).toBe(10);
    expect(mockDispatchBuild).not.toHaveBeenCalled();
  });

  it("returns building=true when edition is already building", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockGetEditionForDate.mockResolvedValue({
      status: "building",
      articleCount: 0,
      sections: null,
      fileSize: "0 KB",
      fileSizeBytes: 0,
      epubStoragePath: null,
    });

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    expect(result.success).toBe(true);
    expect(result.building).toBe(true);
    expect(mockDispatchBuild).not.toHaveBeenCalled();
  });

  it("creates building record and dispatches to GitHub Actions", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    expect(result.success).toBe(true);
    expect(result.building).toBe(true);
    expect(mockDispatchBuild).toHaveBeenCalledWith("record-1");
  });

  it("marks record as failed when GitHub dispatch fails", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockDispatchBuild.mockRejectedValue(new Error("GitHub dispatch not configured"));

    const { getItNow } = await import("@/actions/build");
    const result = await getItNow();

    expect(result.success).toBe(false);
    expect(result.error).toBe("GitHub dispatch not configured");
    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "failed",
        errorMessage: "GitHub dispatch not configured",
      })
    );
  });
});
