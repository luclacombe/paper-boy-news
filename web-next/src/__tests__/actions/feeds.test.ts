import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: vi.fn(),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB — chainable query builder
const mockDbResult: unknown[] = [];
const mockInsertValues = vi.fn().mockResolvedValue(undefined);
const mockDeleteWhere = vi.fn().mockResolvedValue(undefined);

vi.mock("@/db", () => ({
  db: {
    select: vi.fn().mockReturnValue({
      from: vi.fn().mockReturnValue({
        where: vi.fn().mockReturnValue({
          orderBy: vi.fn().mockImplementation(() => mockDbResult),
        }),
      }),
    }),
    insert: vi.fn().mockReturnValue({
      values: mockInsertValues,
    }),
    delete: vi.fn().mockReturnValue({
      where: mockDeleteWhere,
    }),
  },
}));

const FAKE_PROFILE = {
  id: "profile-1",
  authId: "auth-1",
};

const FAKE_FEED_ROW = {
  id: "feed-1",
  userId: "profile-1",
  name: "Ars Technica",
  url: "https://feeds.arstechnica.com/arstechnica/index",
  category: "Technology",
  position: 0,
  createdAt: new Date("2025-01-01"),
};

describe("getFeeds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDbResult.length = 0;
  });

  it("returns empty array when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { getFeeds } = await import("@/actions/feeds");
    const result = await getFeeds();
    expect(result).toEqual([]);
  });

  it("returns mapped feeds for authenticated user", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockDbResult.push(FAKE_FEED_ROW);
    const { getFeeds } = await import("@/actions/feeds");
    const result = await getFeeds();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Ars Technica");
    expect(result[0].createdAt).toBe("2025-01-01T00:00:00.000Z");
  });
});

describe("addFeed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDbResult.length = 0;
  });

  it("throws when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { addFeed } = await import("@/actions/feeds");
    await expect(addFeed("Test", "https://example.com/rss", "Custom")).rejects.toThrow(
      "Not authenticated"
    );
  });

  it("inserts a feed with correct values", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    // No existing feeds
    const { addFeed } = await import("@/actions/feeds");
    await addFeed("New Feed", "https://example.com/rss", "Tech");
    expect(mockInsertValues).toHaveBeenCalled();
  });
});

describe("removeFeed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { removeFeed } = await import("@/actions/feeds");
    await expect(removeFeed("feed-1")).rejects.toThrow("Not authenticated");
  });

  it("deletes by feed ID", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    const { removeFeed } = await import("@/actions/feeds");
    await removeFeed("feed-1");
    expect(mockDeleteWhere).toHaveBeenCalled();
  });
});

describe("setFeeds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { setFeeds } = await import("@/actions/feeds");
    await expect(
      setFeeds([{ name: "F", url: "https://example.com", category: "C" }])
    ).rejects.toThrow("Not authenticated");
  });

  it("deletes all then bulk inserts", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    const { setFeeds } = await import("@/actions/feeds");
    await setFeeds([
      { name: "Feed 1", url: "https://example.com/1", category: "News" },
      { name: "Feed 2", url: "https://example.com/2", category: "Tech" },
    ]);
    expect(mockDeleteWhere).toHaveBeenCalled();
    expect(mockInsertValues).toHaveBeenCalled();
  });

  it("handles empty feeds array (delete only)", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    const { setFeeds } = await import("@/actions/feeds");
    await setFeeds([]);
    expect(mockDeleteWhere).toHaveBeenCalled();
    expect(mockInsertValues).not.toHaveBeenCalled();
  });
});
