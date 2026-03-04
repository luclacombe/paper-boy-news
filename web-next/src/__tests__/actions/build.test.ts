import { describe, it, expect, vi, beforeEach } from "vitest";

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

// Mock Supabase client (for storage upload)
const mockUpload = vi.fn().mockResolvedValue({ error: null });
vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn().mockResolvedValue({
    auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: "auth-1" } } }) },
    storage: {
      from: vi.fn().mockReturnValue({ upload: mockUpload }),
    },
  }),
}));

// Mock DB
const mockFeedRows: unknown[] = [];
const mockCountResult = [{ value: 0 }];
const mockInsertValues = vi.fn().mockResolvedValue(undefined);

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
      values: mockInsertValues,
    }),
  },
}));

const FAKE_PROFILE = {
  id: "profile-1",
  authId: "auth-1",
  title: "Morning Digest",
  language: "en",
  maxArticlesPerFeed: 10,
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
};

const FAKE_BUILD_RESPONSE = {
  success: true,
  epub_base64: "UEsDBBQAAAA=", // minimal base64
  total_articles: 5,
  sections: [{ name: "Tech", headlines: ["Article 1", "Article 2"] }],
  file_size: "22 KB",
  file_size_bytes: 22000,
  error: null,
};

describe("triggerBuild", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFeedRows.length = 0;
    mockCountResult[0] = { value: 0 };
  });

  it("returns error when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();
    expect(result.success).toBe(false);
    expect(result.error).toBe("Not authenticated");
  });

  it("returns error when profile not found", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(null);
    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();
    expect(result.success).toBe(false);
    expect(result.error).toBe("Profile not found");
  });

  it("returns error when no feeds configured", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    // mockFeedRows stays empty
    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();
    expect(result.success).toBe(false);
    expect(result.error).toContain("No feeds");
  });

  it("calls buildNewspaper with correct request shape", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockBuildNewspaper.mockResolvedValue(FAKE_BUILD_RESPONSE);

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(true);
    expect(mockBuildNewspaper).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Morning Digest",
        language: "en",
        feeds: [{ name: "Feed 1", url: "https://example.com/rss" }],
      })
    );
  });

  it("records failure when build API throws", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockBuildNewspaper.mockRejectedValue(new Error("API unreachable"));

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(false);
    expect(result.error).toBe("API unreachable");
    // Delivery history should record failure
    expect(mockInsertValues).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "failed",
        errorMessage: "API unreachable",
      })
    );
  });

  it("records failure when build returns success=false", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockBuildNewspaper.mockResolvedValue({
      success: false,
      epub_base64: null,
      error: "No articles fetched",
    });

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(false);
    expect(result.error).toBe("No articles fetched");
  });

  it("skips deliver when method is local", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue({ ...FAKE_PROFILE, deliveryMethod: "local" });
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockBuildNewspaper.mockResolvedValue(FAKE_BUILD_RESPONSE);

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(true);
    expect(mockDeliverNewspaper).not.toHaveBeenCalled();
  });

  it("calls deliverNewspaper when method is not local", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockGetUserProfile.mockResolvedValue({
      ...FAKE_PROFILE,
      deliveryMethod: "google_drive",
      googleTokens: {
        token: "t",
        refreshToken: "r",
        tokenUri: "https://oauth2.googleapis.com/token",
        clientId: "cid",
        clientSecret: "cs",
        scopes: ["https://www.googleapis.com/auth/drive.file"],
        expiry: null,
      },
    });
    mockFeedRows.push(
      { id: "f1", userId: "profile-1", name: "Feed 1", url: "https://example.com/rss", category: "News", position: 0 }
    );
    mockBuildNewspaper.mockResolvedValue(FAKE_BUILD_RESPONSE);
    mockDeliverNewspaper.mockResolvedValue({ success: true, message: "Uploaded" });

    const { triggerBuild } = await import("@/actions/build");
    const result = await triggerBuild();

    expect(result.success).toBe(true);
    expect(mockDeliverNewspaper).toHaveBeenCalledWith(
      expect.objectContaining({
        delivery_method: "google_drive",
      })
    );
  });
});
