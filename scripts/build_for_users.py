"""Build and deliver newspapers for web app users via Supabase.

Three modes:
  1. On-demand: BUILD_RECORD_ID set — build (or deliver) for a single record
  2. Build:     BUILD_MODE=build — build all users' papers at 5 AM UTC
  3. Deliver:   BUILD_MODE=deliver — deliver pre-built papers at each user's time

Environment variables:
  SUPABASE_URL            — Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY — Service role key (bypasses RLS)
  GOOGLE_CLIENT_ID        — For OAuth token refresh
  GOOGLE_CLIENT_SECRET    — For OAuth token refresh
  BUILD_RECORD_ID         — (optional) Specific delivery_history record ID
  BUILD_MODE              — (optional) "build" or "deliver"
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
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
from paper_boy.cache import ContentCache
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
        d = now.date() - timedelta(days=1)
        return d.isoformat()
    return now.date().isoformat()


def build_config_from_profile(
    profile: dict, feeds: list[dict]
) -> Config:
    """Construct a paper_boy Config from Supabase profile + feeds data."""
    feed_configs = [
        FeedConfig(name=f["name"], url=f["url"], category=f.get("category", ""))
        for f in feeds
    ]

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


def _format_file_size(size_bytes: int) -> str:
    """Format byte count as human-readable size string."""
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


def _generate_delivery_message(config: Config) -> str:
    """Generate a human-readable delivery success message."""
    method = config.delivery.method
    if method == "google_drive":
        return f"Uploaded to Google Drive ({config.delivery.google_drive.folder_name})"
    elif method == "gmail_api":
        return f"Sent to {config.delivery.email.recipient} via Gmail"
    elif method == "email":
        return f"Emailed to {config.delivery.email.recipient}"
    return "Available for download"


def _write_back_tokens(sb, prof: dict, user_id: str, token_data: dict | None) -> None:
    """Write refreshed OAuth tokens back to the DB if they changed."""
    if not token_data:
        return
    old_token = (prof.get("google_tokens") or {}).get("token")
    if token_data.get("token") != old_token:
        updated_tokens = dict(prof.get("google_tokens", {}))
        updated_tokens["token"] = token_data["token"]
        if token_data.get("expiry"):
            updated_tokens["expiry"] = token_data["expiry"]
        sb.table("user_profiles").update(
            {"google_tokens": updated_tokens}
        ).eq("id", user_id).execute()


def _build_for_user(sb, prof: dict, feed_list: list[dict], record_id: str,
                    edition_date: date, cache: ContentCache | None = None) -> None:
    """Build EPUB for a user and update the delivery_history record.

    Sets status to "built" (for auto-delivery users) or "delivered" (for local/download).
    On-demand callers should use build_and_deliver_for_record() instead.
    """
    edition_date_str = edition_date.isoformat()
    is_local = prof.get("delivery_method", "local") == "local"

    try:
        config = build_config_from_profile(prof, feed_list)

        with tempfile.TemporaryDirectory(prefix="paperboy_") as tmp_dir:
            output_path = os.path.join(
                tmp_dir, f"paper-boy-{edition_date_str}.epub"
            )

            result = build_newspaper(config, output_path=output_path, issue_date=edition_date, cache=cache)

            # Read EPUB for size + storage upload
            epub_bytes = Path(result.epub_path).read_bytes()
            file_size_bytes = len(epub_bytes)
            file_size = _format_file_size(file_size_bytes)

            # Extract sections summary
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

            # Local/download users go straight to "delivered" — no delivery step
            # Auto-delivery users get "built" — delivery happens in run_deliver()
            if is_local:
                final_status = "delivered"
                delivery_message = "Available for download"
            else:
                final_status = "built"
                delivery_message = None

            update_data: dict = {
                "status": final_status,
                "article_count": result.total_articles,
                "source_count": len(feed_list),
                "file_size": file_size,
                "file_size_bytes": file_size_bytes,
                "epub_storage_path": epub_storage_path,
                "sections": sections,
            }
            if delivery_message:
                update_data["delivery_message"] = delivery_message

            sb.table("delivery_history").update(update_data).eq("id", record_id).execute()

            logger.info(
                "Built edition %s for user %s: %d articles, %s [%s]",
                edition_date_str,
                prof["id"],
                result.total_articles,
                file_size,
                final_status,
            )

    except Exception as e:
        logger.exception("Build failed for record %s", record_id)
        sb.table("delivery_history").update({
            "status": "failed",
            "error_message": str(e)[:500],
        }).eq("id", record_id).execute()


def _deliver_record(sb, rec: dict, prof: dict) -> None:
    """Deliver a pre-built EPUB from Supabase Storage and update the record."""
    record_id = rec["id"]
    user_id = rec["user_id"]
    epub_storage_path = rec.get("epub_storage_path")

    if not epub_storage_path:
        sb.table("delivery_history").update({
            "status": "failed",
            "error_message": "No EPUB file in storage",
        }).eq("id", record_id).execute()
        return

    try:
        config = build_config_from_profile(prof, [])  # feeds not needed for delivery
        token_data = get_token_data(prof)

        # Download EPUB from Supabase Storage
        epub_bytes = sb.storage.from_("epubs").download(epub_storage_path)

        with tempfile.TemporaryDirectory(prefix="paperboy_deliver_") as tmp_dir:
            epub_path = os.path.join(tmp_dir, "paper.epub")
            Path(epub_path).write_bytes(epub_bytes)

            deliver(epub_path, config, token_data=token_data)

            delivery_message = _generate_delivery_message(config)
            _write_back_tokens(sb, prof, user_id, token_data)

            sb.table("delivery_history").update({
                "status": "delivered",
                "delivery_message": delivery_message,
            }).eq("id", record_id).execute()

            logger.info("Delivered record %s: %s", record_id, delivery_message)

    except Exception as e:
        logger.exception("Delivery failed for record %s", record_id)
        sb.table("delivery_history").update({
            "status": "failed",
            "error_message": f"Delivery failed: {str(e)[:480]}",
        }).eq("id", record_id).execute()


def build_and_deliver_for_record(
    record_id: str, cache: ContentCache | None = None
) -> None:
    """On-demand mode: build and/or deliver for a specific delivery_history record.

    If the record is already "built" (EPUB in Storage), skips to delivery.
    Otherwise builds + delivers in one step.
    """
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

    # If record is already "built", skip to delivery-only
    if rec["status"] == "built" and rec.get("epub_storage_path"):
        logger.info("Record %s already built — delivering from storage", record_id)
        _deliver_record(sb, rec, prof)
        return

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

            result = build_newspaper(config, output_path=output_path, issue_date=edition_date, cache=cache)

            # Read EPUB for size + storage upload
            epub_bytes = Path(result.epub_path).read_bytes()
            file_size_bytes = len(epub_bytes)
            file_size = _format_file_size(file_size_bytes)

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
                    delivery_message = _generate_delivery_message(config)
                    _write_back_tokens(sb, prof, user_id, token_data)
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


# ─── Build mode: build all users' papers (5 AM UTC) ─────────────────────

def run_build_all() -> None:
    """Build all onboarded users' papers. Called once daily at 5 AM UTC.

    Uses a shared ContentCache to deduplicate RSS fetches, article extraction,
    and image downloads across all users.
    """
    sb = get_supabase()

    users = (
        sb.table("user_profiles")
        .select("*")
        .eq("onboarding_complete", True)
        .execute()
    )

    if not users.data:
        logger.info("No onboarded users found")
        return

    cache = ContentCache()
    built_count = 0

    for prof in users.data:
        user_id = prof["id"]
        timezone = prof.get("timezone", "UTC")

        edition_date_str = get_edition_date(timezone)

        # Skip if already built for today
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

        logger.info("Building for user %s (edition %s)", user_id, edition_date_str)

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
            edition_date = date.fromisoformat(edition_date_str)
            _build_for_user(sb, prof, feeds.data, record_id, edition_date, cache=cache)
            built_count += 1

    cache.log_stats()
    logger.info("Build phase complete: %d papers built", built_count)


# ─── Deliver mode: deliver pre-built papers at each user's time ──────────

def run_deliver() -> None:
    """Deliver pre-built papers whose delivery window matches now.

    Scans for records with status="built", checks if the user's delivery_time
    is within ±15 min of the current time in their timezone.
    """
    sb = get_supabase()

    # Fetch all "built" records (not yet delivered)
    built_records = (
        sb.table("delivery_history")
        .select("*")
        .eq("status", "built")
        .execute()
    )

    if not built_records.data:
        logger.info("No papers awaiting delivery")
        return

    now_utc = datetime.now(ZoneInfo("UTC"))
    delivered_count = 0

    for rec in built_records.data:
        user_id = rec["user_id"]

        # Fetch user profile for timezone + delivery_time
        profile = (
            sb.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not profile.data:
            continue

        prof = profile.data
        timezone = prof.get("timezone", "UTC")
        delivery_time_str = prof.get("delivery_time", "06:00")

        # Check if within ±15 min of delivery window
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

        logger.info("Delivering for user %s (record %s)", user_id, rec["id"])
        _deliver_record(sb, rec, prof)
        delivered_count += 1

    logger.info("Deliver phase complete: %d papers delivered", delivered_count)


# ─── Legacy: combined build + deliver (kept for backward compat) ─────────

def run_scheduled() -> None:
    """Legacy scheduled mode: build + deliver in one step if within delivery window."""
    sb = get_supabase()

    users = (
        sb.table("user_profiles")
        .select("*")
        .eq("onboarding_complete", True)
        .execute()
    )

    if not users.data:
        logger.info("No onboarded users found")
        return

    cache = ContentCache()
    now_utc = datetime.now(ZoneInfo("UTC"))

    for prof in users.data:
        user_id = prof["id"]
        timezone = prof.get("timezone", "UTC")
        delivery_time_str = prof.get("delivery_time", "06:00")

        edition_date_str = get_edition_date(timezone)

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

        feeds = (
            sb.table("user_feeds")
            .select("*")
            .eq("user_id", user_id)
            .order("position")
            .execute()
        )
        if not feeds.data:
            continue

        count_resp = (
            sb.table("delivery_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        edition_number = (count_resp.count or 0) + 1

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
            build_and_deliver_for_record(record_id, cache=cache)

    cache.log_stats()


# ─── Entry point ─────────────────────────────────────────────────────────

def main():
    record_id = os.environ.get("BUILD_RECORD_ID")
    build_mode = os.environ.get("BUILD_MODE", "")

    if record_id:
        logger.info("On-demand mode: building record %s", record_id)
        build_and_deliver_for_record(record_id)
    elif build_mode == "build":
        logger.info("Build mode: building all papers")
        run_build_all()
    elif build_mode == "deliver":
        logger.info("Deliver mode: checking delivery windows")
        run_deliver()
    else:
        logger.info("Scheduled mode (legacy): scanning all users")
        run_scheduled()


if __name__ == "__main__":
    main()
