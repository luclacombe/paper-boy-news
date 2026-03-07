/**
 * Dev Reset Script
 *
 * Resets a user's state for re-testing flows (onboarding, delivery, etc.)
 * without creating a new account or clearing cookies.
 *
 * Usage:
 *   pnpm dev:reset                          # Reset all users (onboarding + feeds + history)
 *   pnpm dev:reset -- --email dev@paperboy.local   # Reset specific user
 *   pnpm dev:reset -- --onboarding          # Only reset onboarding flag
 *   pnpm dev:reset -- --history             # Only clear delivery history
 *   pnpm dev:reset -- --feeds               # Only clear feeds
 */

import { config } from "dotenv";
config({ path: ".env.local" });

import postgres from "postgres";

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error("ERROR: DATABASE_URL not set in .env.local");
  process.exit(1);
}

const sql = postgres(DATABASE_URL, { prepare: false });

const args = process.argv.slice(2);
const email = args.includes("--email")
  ? args[args.indexOf("--email") + 1]
  : null;
const onboardingOnly = args.includes("--onboarding");
const historyOnly = args.includes("--history");
const feedsOnly = args.includes("--feeds");
const specificReset = onboardingOnly || historyOnly || feedsOnly;

async function main() {
  try {
    // Build WHERE clause for targeting specific user
    const userFilter = email
      ? sql`WHERE p.auth_id = (SELECT id FROM auth.users WHERE email = ${email})`
      : sql`WHERE TRUE`;

    // Get target profiles
    const profiles = await sql`
      SELECT p.id, p.auth_id, u.email, p.onboarding_complete
      FROM user_profiles p
      JOIN auth.users u ON u.id = p.auth_id
      ${userFilter}
    `;

    if (profiles.length === 0) {
      console.log(email ? `No user found with email: ${email}` : "No users found");
      process.exit(0);
    }

    const profileIds = profiles.map((p) => p.id);

    console.log(`\nResetting ${profiles.length} user(s):`);
    for (const p of profiles) {
      console.log(`  ${p.email} (onboarded: ${p.onboarding_complete})`);
    }
    console.log("");

    if (!specificReset || onboardingOnly) {
      await sql`
        UPDATE user_profiles
        SET onboarding_complete = false,
            device = 'kobo',
            delivery_method = 'local',
            title = 'Morning Digest',
            reading_time = '20 min',
            max_articles_per_feed = 10,
            include_images = true,
            delivery_time = '06:00',
            timezone = 'UTC',
            google_drive_folder = 'Rakuten Kobo',
            kindle_email = '',
            email_method = 'gmail',
            google_tokens = null,
            updated_at = now()
        WHERE id = ANY(${profileIds})
      `;
      console.log("  [ok] Reset onboarding state + profile settings");
    }

    if (!specificReset || feedsOnly) {
      const deleted = await sql`
        DELETE FROM user_feeds WHERE user_id = ANY(${profileIds})
      `;
      console.log(`  [ok] Deleted ${deleted.count} feeds`);
    }

    if (!specificReset || historyOnly) {
      const deleted = await sql`
        DELETE FROM delivery_history WHERE user_id = ANY(${profileIds})
      `;
      console.log(`  [ok] Deleted ${deleted.count} delivery history records`);
    }

    console.log("\nDone! Next step:");
    console.log("  → Visit http://localhost:3000/dev/reset to clear browser state + sign out");
    console.log("  Then log in at /login — you'll be redirected to onboarding\n");
  } catch (err) {
    console.error("Error:", err);
    process.exit(1);
  } finally {
    await sql.end();
  }
}

main();
