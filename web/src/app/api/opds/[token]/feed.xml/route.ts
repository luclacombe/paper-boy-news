import { NextResponse } from "next/server";
import { db } from "@/db";
import { userProfiles, deliveryHistory } from "@/db/schema";
import { eq, and, inArray, isNotNull, desc } from "drizzle-orm";
import { buildOpdsFeed, type OpdsEdition } from "@/lib/opds";

const TOKEN_PATTERN = /^[a-f0-9]{64}$/;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;

  // Validate token format before DB query
  if (!TOKEN_PATTERN.test(token)) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  // Look up user by token
  const [profile] = await db
    .select({ id: userProfiles.id, title: userProfiles.title })
    .from(userProfiles)
    .where(eq(userProfiles.opdsToken, token))
    .limit(1);

  if (!profile) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  // Fetch recent editions with EPUBs
  const editions = await db
    .select({
      id: deliveryHistory.id,
      editionDate: deliveryHistory.editionDate,
      articleCount: deliveryHistory.articleCount,
      sourceCount: deliveryHistory.sourceCount,
      fileSize: deliveryHistory.fileSize,
      epubStoragePath: deliveryHistory.epubStoragePath,
    })
    .from(deliveryHistory)
    .where(
      and(
        eq(deliveryHistory.userId, profile.id),
        isNotNull(deliveryHistory.epubStoragePath),
        inArray(deliveryHistory.status, ["built", "delivered"])
      )
    )
    .orderBy(desc(deliveryHistory.editionDate))
    .limit(30);

  const baseUrl = process.env.NEXT_PUBLIC_APP_URL!;
  const selfUrl = `${baseUrl}/api/opds/${token}/feed.xml`;

  const opdsEditions: OpdsEdition[] = editions.map((e) => ({
    id: e.id,
    editionDate: e.editionDate,
    articleCount: e.articleCount ?? 0,
    sourceCount: e.sourceCount ?? 0,
    fileSize: e.fileSize ?? "0 KB",
    downloadUrl: `${baseUrl}/api/opds/${token}/download/${e.id}`,
  }));

  const xml = buildOpdsFeed(opdsEditions, profile.title, selfUrl, profile.id);

  return new NextResponse(xml, {
    status: 200,
    headers: {
      "Content-Type": "application/atom+xml;profile=opds-catalog;kind=acquisition",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
