import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetAuthUser = vi.fn();
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB
const mockUpdateSet = vi.fn().mockReturnValue({
  where: vi.fn().mockResolvedValue(undefined),
});
vi.mock("@/db", () => ({
  db: {
    update: vi.fn().mockReturnValue({
      set: mockUpdateSet,
    }),
  },
}));

// Set env vars for Google OAuth
vi.stubEnv("GOOGLE_CLIENT_ID", "test-client-id");
vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://localhost:3000");

describe("getGoogleAuthUrl", () => {
  it("constructs URL with client_id and scopes", async () => {
    const { getGoogleAuthUrl } = await import("@/actions/google-oauth");
    const url = await getGoogleAuthUrl();
    expect(url).toContain("client_id=test-client-id");
    expect(url).toContain("drive.file");
    expect(url).toContain("gmail.send");
    expect(url).toContain("access_type=offline");
    expect(url).toContain("prompt=consent");
  });

  it("includes redirect URI from APP_URL", async () => {
    const { getGoogleAuthUrl } = await import("@/actions/google-oauth");
    const url = await getGoogleAuthUrl();
    expect(url).toContain(
      encodeURIComponent("http://localhost:3000/api/auth/google/callback")
    );
  });
});

describe("disconnectGoogle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { disconnectGoogle } = await import("@/actions/google-oauth");
    await expect(disconnectGoogle()).rejects.toThrow("Not authenticated");
  });

  it("sets googleTokens to null", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1" });
    const { disconnectGoogle } = await import("@/actions/google-oauth");
    await disconnectGoogle();
    expect(mockUpdateSet).toHaveBeenCalledWith(
      expect.objectContaining({ googleTokens: null })
    );
  });
});

describe("hasGmailScope", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false when no profile", async () => {
    mockGetUserProfile.mockResolvedValue(null);
    const { hasGmailScope } = await import("@/actions/google-oauth");
    expect(await hasGmailScope()).toBe(false);
  });

  it("returns false when no google tokens", async () => {
    mockGetUserProfile.mockResolvedValue({ googleTokens: null });
    const { hasGmailScope } = await import("@/actions/google-oauth");
    expect(await hasGmailScope()).toBe(false);
  });

  it("returns true when gmail.send scope is present", async () => {
    mockGetUserProfile.mockResolvedValue({
      googleTokens: {
        scopes: ["https://www.googleapis.com/auth/gmail.send"],
      },
    });
    const { hasGmailScope } = await import("@/actions/google-oauth");
    expect(await hasGmailScope()).toBe(true);
  });
});

describe("hasDriveScope", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns false when no tokens", async () => {
    mockGetUserProfile.mockResolvedValue({ googleTokens: null });
    const { hasDriveScope } = await import("@/actions/google-oauth");
    expect(await hasDriveScope()).toBe(false);
  });

  it("returns true when drive.file scope is present", async () => {
    mockGetUserProfile.mockResolvedValue({
      googleTokens: {
        scopes: ["https://www.googleapis.com/auth/drive.file"],
      },
    });
    const { hasDriveScope } = await import("@/actions/google-oauth");
    expect(await hasDriveScope()).toBe(true);
  });
});
