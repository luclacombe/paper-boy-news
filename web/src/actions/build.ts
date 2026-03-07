"use server";

import { getAuthUser, getUserProfile } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { db } from "@/db";
import { userFeeds, deliveryHistory } from "@/db/schema";
import { eq, asc, count } from "drizzle-orm";
import { buildNewspaper, deliverNewspaper } from "@/lib/api-client";
import { getEditionDate } from "@/lib/edition-date";
import { getEditionForDate } from "@/actions/delivery-history";
import type {
  BuildResult,
  ApiBuildRequest,
  ApiDeliverRequest,
  GoogleTokens,
  SectionSummary,
} from "@/types";

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
    return errorResult("A build is already in progress", editionDate);
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

  // 2. POST to FastAPI /build
  const buildRequest: ApiBuildRequest = {
    title: profile.title,
    language: profile.language,
    max_articles_per_feed: profile.maxArticlesPerFeed,
    include_images: profile.includeImages,
    feeds: feeds.map((f) => ({ name: f.name, url: f.url })),
    device: profile.device,
    edition_date: editionDate,
  };

  let buildResponse;
  try {
    buildResponse = await buildNewspaper(buildRequest);
  } catch (err) {
    const errorMsg =
      err instanceof Error ? err.message : "Build request failed";

    await db.insert(deliveryHistory).values({
      userId: profile.id,
      status: "failed",
      editionNumber,
      editionDate,
      sourceCount: feeds.length,
      deliveryMethod: profile.deliveryMethod,
      errorMessage: errorMsg,
    });

    return errorResult(errorMsg, editionDate);
  }

  if (!buildResponse.success || !buildResponse.epub_base64) {
    const errorMsg = buildResponse.error ?? "Build returned no EPUB";

    await db.insert(deliveryHistory).values({
      userId: profile.id,
      status: "failed",
      editionNumber,
      editionDate,
      sourceCount: feeds.length,
      deliveryMethod: profile.deliveryMethod,
      errorMessage: errorMsg,
    });

    return errorResult(errorMsg, editionDate);
  }

  // 3. Upload EPUB to Supabase Storage
  let epubStoragePath: string | null = null;
  try {
    const supabase = await createClient();
    const filename = `${profile.title.replace(/\s+/g, "-")}-${editionDate}.epub`;
    const storagePath = `${user.id}/${filename}`;
    const epubBuffer = Buffer.from(buildResponse.epub_base64, "base64");

    const { error: uploadError } = await supabase.storage
      .from("epubs")
      .upload(storagePath, epubBuffer, {
        contentType: "application/epub+zip",
        upsert: true,
      });

    if (!uploadError) {
      epubStoragePath = storagePath;
    }
  } catch {
    // Storage upload is non-critical — continue without it
  }

  // 4. If delivery_method != "local", POST to FastAPI /deliver
  let deliveryMessage = "Available for download";
  if (profile.deliveryMethod !== "local") {
    try {
      const googleTokens = profile.googleTokens as GoogleTokens | null;
      const deliverRequest: ApiDeliverRequest = {
        epub_base64: buildResponse.epub_base64,
        title: profile.title,
        device: profile.device,
        delivery_method: profile.deliveryMethod,
        google_drive_folder: profile.googleDriveFolder,
        google_tokens: googleTokens
          ? {
              token: googleTokens.token,
              refresh_token: googleTokens.refreshToken,
              token_uri: googleTokens.tokenUri,
              client_id: googleTokens.clientId,
              client_secret: googleTokens.clientSecret,
              scopes: googleTokens.scopes,
              expiry: googleTokens.expiry,
            }
          : null,
        kindle_email: profile.kindleEmail ?? "",
        email_smtp_host: profile.emailSmtpHost ?? "smtp.gmail.com",
        email_smtp_port: profile.emailSmtpPort ?? 465,
        email_sender: profile.emailSender ?? "",
        email_password: profile.emailPassword ?? "",
      };

      const deliverResponse = await deliverNewspaper(deliverRequest);
      deliveryMessage = deliverResponse.message;
    } catch (err) {
      deliveryMessage =
        err instanceof Error ? err.message : "Delivery failed";
    }
  }

  // 5. Insert delivery_history record
  const sections = buildResponse.sections as SectionSummary[];
  await db.insert(deliveryHistory).values({
    userId: profile.id,
    status: "delivered",
    editionNumber,
    editionDate,
    articleCount: buildResponse.total_articles,
    sourceCount: feeds.length,
    fileSize: buildResponse.file_size,
    fileSizeBytes: buildResponse.file_size_bytes,
    deliveryMethod: profile.deliveryMethod,
    deliveryMessage,
    epubStoragePath,
    sections,
  });

  // 6. Return result
  return {
    success: true,
    editionDate,
    totalArticles: buildResponse.total_articles,
    sections,
    fileSize: buildResponse.file_size,
    fileSizeBytes: buildResponse.file_size_bytes,
    epubStoragePath,
    error: null,
  };
}
