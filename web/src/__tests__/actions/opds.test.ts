import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetAuthUser = vi.fn();
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB
const mockUpdateSet = vi.fn().mockReturnValue({ where: vi.fn().mockResolvedValue(undefined) });
vi.mock("@/db", () => ({
  db: {
    update: vi.fn().mockReturnValue({
      set: (...args: unknown[]) => mockUpdateSet(...args),
    }),
  },
}));

vi.mock("@/db/schema", () => ({
  userProfiles: { id: "id" },
}));

// Mock env
vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://paper-boy.test");

const FAKE_USER = { id: "auth-1", email: "user@example.com" };
const FAKE_PROFILE = { id: "profile-1", authId: "auth-1", opdsToken: null };
const FAKE_PROFILE_WITH_TOKEN = {
  id: "profile-1",
  authId: "auth-1",
  opdsToken: "a".repeat(64),
};

describe("enableOpdsSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { enableOpdsSync } = await import("@/actions/opds");
    await expect(enableOpdsSync()).rejects.toThrow("Not authenticated");
  });

  it("generates 64-char hex token and returns URL", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    const { enableOpdsSync } = await import("@/actions/opds");
    const result = await enableOpdsSync();

    expect(result.url).toMatch(
      /^https:\/\/paper-boy\.test\/api\/opds\/[a-f0-9]{64}\/feed\.xml$/
    );
    expect(mockUpdateSet).toHaveBeenCalled();
  });

  it("returns existing URL when already enabled (idempotent)", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE_WITH_TOKEN);
    const { enableOpdsSync } = await import("@/actions/opds");
    const result = await enableOpdsSync();

    expect(result.url).toBe(
      `https://paper-boy.test/api/opds/${"a".repeat(64)}/feed.xml`
    );
    // Should NOT update DB
    expect(mockUpdateSet).not.toHaveBeenCalled();
  });
});

describe("disableOpdsSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { disableOpdsSync } = await import("@/actions/opds");
    await expect(disableOpdsSync()).rejects.toThrow("Not authenticated");
  });

  it("clears token", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE_WITH_TOKEN);
    const { disableOpdsSync } = await import("@/actions/opds");
    await disableOpdsSync();

    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({ opdsToken: null })
    );
  });
});

describe("regenerateOpdsUrl", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { regenerateOpdsUrl } = await import("@/actions/opds");
    await expect(regenerateOpdsUrl()).rejects.toThrow("Not authenticated");
  });

  it("generates new token different from old", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE_WITH_TOKEN);
    const { regenerateOpdsUrl } = await import("@/actions/opds");
    const result = await regenerateOpdsUrl();

    // New URL should be different from the old token
    expect(result.url).not.toContain("a".repeat(64));
    expect(result.url).toMatch(
      /^https:\/\/paper-boy\.test\/api\/opds\/[a-f0-9]{64}\/feed\.xml$/
    );
  });
});
