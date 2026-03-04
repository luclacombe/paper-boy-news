"use server";

import { getAuthUser } from "@/lib/auth";
import { db } from "@/db";
import { userProfiles, userFeeds } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { OnboardingData } from "@/types";

export async function completeOnboarding(
  data: OnboardingData
): Promise<void> {
  const user = await getAuthUser();
  if (!user) throw new Error("Not authenticated");

  // Get the user's profile ID
  const [profile] = await db
    .select({ id: userProfiles.id })
    .from(userProfiles)
    .where(eq(userProfiles.authId, user.id))
    .limit(1);

  if (!profile) throw new Error("Profile not found");

  // 1. Update user_profiles with device, delivery, schedule, newspaper settings
  await db
    .update(userProfiles)
    .set({
      device: data.device,
      deliveryMethod: data.deliveryMethod,
      title: data.title,
      readingTime: data.readingTime,
      maxArticlesPerFeed: data.maxArticlesPerFeed,
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

  // 2. Bulk insert feeds
  if (data.feeds.length > 0) {
    await db.insert(userFeeds).values(
      data.feeds.map((feed, index) => ({
        userId: profile.id,
        name: feed.name,
        url: feed.url,
        category: feed.category,
        position: index,
      }))
    );
  }
}
