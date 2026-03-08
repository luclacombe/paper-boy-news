import { NextRequest, NextResponse } from "next/server";
import nodemailer from "nodemailer";
import { createClient } from "@/lib/supabase/server";

/**
 * POST /api/smtp-test
 * Test SMTP credentials without sending an email.
 * Ported from api/routes/smtp_test.py.
 */
export async function POST(request: NextRequest) {
  // Auth check
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json(
      { success: false, message: "Not authenticated" },
      { status: 401 }
    );
  }

  const body = await request.json();
  const { smtp_host, smtp_port, sender, password } = body as {
    smtp_host: string;
    smtp_port: number;
    sender: string;
    password: string;
  };

  if (!smtp_host || !smtp_port || !sender || !password) {
    return NextResponse.json({
      success: false,
      message: "All SMTP fields are required",
    });
  }

  // SSRF protection — resolve hostname and block private IPs
  try {
    const { resolve4, resolve6 } = await import("node:dns/promises");
    const ips: string[] = [];
    try {
      ips.push(...(await resolve4(smtp_host)));
    } catch { /* no A records */ }
    try {
      ips.push(...(await resolve6(smtp_host)));
    } catch { /* no AAAA records */ }

    for (const ip of ips) {
      if (isPrivateIp(ip)) {
        return NextResponse.json({
          success: false,
          message:
            "SMTP host resolves to a private/internal address. Use a public SMTP server.",
        });
      }
    }
  } catch {
    // DNS resolution failed — let nodemailer handle the error naturally
  }

  // Test SMTP connection
  try {
    const port = Number(smtp_port);
    const transporter = nodemailer.createTransport({
      host: smtp_host,
      port,
      secure: port === 465,
      auth: { user: sender, pass: password },
      connectionTimeout: 10_000,
      greetingTimeout: 10_000,
    });

    await transporter.verify();

    return NextResponse.json({
      success: true,
      message: "Connection successful! Your email credentials are valid.",
    });
  } catch (err) {
    const error = err as Error & { code?: string; responseCode?: number };

    // Gmail App Password errors
    if (error.responseCode === 534) {
      return NextResponse.json({
        success: false,
        message:
          "Gmail requires an App Password. " +
          "Enable 2-Step Verification in your Google Account, " +
          "then create an App Password at myaccount.google.com/apppasswords",
      });
    }
    if (error.responseCode === 535) {
      return NextResponse.json({
        success: false,
        message:
          "Authentication failed. Check that your email address " +
          "and App Password are correct.",
      });
    }

    // Connection errors
    if (error.code === "ECONNREFUSED") {
      return NextResponse.json({
        success: false,
        message: `Connection refused by ${smtp_host}:${smtp_port}. Check the port number.`,
      });
    }
    if (error.code === "ENOTFOUND") {
      return NextResponse.json({
        success: false,
        message: `Could not resolve hostname: ${smtp_host}`,
      });
    }
    if (error.code === "ETIMEDOUT" || error.code === "ESOCKET") {
      return NextResponse.json({
        success: false,
        message: `Connection to ${smtp_host}:${smtp_port} timed out.`,
      });
    }
    if (error.message?.includes("SSL") || error.code === "UNABLE_TO_VERIFY_LEAF_SIGNATURE") {
      return NextResponse.json({
        success: false,
        message: `SSL error connecting to ${smtp_host}:${smtp_port}. Port 465 uses SSL, port 587 uses STARTTLS.`,
      });
    }

    return NextResponse.json({
      success: false,
      message: `Connection error: ${error.message}`,
    });
  }
}

function isPrivateIp(ip: string): boolean {
  if (ip.startsWith("10.") || ip.startsWith("192.168.") || ip.startsWith("127.")) return true;
  if (ip.startsWith("172.")) {
    const second = parseInt(ip.split(".")[1], 10);
    if (second >= 16 && second <= 31) return true;
  }
  if (ip.startsWith("169.254.")) return true;
  if (ip === "0.0.0.0" || ip === "::1" || ip === "::") return true;
  if (ip.startsWith("fc") || ip.startsWith("fd") || ip.startsWith("fe80")) return true;
  return false;
}
