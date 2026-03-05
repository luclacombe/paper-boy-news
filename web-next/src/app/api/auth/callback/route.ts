import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { db } from "@/db";
import { userProfiles } from "@/db/schema";
import { eq } from "drizzle-orm";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const rawNext = searchParams.get("next") ?? "/dashboard";
  // Prevent open redirect — only allow relative paths on the same origin
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/dashboard";

  if (!code) {
    return NextResponse.redirect(
      new URL("/login?message=Authentication+failed.+Please+try+again.", request.url)
    );
  }

  const cookiesToApply: {
    name: string;
    value: string;
    options: Record<string, unknown>;
  }[] = [];

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach((cookie) => cookiesToApply.push(cookie));
        },
      },
    }
  );

  const { data, error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(
      new URL("/login?message=Authentication+failed.+Please+try+again.", request.url)
    );
  }

  // If coming from onboarding, check if user is already onboarded — redirect
  // to dashboard instead of /onboarding/complete to prevent data overwrites
  let finalNext = next;
  if (next === "/onboarding/complete" && data.user) {
    try {
      const [profile] = await db
        .select({ onboardingComplete: userProfiles.onboardingComplete })
        .from(userProfiles)
        .where(eq(userProfiles.authId, data.user.id))
        .limit(1);

      if (profile?.onboardingComplete) {
        finalNext = "/dashboard";
      }
    } catch {
      // DB check failed — continue to onboarding/complete which has its own fallback
    }
  }

  const redirectUrl = new URL(finalNext, request.url);
  const response = NextResponse.redirect(redirectUrl);

  for (const { name, value, options } of cookiesToApply) {
    response.cookies.set(name, value, options);
  }

  return response;
}
