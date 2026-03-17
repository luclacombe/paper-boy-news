"use server";

import crypto from "crypto";
import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";

/** OPDS tokens expire after 90 days. */
const OPDS_TOKEN_DAYS = 90;

function buildOpdsUrl(token: string): string {
  return `${process.env.NEXT_PUBLIC_APP_URL}/api/opds/${token}/feed.xml`;
}

function tokenExpiresAt(): Date {
  return new Date(Date.now() + OPDS_TOKEN_DAYS * 24 * 60 * 60 * 1000);
}

export async function enableOpdsSync(): Promise<{ url: string }> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const profile = await getUserProfile();
  if (!profile) throw new Error("Profile not found");

  // Idempotent: if already enabled and not expired, return existing URL
  if (profile.opdsToken) {
    const expired =
      profile.opdsTokenExpiresAt && profile.opdsTokenExpiresAt < new Date();
    if (!expired) {
      return { url: buildOpdsUrl(profile.opdsToken) };
    }
    // Token expired — fall through to regenerate
  }

  const token = crypto.randomBytes(32).toString("hex");

  await db
    .update(userProfiles)
    .set({
      opdsToken: token,
      opdsTokenExpiresAt: tokenExpiresAt(),
      updatedAt: new Date(),
    })
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
    .set({
      opdsToken: null,
      opdsTokenExpiresAt: null,
      updatedAt: new Date(),
    })
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
    .set({
      opdsToken: token,
      opdsTokenExpiresAt: tokenExpiresAt(),
      updatedAt: new Date(),
    })
    .where(eq(userProfiles.id, profile.id));

  return { url: buildOpdsUrl(token) };
}
