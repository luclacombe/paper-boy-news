"use server";

import crypto from "crypto";
import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";

function buildOpdsUrl(token: string): string {
  return `${process.env.NEXT_PUBLIC_APP_URL}/api/opds/${token}/feed.xml`;
}

export async function enableOpdsSync(): Promise<{ url: string }> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const profile = await getUserProfile();
  if (!profile) throw new Error("Profile not found");

  // Idempotent: if already enabled, return existing URL
  if (profile.opdsToken) {
    return { url: buildOpdsUrl(profile.opdsToken) };
  }

  const token = crypto.randomBytes(32).toString("hex");

  await db
    .update(userProfiles)
    .set({ opdsToken: token, updatedAt: new Date() })
    .where(eq(userProfiles.id, profile.id));

  return { url: buildOpdsUrl(token) };
}

export async function disableOpdsSync(): Promise<void> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const profile = await getUserProfile();
  if (!profile) throw new Error("Profile not found");

  await db
    .update(userProfiles)
    .set({ opdsToken: null, updatedAt: new Date() })
    .where(eq(userProfiles.id, profile.id));
}

export async function regenerateOpdsUrl(): Promise<{ url: string }> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const profile = await getUserProfile();
  if (!profile) throw new Error("Profile not found");

  const token = crypto.randomBytes(32).toString("hex");

  await db
    .update(userProfiles)
    .set({ opdsToken: token, updatedAt: new Date() })
    .where(eq(userProfiles.id, profile.id));

  return { url: buildOpdsUrl(token) };
}
