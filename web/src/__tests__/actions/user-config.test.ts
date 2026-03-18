import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetAuthUser = vi.fn();
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB
const mockUpdate = vi.fn().mockReturnThis();
const mockSet = vi.fn().mockReturnThis();
const mockWhere = vi.fn().mockResolvedValue(undefined);

vi.mock("@/db", () => ({
  db: {
    update: (...args: unknown[]) => {
      mockUpdate(...args);
      return { set: (...a: unknown[]) => { mockSet(...a); return { where: mockWhere }; } };
    },
  },
}));

const FAKE_PROFILE = {
  id: "profile-1",
  authId: "auth-1",
  title: "Morning Digest",
  language: "en",
  totalArticleBudget: 10,
  readingTime: "20 min",
  includeImages: true,
  device: "kobo",
  deliveryMethod: "local",
  googleDriveFolder: "Rakuten Kobo",
  recipientEmail: "",
  deliveryTime: "06:00",
  timezone: "UTC",
  googleTokens: null,
  onboardingComplete: true,
  createdAt: new Date("2025-01-01"),
  updatedAt: new Date("2025-01-01"),
};

describe("getUserConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when user is not authenticated", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { getUserConfig } = await import("@/actions/user-config");
    const result = await getUserConfig();
    expect(result).toBeNull();
  });

  it("returns UserConfig for authenticated user", async () => {
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    const { getUserConfig } = await import("@/actions/user-config");
    const result = await getUserConfig();
    expect(result).not.toBeNull();
    expect(result!.id).toBe("profile-1");
    expect(result!.title).toBe("Morning Digest");
    expect(result!.device).toBe("kobo");
    expect(result!.createdAt).toBe("2025-01-01T00:00:00.000Z");
  });
});

describe("updateUserConfig", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when user is not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { updateUserConfig } = await import("@/actions/user-config");
    await expect(updateUserConfig({ title: "New" })).rejects.toThrow(
      "Not authenticated"
    );
  });

  it("updates only provided fields", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    const { updateUserConfig } = await import("@/actions/user-config");
    await updateUserConfig({ title: "New Title" });

    expect(mockSet).toHaveBeenCalledWith(
      expect.objectContaining({ title: "New Title" })
    );
    // Should NOT contain fields not provided
    const setArg = mockSet.mock.calls[0][0];
    expect(setArg).not.toHaveProperty("device");
  });

  it("no-ops when data is empty", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    const { updateUserConfig } = await import("@/actions/user-config");
    await updateUserConfig({});
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

describe("isOnboardingComplete", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false when profile not found", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { isOnboardingComplete } = await import("@/actions/user-config");
    const result = await isOnboardingComplete();
    expect(result).toBe(false);
  });

  it("returns actual onboardingComplete flag", async () => {
    mockGetUserProfile.mockResolvedValue({
      ...FAKE_PROFILE,
      onboardingComplete: true,
    });
    const { isOnboardingComplete } = await import("@/actions/user-config");
    const result = await isOnboardingComplete();
    expect(result).toBe(true);
  });
});
