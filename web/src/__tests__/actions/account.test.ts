import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock auth
const mockGetAuthUser = vi.fn();
const mockGetUserProfile = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuthUser: (...args: unknown[]) => mockGetAuthUser(...args),
  getUserProfile: (...args: unknown[]) => mockGetUserProfile(...args),
}));

// Mock DB
const mockDeleteWhere = vi.fn().mockResolvedValue(undefined);
vi.mock("@/db", () => ({
  db: {
    delete: vi.fn().mockReturnValue({
      where: (...args: unknown[]) => mockDeleteWhere(...args),
    }),
  },
}));

// Mock admin client
const mockAdminDeleteUser = vi.fn().mockResolvedValue({ error: null });
const mockAdminUpdateUserById = vi.fn().mockResolvedValue({ error: null });
const mockStorageList = vi.fn().mockResolvedValue({ data: [] });
const mockStorageRemove = vi.fn().mockResolvedValue({ error: null });

vi.mock("@/lib/supabase/admin", () => ({
  createAdminClient: () => ({
    auth: {
      admin: {
        deleteUser: (...args: unknown[]) => mockAdminDeleteUser(...args),
        updateUserById: (...args: unknown[]) =>
          mockAdminUpdateUserById(...args),
      },
    },
    storage: {
      from: () => ({
        list: (...args: unknown[]) => mockStorageList(...args),
        remove: (...args: unknown[]) => mockStorageRemove(...args),
      }),
    },
  }),
}));

// Mock Supabase server client (for sendPasswordReset)
const mockResetPasswordForEmail = vi.fn().mockResolvedValue({ error: null });
vi.mock("@/lib/supabase/server", () => ({
  createClient: () =>
    Promise.resolve({
      auth: {
        resetPasswordForEmail: (...args: unknown[]) =>
          mockResetPasswordForEmail(...args),
      },
    }),
}));

// Mock standalone Supabase client (for password verification in changePassword)
const mockSignInWithPassword = vi.fn();
vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: (...args: unknown[]) =>
        mockSignInWithPassword(...args),
    },
  }),
}));

const FAKE_USER_EMAIL = {
  id: "auth-1",
  email: "user@example.com",
  app_metadata: { provider: "email" },
};

const FAKE_USER_GOOGLE = {
  id: "auth-2",
  email: "user@gmail.com",
  app_metadata: { provider: "google" },
};

const FAKE_PROFILE = {
  id: "profile-1",
  authId: "auth-1",
};

describe("getAccountInfo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { getAccountInfo } = await import("@/actions/account");
    const result = await getAccountInfo();
    expect(result).toBeNull();
  });

  it("returns email and provider 'email' for email user", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    const { getAccountInfo } = await import("@/actions/account");
    const result = await getAccountInfo();
    expect(result).toEqual({
      email: "user@example.com",
      provider: "email",
    });
  });

  it("returns email and provider 'google' for Google user", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_GOOGLE);
    const { getAccountInfo } = await import("@/actions/account");
    const result = await getAccountInfo();
    expect(result).toEqual({
      email: "user@gmail.com",
      provider: "google",
    });
  });

  it("defaults to 'email' when app_metadata missing", async () => {
    mockGetAuthUser.mockResolvedValue({
      id: "auth-3",
      email: "test@test.com",
      app_metadata: {},
    });
    const { getAccountInfo } = await import("@/actions/account");
    const result = await getAccountInfo();
    expect(result?.provider).toBe("email");
  });
});

describe("changePassword", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("old", "newpass12")).rejects.toThrow(
      "Not authenticated"
    );
  });

  it("throws when Google OAuth user attempts password change", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_GOOGLE);
    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("old", "newpass12")).rejects.toThrow(
      "Password is managed by Google"
    );
  });

  it("throws when current password is empty", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("", "newpass12")).rejects.toThrow(
      "Current password is required"
    );
  });

  it("throws when new password is too short", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("oldpass", "short")).rejects.toThrow(
      "New password must be at least 8 characters"
    );
  });

  it("throws when current password is incorrect", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockSignInWithPassword.mockResolvedValue({
      error: { message: "Invalid credentials" },
    });
    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("wrong", "newpass12")).rejects.toThrow(
      "Current password is incorrect"
    );
  });

  it("successfully changes password", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockSignInWithPassword.mockResolvedValue({ error: null });
    mockAdminUpdateUserById.mockResolvedValue({ error: null });

    const { changePassword } = await import("@/actions/account");
    const result = await changePassword("correctpass", "newpass12");

    expect(result).toEqual({ success: true });
    expect(mockSignInWithPassword).toHaveBeenCalledWith({
      email: "user@example.com",
      password: "correctpass",
    });
    expect(mockAdminUpdateUserById).toHaveBeenCalledWith("auth-1", {
      password: "newpass12",
    });
  });

  it("throws when admin update fails", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockSignInWithPassword.mockResolvedValue({ error: null });
    mockAdminUpdateUserById.mockResolvedValue({
      error: { message: "Internal error" },
    });

    const { changePassword } = await import("@/actions/account");
    await expect(changePassword("correctpass", "newpass12")).rejects.toThrow(
      "Failed to update password"
    );
  });
});

describe("deleteAccount", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { deleteAccount } = await import("@/actions/account");
    await expect(deleteAccount()).rejects.toThrow("Not authenticated");
  });

  it("throws when profile not found", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockGetUserProfile.mockResolvedValue(null);
    const { deleteAccount } = await import("@/actions/account");
    await expect(deleteAccount()).rejects.toThrow("Profile not found");
  });

  it("deletes profile first, cleans storage, then deletes auth user", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockStorageList.mockResolvedValue({
      data: [{ name: "paper-2025-01-01.epub" }],
    });
    mockAdminDeleteUser.mockResolvedValue({ error: null });

    const { deleteAccount } = await import("@/actions/account");
    const result = await deleteAccount();

    expect(result).toEqual({ success: true });
    expect(mockDeleteWhere).toHaveBeenCalled();
    expect(mockStorageList).toHaveBeenCalledWith("auth-1");
    expect(mockStorageRemove).toHaveBeenCalledWith([
      "auth-1/paper-2025-01-01.epub",
    ]);
    expect(mockAdminDeleteUser).toHaveBeenCalledWith("auth-1");
  });

  it("succeeds even when storage cleanup fails", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockStorageList.mockRejectedValue(new Error("Storage unavailable"));
    mockAdminDeleteUser.mockResolvedValue({ error: null });

    const { deleteAccount } = await import("@/actions/account");
    const result = await deleteAccount();

    expect(result).toEqual({ success: true });
    expect(mockAdminDeleteUser).toHaveBeenCalledWith("auth-1");
  });

  it("succeeds when no storage files exist", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockStorageList.mockResolvedValue({ data: [] });
    mockAdminDeleteUser.mockResolvedValue({ error: null });

    const { deleteAccount } = await import("@/actions/account");
    const result = await deleteAccount();

    expect(result).toEqual({ success: true });
    expect(mockStorageRemove).not.toHaveBeenCalled();
  });

  it("throws when auth deletion fails but profile is already deleted", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockGetUserProfile.mockResolvedValue(FAKE_PROFILE);
    mockAdminDeleteUser.mockResolvedValue({
      error: { message: "Cannot delete" },
    });

    const { deleteAccount } = await import("@/actions/account");
    await expect(deleteAccount()).rejects.toThrow("Failed to delete account");
    // Profile is deleted first (credentials cleaned up), even if auth deletion fails
    expect(mockDeleteWhere).toHaveBeenCalled();
  });
});

describe("sendPasswordReset", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("throws when not authenticated", async () => {
    mockGetAuthUser.mockResolvedValue(null);
    const { sendPasswordReset } = await import("@/actions/account");
    await expect(sendPasswordReset()).rejects.toThrow("Not authenticated");
  });

  it("throws when user has no email", async () => {
    mockGetAuthUser.mockResolvedValue({ id: "auth-1", app_metadata: {} });
    const { sendPasswordReset } = await import("@/actions/account");
    await expect(sendPasswordReset()).rejects.toThrow("Not authenticated");
  });

  it("sends reset email successfully", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockResetPasswordForEmail.mockResolvedValue({ error: null });

    const { sendPasswordReset } = await import("@/actions/account");
    const result = await sendPasswordReset();

    expect(result).toEqual({ success: true });
    expect(mockResetPasswordForEmail).toHaveBeenCalledWith(
      "user@example.com",
      expect.objectContaining({ redirectTo: expect.stringContaining("/api/auth/confirm") })
    );
  });

  it("throws when Supabase returns an error", async () => {
    mockGetAuthUser.mockResolvedValue(FAKE_USER_EMAIL);
    mockResetPasswordForEmail.mockResolvedValue({
      error: { message: "Rate limit exceeded" },
    });

    const { sendPasswordReset } = await import("@/actions/account");
    await expect(sendPasswordReset()).rejects.toThrow(
      "Failed to send reset email"
    );
  });
});
