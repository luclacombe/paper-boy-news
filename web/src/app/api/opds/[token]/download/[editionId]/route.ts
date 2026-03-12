import { NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase/admin";
import { db } from "@/db";
import { userProfiles, deliveryHistory } from "@/db/schema";
import { eq, and } from "drizzle-orm";

const TOKEN_PATTERN = /^[a-f0-9]{64}$/;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export async function GET(
  _request: Request,
  {
    params,
  }: { params: Promise<{ token: string; editionId: string }> }
) {
  const { token, editionId } = await params;

  // Validate formats before DB queries
  if (!TOKEN_PATTERN.test(token) || !UUID_PATTERN.test(editionId)) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  // Look up user by token
  const [profile] = await db
    .select({ id: userProfiles.id })
    .from(userProfiles)
    .where(eq(userProfiles.opdsToken, token))
    .limit(1);

  if (!profile) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  // Look up edition — MUST belong to this user (cross-user isolation)
  const [edition] = await db
    .select({
      epubStoragePath: deliveryHistory.epubStoragePath,
      editionDate: deliveryHistory.editionDate,
    })
    .from(deliveryHistory)
    .where(
      and(
        eq(deliveryHistory.id, editionId),
        eq(deliveryHistory.userId, profile.id)
      )
    )
    .limit(1);

  if (!edition?.epubStoragePath) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  // Download from Supabase Storage via admin client
  const sb = createAdminClient();
  const { data, error } = await sb.storage
    .from("epubs")
    .download(edition.epubStoragePath);

  if (error || !data) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "X-Content-Type-Options": "nosniff" },
    });
  }

  const filename = edition.epubStoragePath.split("/").pop() ?? `paper-${edition.editionDate}.epub`;

  return new NextResponse(data, {
    status: 200,
    headers: {
      "Content-Type": "application/epub+zip",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "private, max-age=86400",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
