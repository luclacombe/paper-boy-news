"use server";

import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { GoogleTokens } from "@/types";

export async function getGoogleAuthUrl(): Promise<string> {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const redirectUri = `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/google/callback`;
  const scopes = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
  ].join(" ");

  return `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scopes)}&access_type=offline&prompt=consent`;
}

export async function disconnectGoogle(): Promise<void> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  await db
    .update(userProfiles)
    .set({ googleTokens: null, updatedAt: new Date() })
    .where(eq(userProfiles.authId, user.id));
}

export async function hasGmailScope(): Promise<boolean> {
  const profile = await getUserProfile();
  if (!profile?.googleTokens) return false;

  const tokens = profile.googleTokens as GoogleTokens;
  return (
    tokens.scopes?.includes("https://www.googleapis.com/auth/gmail.send") ??
    false
  );
}

export async function hasDriveScope(): Promise<boolean> {
  const profile = await getUserProfile();
  if (!profile?.googleTokens) return false;

  const tokens = profile.googleTokens as GoogleTokens;
  return (
    tokens.scopes?.includes("https://www.googleapis.com/auth/drive.file") ??
    false
  );
}
