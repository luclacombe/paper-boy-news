import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { GoogleTokens } from "@/types";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const errorParam = searchParams.get("error");

  if (errorParam || !code) {
    return NextResponse.redirect(
      new URL(`/delivery?error=${errorParam || "no_code"}`, request.url)
    );
  }

  // 1. Get the authenticated user from cookies
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll() {
          // No-op — we don't need to set Supabase cookies here
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // 2. Exchange authorization code for tokens
  const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      redirect_uri: `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/google/callback`,
      grant_type: "authorization_code",
    }),
  });

  if (!tokenResponse.ok) {
    return NextResponse.redirect(
      new URL("/delivery?error=token_exchange_failed", request.url)
    );
  }

  const tokenData = await tokenResponse.json();

  // 3. Build GoogleTokens object (client_id/secret NOT stored — build runner uses env vars)
  const googleTokens: GoogleTokens = {
    token: tokenData.access_token,
    refreshToken: tokenData.refresh_token,
    tokenUri: "https://oauth2.googleapis.com/token",
    scopes: tokenData.scope?.split(" ") ?? [],
    expiry: tokenData.expires_in
      ? new Date(Date.now() + tokenData.expires_in * 1000).toISOString()
      : null,
  };

  // 4. Store tokens in user_profiles via Drizzle (bypasses RLS — safe because we verified the user above)
  await db
    .update(userProfiles)
    .set({ googleTokens, updatedAt: new Date() })
    .where(eq(userProfiles.authId, user.id));

  // 5. Redirect to delivery page
  return NextResponse.redirect(
    new URL("/delivery?connected=true", request.url)
  );
}
