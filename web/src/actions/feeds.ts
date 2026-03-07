"use server";

import { getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { userFeeds } from "@/db/schema";
import { eq, asc } from "drizzle-orm";
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
    .where(eq(userFeeds.id, feedId));
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
