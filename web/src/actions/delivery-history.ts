"use server";

import { getUserProfile } from "@/lib/auth";
import { db } from "@/db";
import { deliveryHistory } from "@/db/schema";
import { eq, and, ne, desc, count } from "drizzle-orm";
import type { DeliveryRecord, SectionSummary } from "@/types";

export async function getDeliveryHistory(
  limit = 30
): Promise<DeliveryRecord[]> {
  const profile = await getUserProfile();
  if (!profile) return [];

  const rows = await db
    .select()
    .from(deliveryHistory)
    .where(eq(deliveryHistory.userId, profile.id))
    .orderBy(desc(deliveryHistory.createdAt))
    .limit(limit);

  return rows.map((row) => ({
    id: row.id,
    userId: row.userId,
    status: row.status as DeliveryRecord["status"],
    editionNumber: row.editionNumber ?? 0,
    editionDate: row.editionDate,
    articleCount: row.articleCount ?? 0,
    sourceCount: row.sourceCount ?? 0,
    fileSize: row.fileSize ?? "0 KB",
    fileSizeBytes: row.fileSizeBytes ?? 0,
    deliveryMethod: row.deliveryMethod ?? "",
    deliveryMessage: row.deliveryMessage ?? "",
    errorMessage: row.errorMessage,
    epubStoragePath: row.epubStoragePath,
    resendMessageId: row.resendMessageId,
    sections: (row.sections as SectionSummary[]) ?? null,
    createdAt: row.createdAt.toISOString(),
  }));
}

/** Get the latest non-failed edition for a specific date. */
export async function getEditionForDate(
  editionDate: string
): Promise<DeliveryRecord | null> {
  const profile = await getUserProfile();
  if (!profile) return null;

  const [row] = await db
    .select()
    .from(deliveryHistory)
    .where(
      and(
        eq(deliveryHistory.userId, profile.id),
        eq(deliveryHistory.editionDate, editionDate),
        ne(deliveryHistory.status, "failed")
      )
    )
    .orderBy(desc(deliveryHistory.createdAt))
    .limit(1);

  if (!row) return null;

  return {
    id: row.id,
    userId: row.userId,
    status: row.status as DeliveryRecord["status"],
    editionNumber: row.editionNumber ?? 0,
    editionDate: row.editionDate,
    articleCount: row.articleCount ?? 0,
    sourceCount: row.sourceCount ?? 0,
    fileSize: row.fileSize ?? "0 KB",
    fileSizeBytes: row.fileSizeBytes ?? 0,
    deliveryMethod: row.deliveryMethod ?? "",
    deliveryMessage: row.deliveryMessage ?? "",
    errorMessage: row.errorMessage,
    epubStoragePath: row.epubStoragePath,
    resendMessageId: row.resendMessageId,
    sections: (row.sections as SectionSummary[]) ?? null,
    createdAt: row.createdAt.toISOString(),
  };
}

/** Check if there's an active build (status = "building") for today's edition. */
export async function hasActiveBuild(editionDate: string): Promise<boolean> {
  const profile = await getUserProfile();
  if (!profile) return false;

  const [row] = await db
    .select({ id: deliveryHistory.id })
    .from(deliveryHistory)
    .where(
      and(
        eq(deliveryHistory.userId, profile.id),
        eq(deliveryHistory.editionDate, editionDate),
        eq(deliveryHistory.status, "building")
      )
    )
    .limit(1);

  return !!row;
}

export async function getEditionCount(): Promise<number> {
  const profile = await getUserProfile();
  if (!profile) return 0;

  const [result] = await db
    .select({ value: count() })
    .from(deliveryHistory)
    .where(eq(deliveryHistory.userId, profile.id));

  return result?.value ?? 0;
}
