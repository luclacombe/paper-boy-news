"use server";

import { getAuthUser, getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userFeeds, deliveryHistory } from "@/db/schema";
import { eq, asc, count } from "drizzle-orm";
import { dispatchBuild } from "@/lib/github-dispatch";
import { getEditionDate } from "@/lib/edition-date";
import { getEditionForDate } from "@/actions/delivery-history";
import type { BuildResult } from "@/types";

function errorResult(error: string, editionDate: string): BuildResult {
  return {
    success: false,
    editionDate,
    totalArticles: 0,
    sections: [],
    fileSize: "0 KB",
    fileSizeBytes: 0,
    epubStoragePath: null,
    error,
  };
}

export async function getItNow(): Promise<BuildResult> {
  const user = await getAuthUser();
  if (!user) return errorResult("Not authenticated", "");

  const profile = await getUserProfile();
  if (!profile) return errorResult("Profile not found", "");

  const editionDate = getEditionDate(profile.timezone);

  // One-per-day guard: return existing edition if already built/delivered
  const existing = await getEditionForDate(editionDate);
  if (existing && existing.status === "delivered") {
    return {
      success: true,
      editionDate,
      totalArticles: existing.articleCount,
      sections: existing.sections ?? [],
      fileSize: existing.fileSize,
      fileSizeBytes: existing.fileSizeBytes,
      epubStoragePath: existing.epubStoragePath,
      error: null,
    };
  }
  if (existing && existing.status === "building") {
    return {
      success: true,
      building: true,
      editionDate,
      totalArticles: 0,
      sections: [],
      fileSize: "0 KB",
      fileSizeBytes: 0,
      epubStoragePath: null,
      error: null,
    };
  }

  // 1. Load feeds from DB
  const feeds = await db
    .select()
    .from(userFeeds)
    .where(eq(userFeeds.userId, profile.id))
    .orderBy(asc(userFeeds.position));

  if (feeds.length === 0) {
    return errorResult("No feeds configured. Add sources first.", editionDate);
  }

  // Get edition number
  const [editionCount] = await db
    .select({ value: count() })
    .from(deliveryHistory)
    .where(eq(deliveryHistory.userId, profile.id));
  const editionNumber = (editionCount?.value ?? 0) + 1;

  // 2. Insert delivery_history with status "building"
  const [record] = await db
    .insert(deliveryHistory)
    .values({
      userId: profile.id,
      status: "building",
      editionNumber,
      editionDate,
      sourceCount: feeds.length,
      deliveryMethod: profile.deliveryMethod,
    })
    .returning({ id: deliveryHistory.id });

  // 3. Fire GitHub Actions repository_dispatch
  try {
    await dispatchBuild(record.id);
  } catch (err) {
    // If dispatch fails, mark record as failed
    const errorMsg =
      err instanceof Error ? err.message : "Failed to start build";

    await db
      .update(deliveryHistory)
      .set({ status: "failed", errorMessage: errorMsg })
      .where(eq(deliveryHistory.id, record.id));

    return errorResult(errorMsg, editionDate);
  }

  // 4. Return immediately — dashboard will poll for completion
  return {
    success: true,
    building: true,
    editionDate,
    totalArticles: 0,
    sections: [],
    fileSize: "0 KB",
    fileSizeBytes: 0,
    epubStoragePath: null,
    error: null,
  };
}
