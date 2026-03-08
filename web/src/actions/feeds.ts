"use server";

import { getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userFeeds } from "@/db/schema";
import { eq, asc, and } from "drizzle-orm";
import type { Feed } from "@/types";

export async function getFeeds(): Promise<Feed[]> {
  const profile = await getUserProfile();
  if (!profile) return [];

  const rows = await db
    .select()
    .from(userFeeds)
    .where(eq(userFeeds.userId, profile.id))
    .orderBy(asc(userFeeds.position));

  return rows.map((row) => ({
    id: row.id,
    userId: row.userId,
    name: row.name,
    url: row.url,
    category: row.category,
    position: row.position,
    createdAt: row.createdAt.toISOString(),
  }));
}

export async function addFeed(
  name: string,
  url: string,
  category: string
): Promise<void> {
  const profile = await getUserProfile();
  if (!profile) throw new Error("Not authenticated");

  // Get the next position
  const existing = await db
    .select({ position: userFeeds.position })
    .from(userFeeds)
    .where(eq(userFeeds.userId, profile.id))
    .orderBy(asc(userFeeds.position));

  const nextPosition =
    existing.length > 0 ? existing[existing.length - 1].position + 1 : 0;

  await db.insert(userFeeds).values({
    userId: profile.id,
    name,
    url,
    category,
    position: nextPosition,
  });
}

export async function removeFeed(feedId: string): Promise<void> {
  const profile = await getUserProfile();
  if (!profile) throw new Error("Not authenticated");

  await db
    .delete(userFeeds)
    .where(and(eq(userFeeds.id, feedId), eq(userFeeds.userId, profile.id)));
}

export async function setFeeds(
  feeds: { name: string; url: string; category: string }[]
): Promise<void> {
  const profile = await getUserProfile();
  if (!profile) throw new Error("Not authenticated");

  // Delete all existing feeds, then bulk insert
  await db.delete(userFeeds).where(eq(userFeeds.userId, profile.id));

  if (feeds.length === 0) return;

  await db.insert(userFeeds).values(
    feeds.map((feed, index) => ({
      userId: profile.id,
      name: feed.name,
      url: feed.url,
      category: feed.category,
      position: index,
    }))
  );
}

export async function cleanOrphanedFeeds(): Promise<number> {
  const profile = await getUserProfile();
  if (!profile) return 0;

  const { getAllCatalogFeedUrls } = await import("@/lib/feed-catalog");
  const catalogUrls = getAllCatalogFeedUrls();

  const rows = await db
    .select()
    .from(userFeeds)
    .where(eq(userFeeds.userId, profile.id));

  const orphans = rows.filter(
    (row) => !catalogUrls.has(row.url) && row.category !== "Custom"
  );

  for (const orphan of orphans) {
    await db
      .delete(userFeeds)
      .where(and(eq(userFeeds.id, orphan.id), eq(userFeeds.userId, profile.id)));
  }

  return orphans.length;
}
