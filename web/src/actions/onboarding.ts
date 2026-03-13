"use server";

import { getAuthUser } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles, userFeeds } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { OnboardingData, Device, DeliveryMethod } from "@/types";

const VALID_DEVICES: Device[] = ["kobo", "kindle", "remarkable", "other"];
const VALID_DELIVERY_METHODS: DeliveryMethod[] = [
  "local",
  "google_drive",
  "email",
  "koreader",
];

function validateOnboardingData(data: OnboardingData): void {
  if (!VALID_DEVICES.includes(data.device)) {
    throw new Error("Invalid device");
  }
  if (!VALID_DELIVERY_METHODS.includes(data.deliveryMethod)) {
    throw new Error("Invalid delivery method");
  }
  if (!Array.isArray(data.feeds) || data.feeds.length === 0) {
    throw new Error("At least one feed is required");
  }
  for (const feed of data.feeds) {
    if (!feed.url || typeof feed.url !== "string") {
      throw new Error("Invalid feed URL");
    }
    if (!feed.name || typeof feed.name !== "string") {
      throw new Error("Invalid feed name");
    }
  }
  if (!data.deliveryTime || typeof data.deliveryTime !== "string") {
    throw new Error("Delivery time is required");
  }
  if (!data.timezone || typeof data.timezone !== "string") {
    throw new Error("Timezone is required");
  }
}

export async function getOnboardingStatus(): Promise<{
  isOnboarded: boolean;
}> {
  const user = await getAuthUser();
  if (!user) return { isOnboarded: false };

  const [profile] = await db
    .select({ onboardingComplete: userProfiles.onboardingComplete })
    .from(userProfiles)
    .where(eq(userProfiles.authId, user.id))
    .limit(1);

  return { isOnboarded: profile?.onboardingComplete ?? false };
}

export async function completeOnboarding(
  data: OnboardingData
): Promise<void> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  validateOnboardingData(data);

  // Get the user's profile ID
  const [profile] = await db
    .select({ id: userProfiles.id })
    .from(userProfiles)
    .where(eq(userProfiles.authId, user.id))
    .limit(1);

  if (!profile) throw new Error("Profile not found");

  // Atomic: update profile + replace feeds in a single transaction
  await db.transaction(async (tx) => {
    // 1. Update user_profiles with device, delivery, schedule, newspaper settings
    await tx
      .update(userProfiles)
      .set({
        device: data.device,
        deliveryMethod: data.deliveryMethod,
        title: data.title,
        readingTime: data.readingTime,
        totalArticleBudget: data.totalArticleBudget,
        includeImages: data.includeImages,
        deliveryTime: data.deliveryTime,
        timezone: data.timezone,
        googleDriveFolder: data.googleDriveFolder,
        kindleEmail: data.kindleEmail,
        emailMethod: data.emailMethod,
        onboardingComplete: true,
        updatedAt: new Date(),
      })
      .where(eq(userProfiles.id, profile.id));

    // 2. Clear existing feeds (idempotent: no-op on first onboarding)
    await tx.delete(userFeeds).where(eq(userFeeds.userId, profile.id));

    // 3. Insert new feeds
    if (data.feeds.length > 0) {
      await tx.insert(userFeeds).values(
        data.feeds.map((feed, index) => ({
          userId: profile.id,
          name: feed.name,
          url: feed.url,
          category: feed.category,
          position: index,
        }))
      );
    }
  });
}
