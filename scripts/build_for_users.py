"""Build and deliver newspapers for web app users via Supabase.

Two modes:
  1. On-demand: BUILD_RECORD_ID set — build for a single delivery_history record
  2. Scheduled: no BUILD_RECORD_ID — scan all users, build if within delivery window

Environment variables:
  SUPABASE_URL            — Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY — Service role key (bypasses RLS)
  GOOGLE_CLIENT_ID        — For OAuth token refresh
  GOOGLE_CLIENT_SECRET    — For OAuth token refresh
  BUILD_RECORD_ID         — (optional) Specific delivery_history record ID
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from supabase import create_client

from paper_boy.config import (
    Config,
    DeliveryConfig,
    EmailConfig,
    FeedConfig,
    GoogleDriveConfig,
    NewspaperConfig,
)
from paper_boy.delivery import deliver
from paper_boy.main import build_newspaper

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

EDITION_ROLLOVER_HOUR = 5


def get_supabase():
    """Create Supabase client with service role key."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def get_edition_date(timezone: str) -> str:
    """Compute edition date using 5 AM rollover in user's timezone.

    Matches web/src/lib/edition-date.ts logic exactly.
    """
    try:
        tz = ZoneInfo(timezone)
    except (KeyError, Exception):
        tz = ZoneInfo("UTC")

    now = datetime.now(tz)
    if now.hour < EDITION_ROLLOVER_HOUR:
        # Before 5 AM — yesterday's edition
        d = now.date()
        d = date(d.year, d.month, d.day)
        from datetime import timedelta

        d -= timedelta(days=1)
        return d.isoformat()
    return now.date().isoformat()


def build_config_from_profile(
    profile: dict, feeds: list[dict]
) -> Config:
    """Construct a paper_boy Config from Supabase profile + feeds data."""
    feed_configs = [FeedConfig(name=f["name"], url=f["url"]) for f in feeds]

    newspaper = NewspaperConfig(
        title=profile.get("title", "Morning Digest"),
        language=profile.get("language", "en"),
        max_articles_per_feed=profile.get("max_articles_per_feed", 10),
        include_images=profile.get("include_images", True),
    )

    delivery_method = profile.get("delivery_method", "local")
    google_tokens = profile.get("google_tokens")

    # Detect Gmail API routing
    effective_method = delivery_method
    if effective_method == "email" and google_tokens:
        scopes = google_tokens.get("scopes", [])
        if "https://www.googleapis.com/auth/gmail.send" in scopes:
            effective_method = "gmail_api"

    delivery = DeliveryConfig(
        method=effective_method,
        device=profile.get("device", "kobo"),
        google_drive=GoogleDriveConfig(
            folder_name=profile.get("google_drive_folder", "Rakuten Kobo"),
        ),
        email=EmailConfig(
            smtp_host=profile.get("email_smtp_host", "smtp.gmail.com"),
            smtp_port=profile.get("email_smtp_port", 465),
            sender=profile.get("email_sender", ""),
            password=profile.get("email_password", ""),
            recipient=profile.get("kindle_email", ""),
        ),
        keep_days=30,
    )

    return Config(newspaper=newspaper, feeds=feed_configs, delivery=delivery)


def get_token_data(profile: dict) -> dict | None:
    """Extract Google OAuth token data from profile, injecting client credentials."""
    google_tokens = profile.get("google_tokens")
    if not google_tokens or not google_tokens.get("refreshToken"):
        return None

    return {
        "token": google_tokens.get("token", ""),
        "refresh_token": google_tokens["refreshToken"],
        "token_uri": google_tokens.get("tokenUri", "https://oauth2.googleapis.com/token"),
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", google_tokens.get("clientId", "")),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", google_tokens.get("clientSecret", "")),
        "scopes": google_tokens.get("scopes", []),
        "expiry": google_tokens.get("expiry"),
    }


def build_and_deliver_for_record(record_id: str) -> None:
    """On-demand mode: build for a specific delivery_history record."""
    sb = get_supabase()

    # Fetch the record
    record = sb.table("delivery_history").select("*").eq("id", record_id).single().execute()
    if not record.data:
        logger.error("Record %s not found", record_id)
        return

    rec = record.data
    user_id = rec["user_id"]

    # Fetch user profile
    profile = sb.table("user_profiles").select("*").eq("id", user_id).single().execute()
    if not profile.data:
        logger.error("Profile not found for user %s", user_id)
        sb.table("delivery_history").update(
            {"status": "failed", "error_message": "User profile not found"}
        ).eq("id", record_id).execute()
        return

    prof = profile.data

    # Fetch user feeds
    feeds = (
        sb.table("user_feeds")
        .select("*")
        .eq("user_id", user_id)
        .order("position")
        .execute()
    )
    feed_list = feeds.data or []

    if not feed_list:
        sb.table("delivery_history").update(
            {"status": "failed", "error_message": "No feeds configured"}
        ).eq("id", record_id).execute()
        return

    edition_date_str = rec["edition_date"]
    edition_date = date.fromisoformat(edition_date_str)

    try:
        config = build_config_from_profile(prof, feed_list)

        with tempfile.TemporaryDirectory(prefix="paperboy_") as tmp_dir:
            output_path = os.path.join(
                tmp_dir, f"paper-boy-{edition_date.isoformat()}.epub"
            )

            result = build_newspaper(config, output_path=output_path, issue_date=edition_date)

            # Read EPUB for size + storage upload
            epub_bytes = Path(result.epub_path).read_bytes()
            file_size_bytes = len(epub_bytes)
            if file_size_bytes >= 1_048_576:
                file_size = f"{file_size_bytes / 1_048_576:.1f} MB"
            else:
                file_size = f"{file_size_bytes / 1024:.0f} KB"

            # Extract sections
            sections = [
                {"name": s.name, "headlines": [a.title for a in s.articles[:5]]}
                for s in result.sections
            ]

            # Upload EPUB to Supabase Storage
            epub_storage_path = None
            try:
                filename = f"{prof['title'].replace(' ', '-')}-{edition_date_str}.epub"
                storage_path = f"{prof['auth_id']}/{filename}"
                sb.storage.from_("epubs").upload(
                    storage_path,
                    epub_bytes,
                    {"content-type": "application/epub+zip", "upsert": "true"},
                )
                epub_storage_path = storage_path
            except Exception as e:
                logger.warning("Storage upload failed (non-critical): %s", e)

            # Deliver if not local
            delivery_message = "Available for download"
            token_data = get_token_data(prof)

            if prof.get("delivery_method", "local") != "local":
                try:
                    deliver(result.epub_path, config, token_data=token_data)

                    # Generate success message
                    method = config.delivery.method
                    if method == "google_drive":
                        delivery_message = f"Uploaded to Google Drive ({config.delivery.google_drive.folder_name})"
                    elif method == "gmail_api":
                        delivery_message = f"Sent to {config.delivery.email.recipient} via Gmail"
                    elif method == "email":
                        delivery_message = f"Emailed to {config.delivery.email.recipient}"

                    # Write back refreshed tokens if they changed
                    if token_data and token_data.get("token") != (prof.get("google_tokens") or {}).get("token"):
                        updated_tokens = dict(prof.get("google_tokens", {}))
                        updated_tokens["token"] = token_data["token"]
                        if token_data.get("expiry"):
                            updated_tokens["expiry"] = token_data["expiry"]
                        sb.table("user_profiles").update(
                            {"google_tokens": updated_tokens}
                        ).eq("id", user_id).execute()

                except Exception as e:
                    delivery_message = f"Delivery failed: {e}"
                    logger.error("Delivery failed: %s", e)

            # Determine final status based on delivery outcome
            delivery_failed = delivery_message.startswith("Delivery failed:")
            final_status = "failed" if delivery_failed else "delivered"

            update_data: dict = {
                "status": final_status,
                "article_count": result.total_articles,
                "source_count": len(feed_list),
                "file_size": file_size,
                "file_size_bytes": file_size_bytes,
                "epub_storage_path": epub_storage_path,
                "sections": sections,
            }
            if delivery_failed:
                update_data["error_message"] = delivery_message[:500]
            else:
                update_data["delivery_message"] = delivery_message

            sb.table("delivery_history").update(update_data).eq("id", record_id).execute()

            logger.info(
                "Built and delivered edition %s: %d articles, %s",
                edition_date_str,
                result.total_articles,
                file_size,
            )

    except Exception as e:
        logger.exception("Build failed for record %s", record_id)
        sb.table("delivery_history").update({
            "status": "failed",
            "error_message": str(e)[:500],
        }).eq("id", record_id).execute()


def run_scheduled() -> None:
    """Scheduled mode: scan all onboarded users and build if within delivery window."""
    sb = get_supabase()

    # Fetch all onboarded users
    users = (
        sb.table("user_profiles")
        .select("*")
        .eq("onboarding_complete", True)
        .execute()
    )

    if not users.data:
        logger.info("No onboarded users found")
        return

    now_utc = datetime.now(ZoneInfo("UTC"))

    for prof in users.data:
        user_id = prof["id"]
        timezone = prof.get("timezone", "UTC")
        delivery_time_str = prof.get("delivery_time", "06:00")

        # Compute edition date for this user
        edition_date_str = get_edition_date(timezone)

        # Check if already built for today
        existing = (
            sb.table("delivery_history")
            .select("id, status")
            .eq("user_id", user_id)
            .eq("edition_date", edition_date_str)
            .neq("status", "failed")
            .limit(1)
            .execute()
        )
        if existing.data:
            continue

        # Check if current time is within ±15 min of user's delivery time
        try:
            tz = ZoneInfo(timezone)
        except (KeyError, Exception):
            tz = ZoneInfo("UTC")

        user_now = now_utc.astimezone(tz)
        delivery_hour, delivery_minute = map(int, delivery_time_str.split(":"))
        delivery_minutes = delivery_hour * 60 + delivery_minute
        current_minutes = user_now.hour * 60 + user_now.minute

        diff = abs(current_minutes - delivery_minutes)
        if diff > 15 and diff < (24 * 60 - 15):
            continue

        logger.info("Building for user %s (edition %s)", user_id, edition_date_str)

        # Fetch feeds
        feeds = (
            sb.table("user_feeds")
            .select("*")
            .eq("user_id", user_id)
            .order("position")
            .execute()
        )
        if not feeds.data:
            continue

        # Count existing editions for edition number
        count_resp = (
            sb.table("delivery_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        edition_number = (count_resp.count or 0) + 1

        # Create delivery_history record
        record = (
            sb.table("delivery_history")
            .insert({
                "user_id": user_id,
                "status": "building",
                "edition_number": edition_number,
                "edition_date": edition_date_str,
                "source_count": len(feeds.data),
                "delivery_method": prof.get("delivery_method", "local"),
            })
            .execute()
        )

        if record.data:
            record_id = record.data[0]["id"]
            build_and_deliver_for_record(record_id)


def main():
    record_id = os.environ.get("BUILD_RECORD_ID")

    if record_id:
        logger.info("On-demand mode: building record %s", record_id)
        build_and_deliver_for_record(record_id)
    else:
        logger.info("Scheduled mode: scanning all users")
        run_scheduled()


if __name__ == "__main__":
    main()
