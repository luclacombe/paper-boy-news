import { describe, it, expect, vi, beforeEach } from "vitest";
import type { OnboardingData } from "@/types";

// Mock auth
const mockGetAuthUser = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: vi.fn(),
}));

// Mock DB
const mockSelectResult: unknown[] = [];
const mockUpdateSet = vi.fn().mockReturnValue({
  where: vi.fn().mockResolvedValue(undefined),
});
const mockInsertValues = vi.fn().mockResolvedValue(undefined);
const mockDeleteWhere = vi.fn().mockResolvedValue(undefined);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockDb: any = {
  select: vi.fn().mockReturnValue({
    from: vi.fn().mockReturnValue({
      where: vi.fn().mockReturnValue({
        limit: vi.fn().mockImplementation(() => mockSelectResult),
      }),
    }),
  }),
  update: vi.fn().mockReturnValue({
    set: mockUpdateSet,
  }),
  insert: vi.fn().mockReturnValue({
    values: mockInsertValues,
  }),
  delete: vi.fn().mockReturnValue({
    where: mockDeleteWhere,
  }),
};
mockDb.transaction = vi.fn().mockImplementation(
  async (cb: (tx: typeof mockDb) => Promise<void>) => cb(mockDb)
);

vi.mock("@/db", () => ({
  db: mockDb,
}));

const ONBOARDING_DATA: OnboardingData = {
  device: "kindle",
  deliveryMethod: "email",
  feeds: [
    { name: "Ars Technica", url: "https://feeds.arstechnica.com/arstechnica/index", category: "Technology" },
    { name: "NPR", url: "https://feeds.npr.org/1001/rss.xml", category: "World News" },
  ],
  title: "My Paper",
  readingTime: "15 min",
  maxArticlesPerFeed: 8,
  includeImages: false,
  deliveryTime: "07:00",
  timezone: "US/Eastern",
  googleDriveFolder: "Rakuten Kobo",
  kindleEmail: "user@kindle.com",
  emailMethod: "gmail",
};

describe("completeOnboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectResult.length = 0;
  });

  it("throws when user is not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { completeOnboarding } = await import("@/actions/onboarding");
    await expect(completeOnboarding(ONBOARDING_DATA)).rejects.toThrow(
      "Not authenticated"
    );
  });

  it("throws when profile not found", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    // Empty result = no profile
    const { completeOnboarding } = await import("@/actions/onboarding");
    await expect(completeOnboarding(ONBOARDING_DATA)).rejects.toThrow(
      "Profile not found"
    );
  });

  it("updates profile and inserts feeds", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockSelectResult.push({ id: "profile-1" });

    const { completeOnboarding } = await import("@/actions/onboarding");
    await completeOnboarding(ONBOARDING_DATA);

    // Runs in a transaction
    expect(mockDb.transaction).toHaveBeenCalled();

    // Profile updated with onboarding fields
    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({
        device: "kindle",
        deliveryMethod: "email",
        title: "My Paper",
        onboardingComplete: true,
      })
    );

    // Existing feeds cleared before insert
    expect(mockDeleteWhere).toHaveBeenCalled();

    // Feeds bulk inserted with position indices
    expect(mockInsertValues).toHaveBeenCalled();
    const insertedFeeds = mockInsertValues.mock.calls[0][0];
    expect(insertedFeeds).toHaveLength(2);
    expect(insertedFeeds[0].position).toBe(0);
    expect(insertedFeeds[1].position).toBe(1);
  });

  it("rejects empty feeds array with validation error", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockSelectResult.push({ id: "profile-1" });

    const { completeOnboarding } = await import("@/actions/onboarding");
    await expect(
      completeOnboarding({ ...ONBOARDING_DATA, feeds: [] })
    ).rejects.toThrow("At least one feed is required");
  });

  it("rejects invalid device", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    mockSelectResult.push({ id: "profile-1" });

    const { completeOnboarding } = await import("@/actions/onboarding");
    await expect(
      completeOnboarding({ ...ONBOARDING_DATA, device: "invalid" as OnboardingData["device"] })
    ).rejects.toThrow("Invalid device");
  });
});
