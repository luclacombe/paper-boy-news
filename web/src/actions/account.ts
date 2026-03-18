"use server";

import { getAuthUser, getUserProfile } from "@/lib/auth";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";

export type AuthProvider = "google" | "email";

export interface AccountInfo {
  email: string;
  provider: AuthProvider;
}

export async function getAccountInfo(): Promise<AccountInfo | null> {
  const user = await getAuthUser();
  if (!user) return null;

  const provider: AuthProvider =
    user.app_metadata?.provider === "google" ? "google" : "email";

  return { email: user.email ?? "", provider };
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<{ success: true }> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  if (user.app_metadata?.provider === "google") {
    throw new Error("Password is managed by Google");
  }

  if (!currentPassword) {
    throw new Error("Current password is required");
  }

  if (newPassword.length < 8) {
    throw new Error("New password must be at least 8 characters");
  }

  // Verify current password
  const supabase = await createClient();
  const { error: signInError } = await supabase.auth.signInWithPassword({
    email: user.email!,
    password: currentPassword,
  });

  if (signInError) {
    throw new Error("Current password is incorrect");
  }

  // Set new password via admin
  const admin = createAdminClient();
  const { error: updateError } = await admin.auth.admin.updateUserById(
    user.id,
    { password: newPassword }
  );

  if (updateError) {
    throw new Error("Failed to update password");
  }

  return { success: true };
}

export async function deleteAccount(): Promise<{ success: true }> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const profile = await getUserProfile();
  if (!profile) throw new Error("Profile not found");

  const admin = createAdminClient();

  // Step 1: Delete profile first (cascades to user_feeds + delivery_history)
  // This removes credentials (Google tokens) before anything else,
  // so a partial failure never leaves sensitive data orphaned.
  await db
    .delete(userProfiles)
    .where(eq(userProfiles.authId, user.id));

  // Step 2: Clean up Supabase Storage (non-blocking)
  try {
    const { data: files } = await admin.storage
      .from("epubs")
      .list(user.id);

    if (files && files.length > 0) {
      const paths = files.map((f) => `${user.id}/${f.name}`);
      await admin.storage.from("epubs").remove(paths);
    }
  } catch {
    // Storage cleanup failure should not block account deletion
  }

  // Step 3: Delete auth user last (if this fails, credentials are already gone)
  const { error } = await admin.auth.admin.deleteUser(user.id);
  if (error) {
    throw new Error("Failed to delete account");
  }

  return { success: true };
}
