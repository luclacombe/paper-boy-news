import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * POST /api/feeds/validate
 * Validate an RSS/Atom feed URL server-side.
 * Ports SSRF protection from src/paper_boy/url_validation.py.
 */
export async function POST(request: NextRequest) {
  // Auth check
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ valid: false, name: null, error: "Not authenticated" }, { status: 401 });
  }

  const body = await request.json();
  const url: string = body.url;

  if (!url) {
    return NextResponse.json({ valid: false, name: null, error: "URL is required" });
  }

  // SSRF protection
  const ssrfError = await checkSsrf(url);
  if (ssrfError) {
    return NextResponse.json({ valid: false, name: null, error: ssrfError });
  }

  // Fetch and validate RSS/Atom
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: { "User-Agent": "PaperBoy/1.0 (RSS validator)" },
      redirect: "follow",
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return NextResponse.json({
        valid: false,
        name: null,
        error: `Feed returned HTTP ${res.status}`,
      });
    }

    const text = await res.text();

    // Check for RSS or Atom markers
    const isRss = text.includes("<rss") || text.includes("<feed") || text.includes("<channel");
    if (!isRss) {
      return NextResponse.json({
        valid: false,
        name: null,
        error: "No RSS or Atom feed found at this URL",
      });
    }

    // Extract title
    const titleMatch = text.match(/<title[^>]*>([^<]+)<\/title>/);
    const name = titleMatch?.[1]?.trim() || null;

    // Check for at least one item/entry
    const hasItems = text.includes("<item") || text.includes("<entry");
    if (!hasItems) {
      return NextResponse.json({
        valid: false,
        name: null,
        error: "No articles found in feed",
      });
    }

    return NextResponse.json({ valid: true, name, error: null });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      return NextResponse.json({
        valid: false,
        name: null,
        error: "Feed URL timed out",
      });
    }
    return NextResponse.json({
      valid: false,
      name: null,
      error: "Could not validate this feed URL. Please check the URL and try again.",
    });
  }
}

/**
 * SSRF protection — reject private IPs, localhost, non-HTTP schemes.
 * Ported from src/paper_boy/url_validation.py.
 */
async function checkSsrf(url: string): Promise<string | null> {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return "Invalid URL";
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "URL not allowed: only public HTTP/HTTPS URLs are accepted";
  }

  const hostname = parsed.hostname;
  if (!hostname) return "Invalid URL";

  // Block localhost aliases
  const localhostAliases = ["localhost", "0.0.0.0", "[::]", "[::1]", "127.0.0.1", "::1"];
  if (localhostAliases.includes(hostname)) {
    return "URL not allowed: only public HTTP/HTTPS URLs are accepted";
  }

  // DNS resolution + private IP check
  try {
    const { resolve4, resolve6 } = await import("node:dns/promises");

    const ips: string[] = [];
    try {
      ips.push(...(await resolve4(hostname)));
    } catch { /* no A records */ }
    try {
      ips.push(...(await resolve6(hostname)));
    } catch { /* no AAAA records */ }

    for (const ip of ips) {
      if (isPrivateIp(ip)) {
        return "URL not allowed: only public HTTP/HTTPS URLs are accepted";
      }
    }
  } catch {
    // DNS resolution failed — let the fetch handle the error
  }

  return null;
}

function isPrivateIp(ip: string): boolean {
  // IPv4 private ranges
  if (ip.startsWith("10.") || ip.startsWith("192.168.") || ip.startsWith("127.")) return true;
  if (ip.startsWith("172.")) {
    const second = parseInt(ip.split(".")[1], 10);
    if (second >= 16 && second <= 31) return true;
  }
  // Link-local
  if (ip.startsWith("169.254.")) return true;
  // Loopback
  if (ip === "0.0.0.0" || ip === "::1" || ip === "::") return true;
  // IPv6 private
  if (ip.startsWith("fc") || ip.startsWith("fd") || ip.startsWith("fe80")) return true;

  return false;
}
