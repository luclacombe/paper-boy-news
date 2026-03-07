"use server";

import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { UserConfig } from "@/types";

export async function getUserConfig(): Promise<UserConfig | null> {
  const profile = await getUserProfile();
  if (!profile) return null;

  return {
    id: profile.id,
    authId: profile.authId,
    title: profile.title,
    language: profile.language,
    maxArticlesPerFeed: profile.maxArticlesPerFeed,
    readingTime: profile.readingTime,
    includeImages: profile.includeImages,
    device: profile.device as UserConfig["device"],
    deliveryMethod: profile.deliveryMethod as UserConfig["deliveryMethod"],
    googleDriveFolder: profile.googleDriveFolder,
    kindleEmail: profile.kindleEmail ?? "",
    emailMethod: (profile.emailMethod ?? "gmail") as UserConfig["emailMethod"],
    emailSmtpHost: profile.emailSmtpHost ?? "smtp.gmail.com",
    emailSmtpPort: profile.emailSmtpPort ?? 465,
    emailSender: profile.emailSender ?? "",
    emailPassword: profile.emailPassword ?? "",
    deliveryTime: profile.deliveryTime,
    timezone: profile.timezone,
    googleTokens: profile.googleTokens as UserConfig["googleTokens"],
    onboardingComplete: profile.onboardingComplete,
    createdAt: profile.createdAt.toISOString(),
    updatedAt: profile.updatedAt.toISOString(),
  };
}

export async function updateUserConfig(
  data: Partial<UserConfig>
): Promise<void> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  const updates: Record<string, unknown> = {};
  if (data.title !== undefined) updates.title = data.title;
  if (data.language !== undefined) updates.language = data.language;
  if (data.maxArticlesPerFeed !== undefined)
    updates.maxArticlesPerFeed = data.maxArticlesPerFeed;
  if (data.readingTime !== undefined) updates.readingTime = data.readingTime;
  if (data.includeImages !== undefined)
    updates.includeImages = data.includeImages;
  if (data.device !== undefined) updates.device = data.device;
  if (data.deliveryMethod !== undefined)
    updates.deliveryMethod = data.deliveryMethod;
  if (data.googleDriveFolder !== undefined)
    updates.googleDriveFolder = data.googleDriveFolder;
  if (data.kindleEmail !== undefined) updates.kindleEmail = data.kindleEmail;
  if (data.emailMethod !== undefined) updates.emailMethod = data.emailMethod;
  if (data.emailSmtpHost !== undefined)
    updates.emailSmtpHost = data.emailSmtpHost;
  if (data.emailSmtpPort !== undefined)
    updates.emailSmtpPort = data.emailSmtpPort;
  if (data.emailSender !== undefined) updates.emailSender = data.emailSender;
  if (data.emailPassword !== undefined)
    updates.emailPassword = data.emailPassword;
  if (data.deliveryTime !== undefined) updates.deliveryTime = data.deliveryTime;
  if (data.timezone !== undefined) updates.timezone = data.timezone;

  if (Object.keys(updates).length === 0) return;

  updates.updatedAt = new Date();

  await db
    .update(userProfiles)
    .set(updates)
    .where(eq(userProfiles.authId, user.id));
}

export async function isOnboardingComplete(): Promise<boolean> {
  const profile = await getUserProfile();
  return profile?.onboardingComplete ?? false;
}
