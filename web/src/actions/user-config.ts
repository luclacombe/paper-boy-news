"use server";

import { z } from "zod";
import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { UserConfig } from "@/types";

const userConfigUpdateSchema = z.object({
  title: z.string().min(1).max(100),
  language: z.string().min(2).max(10),
  totalArticleBudget: z.number().int().min(1).max(100),
  readingTime: z.string().regex(/^\d+\s+min$/),
  includeImages: z.boolean(),
  device: z.enum(["kobo", "kindle", "remarkable", "other"]),
  deliveryMethod: z.enum(["local", "google_drive", "email", "koreader"]),
  googleDriveFolder: z.string().max(100),
  recipientEmail: z.union([z.string().email().max(254), z.literal("")]),
  deliveryTime: z.string().regex(/^\d{2}:\d{2}$/),
  timezone: z.string().min(1).max(64),
}).partial();

export async function getUserConfig(): Promise<UserConfig | null> {
  const profile = await getUserProfile();
  if (!profile) return null;

  return {
    id: profile.id,
    authId: profile.authId,
    title: profile.title,
    language: profile.language,
    totalArticleBudget: profile.totalArticleBudget,
    readingTime: profile.readingTime,
    includeImages: profile.includeImages,
    device: profile.device as UserConfig["device"],
    deliveryMethod: profile.deliveryMethod as UserConfig["deliveryMethod"],
    googleDriveFolder: profile.googleDriveFolder,
    recipientEmail: profile.recipientEmail ?? "",
    deliveryTime: profile.deliveryTime,
    timezone: profile.timezone,
    opdsToken: profile.opdsToken ?? null,
    opdsTokenExpiresAt: profile.opdsTokenExpiresAt?.toISOString() ?? null,
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

  // Validate input
  const parsed = userConfigUpdateSchema.safeParse(data);
  if (!parsed.success) throw new Error("Invalid configuration data");
  const v = parsed.data;

  const updates: Record<string, unknown> = {};
  if (v.title !== undefined) updates.title = v.title;
  if (v.language !== undefined) updates.language = v.language;
  if (v.totalArticleBudget !== undefined)
    updates.totalArticleBudget = v.totalArticleBudget;
  if (v.readingTime !== undefined) updates.readingTime = v.readingTime;
  if (v.includeImages !== undefined) updates.includeImages = v.includeImages;
  if (v.device !== undefined) updates.device = v.device;
  if (v.deliveryMethod !== undefined)
    updates.deliveryMethod = v.deliveryMethod;
  if (v.googleDriveFolder !== undefined)
    updates.googleDriveFolder = v.googleDriveFolder;
  if (v.recipientEmail !== undefined)
    updates.recipientEmail = v.recipientEmail;
  if (v.deliveryTime !== undefined) updates.deliveryTime = v.deliveryTime;
  if (v.timezone !== undefined) updates.timezone = v.timezone;

  if (Object.keys(updates).length === 0) return;

  updates.updatedAt = new Date();

  await db
    .update(userProfiles)
    .set(updates)
    .where(eq(userProfiles.authId, user.id));
}

