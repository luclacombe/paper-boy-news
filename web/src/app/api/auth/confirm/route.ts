import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Email confirmation callback.
 *
 * Supabase email confirmation links redirect here with a token_hash.
 * We verify the token, exchange it for a session, and redirect to the dashboard.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") ?? "signup";

  if (!tokenHash) {
    return NextResponse.redirect(
      new URL("/login?message=Invalid+confirmation+link.", request.url)
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

  const { error } = await supabase.auth.verifyOtp({
    token_hash: tokenHash,
    type: type as "signup" | "email" | "recovery",
  });

  let redirectUrl: URL;
  if (error) {
    redirectUrl = new URL("/login?message=Email+link+is+invalid+or+has+expired.+Please+try+again.", request.url);
  } else if (type === "recovery") {
    redirectUrl = new URL("/reset-password", request.url);
  } else {
    redirectUrl = new URL("/dashboard", request.url);
  }

  const response = NextResponse.redirect(redirectUrl);

  for (const { name, value, options } of cookiesToApply) {
    response.cookies.set(name, value, options);
  }

  return response;
}
