"""Tests for build_for_users.py — delivery method snapshotting and mid-build safety.

These tests verify that the build script uses the delivery_method from the
delivery_history record (snapshot from when the build was requested), not the
live profile, so that settings changes mid-build don't corrupt delivery.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# We need to set env vars before importing the module
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")

# Mock supabase before import (it's only needed for create_client at module level)
sys.modules.setdefault("supabase", MagicMock())

from scripts.build_for_users import (
    build_config_from_profile,
    get_token_data,
    _build_for_user,
    _deliver_record,
    _send_failure_notifications,
    build_and_deliver_for_record,
    run_deliver,
    _epub_filename,
    _format_file_size,
    _generate_delivery_message,
)

# ─── Fixtures ───────────────────────────────────────────────────────


def _make_profile(**overrides) -> dict:
    """Create a test user profile dict."""
    base = {
        "id": "user-1",
        "auth_id": "auth-1",
        "title": "Morning Digest",
        "language": "en",
        "total_article_budget": 7,
        "reading_time": "20 min",
        "include_images": True,
        "device": "kobo",
        "delivery_method": "google_drive",
        "google_drive_folder": "Rakuten Kobo",
        "recipient_email": "",
        "delivery_time": "06:00",
        "timezone": "UTC",
        "google_tokens": {
            "token": "access-token",
            "refreshToken": "refresh-token",
            "tokenUri": "https://oauth2.googleapis.com/token",
            "clientId": "web-client-id",
            "clientSecret": "web-client-secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        },
        "onboarding_complete": True,
    }
    base.update(overrides)
    return base


def _make_feed_list(count=2) -> list[dict]:
    """Create a test feed list."""
    return [
        {
            "id": f"feed-{i}",
            "user_id": "user-1",
            "name": f"Feed {i + 1}",
            "url": f"https://example.com/feed{i + 1}/rss",
            "category": "News",
            "position": i,
        }
        for i in range(count)
    ]


def _make_record(**overrides) -> dict:
    """Create a test delivery_history record."""
    base = {
        "id": "record-1",
        "user_id": "user-1",
        "status": "building",
        "edition_number": 1,
        "edition_date": "2026-03-09",
        "article_count": 0,
        "source_count": 2,
        "delivery_method": "google_drive",
        "delivery_message": "",
        "error_message": None,
        "epub_storage_path": None,
        "sections": None,
    }
    base.update(overrides)
    return base


def _make_epub(tmp_path: Path) -> Path:
    """Create a fake EPUB file."""
    epub = tmp_path / "Morning-Digest-2026-03-09.epub"
    epub.write_bytes(b"PK\x03\x04fake epub content " * 100)
    return epub


# ─── build_config_from_profile ──────────────────────────────────────


class TestBuildConfigFromProfile:
    def test_basic_config_building(self):
        prof = _make_profile()
        feeds = _make_feed_list()
        config = build_config_from_profile(prof, feeds)

        assert config.newspaper.title == "Morning Digest"
        assert config.delivery.method == "google_drive"
        assert len(config.feeds) == 2

    def test_local_delivery_method(self):
        prof = _make_profile(delivery_method="local")
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.delivery.method == "local"

    def test_email_delivery_method(self):
        """Email method creates config with method='email' (no gmail_api sniffing)."""
        prof = _make_profile(
            delivery_method="email",
            recipient_email="kindle@kindle.com",
        )
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.delivery.method == "email"
        assert config.delivery.email.recipient == "kindle@kindle.com"

    def test_email_without_tokens(self):
        """Email method without any Google tokens still works (uses Resend, not Gmail)."""
        prof = _make_profile(delivery_method="email", google_tokens=None)
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.delivery.method == "email"

    def test_overridden_delivery_method(self):
        """Verifying that overriding delivery_method in the profile dict works."""
        prof = _make_profile(delivery_method="google_drive")
        # Simulate the snapshot override
        prof_snapshot = dict(prof)
        prof_snapshot["delivery_method"] = "local"

        config = build_config_from_profile(prof_snapshot, _make_feed_list())
        assert config.delivery.method == "local"

    def test_feed_categories_preserved(self):
        feeds = [
            {"name": "Tech", "url": "https://example.com/tech", "category": "Technology"},
            {"name": "World", "url": "https://example.com/world"},  # no category key
        ]
        config = build_config_from_profile(_make_profile(), feeds)
        assert config.feeds[0].category == "Technology"
        assert config.feeds[1].category == ""

    def test_reading_time_minutes_parsed(self):
        """reading_time text field is parsed into reading_time_minutes."""
        prof = _make_profile(reading_time="30 min")
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.newspaper.reading_time_minutes == 30

    def test_reading_time_default(self):
        """Default reading_time from fixture is 20 min."""
        config = build_config_from_profile(_make_profile(), _make_feed_list())
        assert config.newspaper.reading_time_minutes == 20

    def test_reading_time_missing(self):
        """Missing reading_time falls back to 0 (article budget used instead)."""
        prof = _make_profile()
        del prof["reading_time"]
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.newspaper.reading_time_minutes == 0

    def test_reading_time_invalid(self):
        """Invalid reading_time text falls back to 0."""
        prof = _make_profile(reading_time="invalid")
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.newspaper.reading_time_minutes == 0

    def test_feed_stats_map_populates_frequency(self):
        """feed_stats_map populates articles_per_day and estimated_read_min."""
        feeds = _make_feed_list()
        stats_map = {
            feeds[0]["url"]: {"articles_per_day": 5.0, "estimated_read_min": 3.5},
            feeds[1]["url"]: {"articles_per_day": 0.3, "estimated_read_min": 8.0},
        }
        config = build_config_from_profile(_make_profile(), feeds, feed_stats_map=stats_map)
        assert config.feeds[0].articles_per_day == 5.0
        assert config.feeds[0].estimated_read_min == 3.5
        assert config.feeds[1].articles_per_day == 0.3
        assert config.feeds[1].estimated_read_min == 8.0

    def test_feed_stats_map_missing_feed(self):
        """Feeds not in feed_stats_map get default 0.0 values."""
        feeds = _make_feed_list()
        stats_map = {
            feeds[0]["url"]: {"articles_per_day": 5.0, "estimated_read_min": 3.5},
            # feeds[1] not in map
        }
        config = build_config_from_profile(_make_profile(), feeds, feed_stats_map=stats_map)
        assert config.feeds[1].articles_per_day == 0.0
        assert config.feeds[1].estimated_read_min == 0.0

    def test_feed_stats_map_none(self):
        """No feed_stats_map (None) preserves backward compat — all defaults."""
        config = build_config_from_profile(_make_profile(), _make_feed_list(), feed_stats_map=None)
        for fc in config.feeds:
            assert fc.articles_per_day == 0.0
            assert fc.estimated_read_min == 0.0


# ─── _build_for_user — delivery method snapshotting ─────────────────


class TestBuildForUserDeliverySnapshot:
    """Verify that _build_for_user uses record_delivery_method, not live profile."""

    @patch("scripts.build_for_users.build_newspaper")
    def test_local_delivery_method_sets_delivered(self, mock_build, tmp_path):
        """When record_delivery_method is 'local', status goes straight to 'delivered'."""
        mock_result = MagicMock()
        mock_result.epub_path = str(_make_epub(tmp_path))
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        sb.storage.from_().upload.return_value = None

        prof = _make_profile(delivery_method="google_drive")  # live profile says Drive
        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "record-1", date(2026, 3, 9),
            record_delivery_method="local",  # but record snapshot says local
        )

        # Should set status to "delivered" (not "built")
        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "delivered"

    @patch("scripts.build_for_users.build_newspaper")
    def test_drive_delivery_method_sets_built(self, mock_build, tmp_path):
        """When record_delivery_method is 'google_drive', status is 'built' (awaiting delivery)."""
        mock_result = MagicMock()
        mock_result.epub_path = str(_make_epub(tmp_path))
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        sb.storage.from_().upload.return_value = None

        prof = _make_profile(delivery_method="local")  # live profile says local
        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "record-1", date(2026, 3, 9),
            record_delivery_method="google_drive",  # but record snapshot says Drive
        )

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "built"

    @patch("scripts.build_for_users.build_newspaper")
    def test_no_record_delivery_method_falls_back_to_profile(self, mock_build, tmp_path):
        """When record_delivery_method is None, falls back to live profile."""
        mock_result = MagicMock()
        mock_result.epub_path = str(_make_epub(tmp_path))
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        sb.storage.from_().upload.return_value = None

        prof = _make_profile(delivery_method="local")
        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "record-1", date(2026, 3, 9),
            # record_delivery_method not passed — defaults to None
        )

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "delivered"  # local → delivered

    @patch("scripts.build_for_users.build_newspaper")
    def test_build_failure_marks_failed(self, mock_build):
        """Build exceptions should mark the record as failed regardless of delivery method."""
        mock_build.side_effect = Exception("Feed parsing error")

        sb = MagicMock()
        prof = _make_profile()
        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "record-1", date(2026, 3, 9),
            record_delivery_method="google_drive",
        )

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "failed"
        assert "Feed parsing error" in update_data["error_message"]


# ─── _deliver_record — delivery method snapshotting ─────────────────


class TestDeliverRecordSnapshot:
    """Verify that _deliver_record uses the record's delivery_method snapshot."""

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_uses_record_delivery_method_not_profile(self, mock_tokens, mock_deliver):
        """Delivery should use the method from the record, not the live profile."""
        mock_tokens.return_value = {"token": "t", "refresh_token": "r"}

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake epub"

        rec = _make_record(
            status="built",
            delivery_method="google_drive",  # record says Drive
            epub_storage_path="auth-1/Morning-Digest-2026-03-09.epub",
        )
        prof = _make_profile(delivery_method="local")  # but profile now says local

        _deliver_record(sb, rec, prof)

        # deliver() should have been called
        mock_deliver.assert_called_once()
        config_arg = mock_deliver.call_args[0][1]
        # The config should reflect google_drive, not local
        assert config_arg.delivery.method == "google_drive"

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_fallback_to_profile_when_record_has_no_method(self, mock_tokens, mock_deliver):
        """If record has no delivery_method, fall back to live profile."""
        mock_tokens.return_value = None

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake epub"

        rec = _make_record(
            status="built",
            delivery_method="",  # empty/falsy
            epub_storage_path="auth-1/Morning-Digest-2026-03-09.epub",
        )
        prof = _make_profile(delivery_method="local")

        _deliver_record(sb, rec, prof)

        # With local delivery, deliver() is still called (it handles "local" as a no-op log)
        config_arg = mock_deliver.call_args[0][1]
        assert config_arg.delivery.method == "local"

    def test_no_epub_path_marks_failed(self):
        """Missing epub_storage_path should mark the record as failed."""
        sb = MagicMock()
        rec = _make_record(status="built", epub_storage_path=None)
        prof = _make_profile()

        _deliver_record(sb, rec, prof)

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "failed"
        assert "No EPUB" in update_data["error_message"]

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_delivery_exception_marks_failed(self, mock_tokens, mock_deliver):
        """Delivery exceptions should mark the record as failed."""
        mock_tokens.return_value = {"token": "t", "refresh_token": "r"}
        mock_deliver.side_effect = Exception("Google Drive API error")

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake epub"

        rec = _make_record(
            status="built",
            delivery_method="google_drive",
            epub_storage_path="auth-1/Morning-Digest-2026-03-09.epub",
        )
        prof = _make_profile()

        _deliver_record(sb, rec, prof)

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "failed"
        assert "Delivery failed" in update_data["error_message"]

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_successful_delivery_updates_status(self, mock_tokens, mock_deliver):
        """Successful delivery should set status to 'delivered' with message."""
        mock_tokens.return_value = {"token": "t", "refresh_token": "r"}

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake epub"

        rec = _make_record(
            status="built",
            delivery_method="google_drive",
            epub_storage_path="auth-1/Morning-Digest-2026-03-09.epub",
        )
        prof = _make_profile()

        _deliver_record(sb, rec, prof)

        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "delivered"
        assert "Google Drive" in update_data["delivery_message"]


# ─── build_and_deliver_for_record — on-demand flow ──────────────────


def _setup_sb_for_on_demand(sb, rec, prof, feed_list=None):
    """Configure a MagicMock Supabase client for build_and_deliver_for_record tests.

    The Supabase Python client uses a chained builder pattern:
        sb.table("x").select("*").eq("k", "v").single().execute()
    MagicMock auto-creates intermediate returns, but each chained call
    returns a NEW MagicMock. To make .execute().data return our fixture,
    we must set up the chain so the final .execute() is deterministic.

    We use side_effect on sb.table() to route different table names to
    different mock chains.
    """
    # Build the record chain
    record_chain = MagicMock()
    record_chain.select.return_value.eq.return_value.single.return_value.execute.return_value = (
        MagicMock(data=rec)
    )

    # Build the profile chain
    profile_chain = MagicMock()
    profile_chain.select.return_value.eq.return_value.single.return_value.execute.return_value = (
        MagicMock(data=prof)
    )

    # Build the feeds chain
    feeds_chain = MagicMock()
    feeds_chain.select.return_value.eq.return_value.order.return_value.execute.return_value = (
        MagicMock(data=feed_list if feed_list is not None else _make_feed_list())
    )

    # Update chain (for status updates)
    update_chain = MagicMock()

    def table_router(name):
        if name == "delivery_history":
            # Return a mock that supports both .select() and .update()
            mock = MagicMock()
            mock.select = record_chain.select
            mock.update = update_chain.update
            return mock
        elif name == "user_profiles":
            return profile_chain
        elif name == "user_feeds":
            return feeds_chain
        return MagicMock()

    sb.table.side_effect = table_router

    # Return the update chain so tests can inspect calls
    return update_chain


class TestBuildAndDeliverForRecord:
    """Test the on-demand build flow with delivery method snapshotting."""

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.build_newspaper")
    @patch("scripts.build_for_users.get_supabase")
    def test_uses_record_delivery_method_for_build_and_deliver(
        self, mock_get_sb, mock_build, mock_deliver, tmp_path
    ):
        """On-demand build should use delivery_method from the record, not profile."""
        epub_path = _make_epub(tmp_path)

        mock_result = MagicMock()
        mock_result.epub_path = str(epub_path)
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        mock_get_sb.return_value = sb

        rec = _make_record(delivery_method="google_drive")
        prof = _make_profile(delivery_method="local")  # profile changed to local!

        _setup_sb_for_on_demand(sb, rec, prof)
        sb.storage.from_().upload.return_value = None

        build_and_deliver_for_record("record-1")

        # deliver() should be called because record says google_drive (not local)
        mock_deliver.assert_called_once()
        config_arg = mock_deliver.call_args[0][1]
        assert config_arg.delivery.method == "google_drive"

    @patch("scripts.build_for_users._deliver_record")
    @patch("scripts.build_for_users.get_supabase")
    def test_already_built_skips_to_delivery(self, mock_get_sb, mock_deliver_record):
        """If record is already 'built', should skip to delivery-only."""
        sb = MagicMock()
        mock_get_sb.return_value = sb

        rec = _make_record(
            status="built",
            delivery_method="google_drive",
            epub_storage_path="auth-1/Morning-Digest-2026-03-09.epub",
        )
        prof = _make_profile()

        _setup_sb_for_on_demand(sb, rec, prof)

        build_and_deliver_for_record("record-1")

        mock_deliver_record.assert_called_once_with(sb, rec, prof)

    @patch("scripts.build_for_users.get_supabase")
    def test_no_feeds_marks_failed(self, mock_get_sb):
        """On-demand build with no feeds should mark record as failed."""
        sb = MagicMock()
        mock_get_sb.return_value = sb

        rec = _make_record()
        prof = _make_profile()

        update_chain = _setup_sb_for_on_demand(sb, rec, prof, feed_list=[])

        build_and_deliver_for_record("record-1")

        update_call = update_chain.update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "failed"
        assert "No feeds" in update_data["error_message"]

    @patch("scripts.build_for_users.get_supabase")
    def test_missing_record_logs_error(self, mock_get_sb):
        """Missing record should log error and return without crashing."""
        sb = MagicMock()
        mock_get_sb.return_value = sb

        _setup_sb_for_on_demand(sb, None, _make_profile())

        # Should not raise
        build_and_deliver_for_record("missing")

    @patch("scripts.build_for_users.get_supabase")
    def test_missing_profile_marks_failed(self, mock_get_sb):
        """Missing user profile should mark record as failed."""
        sb = MagicMock()
        mock_get_sb.return_value = sb

        rec = _make_record()
        update_chain = _setup_sb_for_on_demand(sb, rec, None)

        build_and_deliver_for_record("record-1")

        update_call = update_chain.update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "failed"
        assert "profile not found" in update_data["error_message"].lower()


# ─── Delivery method mid-build scenarios ────────────────────────────


class TestMidBuildSettingsChange:
    """
    Simulate the user changing settings mid-build.

    These tests verify the invariant: the build/delivery pipeline uses
    the delivery_method that was in effect when the build was requested,
    not the current profile settings.
    """

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.build_newspaper")
    @patch("scripts.build_for_users.get_supabase")
    def test_user_switches_drive_to_local_mid_build(
        self, mock_get_sb, mock_build, mock_deliver, tmp_path
    ):
        """User clicked 'Get it now' with Google Drive, then switched to local download.

        Build should still deliver to Google Drive because that's what was in effect.
        """
        epub_path = _make_epub(tmp_path)
        mock_result = MagicMock()
        mock_result.epub_path = str(epub_path)
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        mock_get_sb.return_value = sb

        # Record was created with google_drive
        rec = _make_record(delivery_method="google_drive")
        # But profile NOW says local (user changed it)
        prof = _make_profile(delivery_method="local")

        _setup_sb_for_on_demand(sb, rec, prof)
        sb.storage.from_().upload.return_value = None

        build_and_deliver_for_record("record-1")

        # Should still deliver via google_drive
        mock_deliver.assert_called_once()
        config_arg = mock_deliver.call_args[0][1]
        assert config_arg.delivery.method == "google_drive"

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.build_newspaper")
    @patch("scripts.build_for_users.get_supabase")
    def test_user_switches_local_to_drive_mid_build(
        self, mock_get_sb, mock_build, mock_deliver, tmp_path
    ):
        """User clicked 'Get it now' with local, then switched to Google Drive.

        Build should NOT attempt Google Drive delivery — it was local originally.
        """
        epub_path = _make_epub(tmp_path)
        mock_result = MagicMock()
        mock_result.epub_path = str(epub_path)
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        mock_get_sb.return_value = sb

        # Record was created with local
        rec = _make_record(delivery_method="local")
        # But profile NOW says google_drive (user changed it)
        prof = _make_profile(delivery_method="google_drive")

        _setup_sb_for_on_demand(sb, rec, prof)
        sb.storage.from_().upload.return_value = None

        build_and_deliver_for_record("record-1")

        # Should NOT call deliver() since record says local
        mock_deliver.assert_not_called()

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.build_newspaper")
    @patch("scripts.build_for_users.get_supabase")
    def test_user_switches_drive_to_email_mid_build(
        self, mock_get_sb, mock_build, mock_deliver, tmp_path
    ):
        """User clicked 'Get it now' with Drive, then switched to email.

        Build should still deliver to Google Drive, not email.
        """
        epub_path = _make_epub(tmp_path)
        mock_result = MagicMock()
        mock_result.epub_path = str(epub_path)
        mock_result.total_articles = 5
        mock_result.sections = []
        mock_build.return_value = mock_result

        sb = MagicMock()
        mock_get_sb.return_value = sb

        rec = _make_record(delivery_method="google_drive")
        prof = _make_profile(
            delivery_method="email",
            recipient_email="kindle@kindle.com",
        )

        _setup_sb_for_on_demand(sb, rec, prof)
        sb.storage.from_().upload.return_value = None

        build_and_deliver_for_record("record-1")

        mock_deliver.assert_called_once()
        config_arg = mock_deliver.call_args[0][1]
        assert config_arg.delivery.method == "google_drive"
        # Not email
        assert config_arg.delivery.method != "email"


# ─── Helper function tests ──────────────────────────────────────────


class TestHelperFunctions:
    def test_epub_filename(self):
        assert _epub_filename("Morning Digest", "2026-03-09") == "Morning-Digest-2026-03-09.epub"
        assert _epub_filename("My Paper", "2026-01-01") == "My-Paper-2026-01-01.epub"

    def test_format_file_size_kb(self):
        assert _format_file_size(50000) == "49 KB"
        assert _format_file_size(1024) == "1 KB"

    def test_format_file_size_mb(self):
        assert _format_file_size(1_048_576) == "1.0 MB"
        assert _format_file_size(2_500_000) == "2.4 MB"

    def test_generate_delivery_message_google_drive(self):
        from paper_boy.config import Config, DeliveryConfig, GoogleDriveConfig, EmailConfig, NewspaperConfig

        config = Config(
            newspaper=NewspaperConfig(title="Test"),
            feeds=[],
            delivery=DeliveryConfig(
                method="google_drive",
                device="kobo",
                google_drive=GoogleDriveConfig(folder_name="Test Folder"),
                email=EmailConfig(),
                keep_days=30,
            ),
        )
        assert "Google Drive" in _generate_delivery_message(config)
        assert "Test Folder" in _generate_delivery_message(config)

    def test_generate_delivery_message_email(self):
        from paper_boy.config import Config, DeliveryConfig, GoogleDriveConfig, EmailConfig, NewspaperConfig

        config = Config(
            newspaper=NewspaperConfig(title="Test"),
            feeds=[],
            delivery=DeliveryConfig(
                method="email",
                device="kobo",
                google_drive=GoogleDriveConfig(),
                email=EmailConfig(recipient="user@example.com"),
                keep_days=30,
            ),
        )
        msg = _generate_delivery_message(config)
        assert "Emailed to" in msg
        assert "user@example.com" in msg

    def test_get_token_data_with_tokens(self):
        prof = _make_profile()
        token_data = get_token_data(prof)
        assert token_data is not None
        assert token_data["refresh_token"] == "refresh-token"
        # Should inject env var credentials
        assert token_data["client_id"] == "test-client-id"
        assert token_data["client_secret"] == "test-client-secret"

    def test_get_token_data_without_tokens(self):
        prof = _make_profile(google_tokens=None)
        assert get_token_data(prof) is None

    def test_get_token_data_without_refresh_token(self):
        prof = _make_profile(google_tokens={"token": "t"})
        assert get_token_data(prof) is None


# ─── Failure notification tests ──────────────────────────────────────


class TestSendFailureNotifications:
    """Verify failure notification emails are sent correctly."""

    @patch("scripts.build_for_users.resend")
    def test_sends_user_and_admin_emails(self, mock_resend):
        """Both user and admin emails should be sent on delivery failure."""
        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="email")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="'str' has no attribute 'stem'",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

        assert mock_resend.Emails.send.call_count == 2
        # First call = user email
        user_call = mock_resend.Emails.send.call_args_list[0][0][0]
        assert user_call["to"] == ["user@example.com"]
        assert "delivery issue" in user_call["subject"]
        # Second call = admin email
        admin_call = mock_resend.Emails.send.call_args_list[1][0][0]
        assert admin_call["to"] == ["admin@example.com"]
        assert "[Paper Boy]" in admin_call["subject"]

    @patch("scripts.build_for_users.resend")
    def test_skips_user_email_for_local_delivery(self, mock_resend):
        """Local/koreader users see failures on dashboard — no email needed."""
        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="local")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Build failed",
                edition_date_str="2026-03-22",
                delivery_method="local",
            )

        # Only admin email, no user email
        assert mock_resend.Emails.send.call_count == 1
        admin_call = mock_resend.Emails.send.call_args_list[0][0][0]
        assert admin_call["to"] == ["admin@example.com"]

    @patch("scripts.build_for_users.resend")
    def test_skips_user_email_for_koreader_delivery(self, mock_resend):
        """KOReader users see failures on dashboard — no email needed."""
        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="koreader")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Build failed",
                edition_date_str="2026-03-22",
                delivery_method="koreader",
            )

        # Only admin email
        assert mock_resend.Emails.send.call_count == 1

    @patch("scripts.build_for_users.resend")
    def test_no_admin_email_when_env_var_unset(self, mock_resend):
        """Without ADMIN_ALERT_EMAIL, only user email is sent."""
        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="email")

        env = {"RESEND_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("ADMIN_ALERT_EMAIL", None)
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Some error",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

        # Only user email
        assert mock_resend.Emails.send.call_count == 1
        user_call = mock_resend.Emails.send.call_args_list[0][0][0]
        assert user_call["to"] == ["user@example.com"]

    @patch("scripts.build_for_users.resend")
    def test_notification_failure_does_not_propagate(self, mock_resend):
        """Notification errors must be swallowed — never disrupt the main flow."""
        mock_resend.Emails.send.side_effect = Exception("Resend API down")

        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="email")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            # Should not raise
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Original error",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

    @patch("scripts.build_for_users.resend")
    def test_auth_lookup_failure_still_sends_admin_email(self, mock_resend):
        """If auth email lookup fails, admin alert should still be sent."""
        sb = MagicMock()
        sb.auth.admin.get_user_by_id.side_effect = Exception("Auth service down")

        prof = _make_profile(delivery_method="email")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Some error",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

        # User email skipped (no account_email), but admin email should still send
        assert mock_resend.Emails.send.call_count == 1
        admin_call = mock_resend.Emails.send.call_args_list[0][0][0]
        assert admin_call["to"] == ["admin@example.com"]

    @patch("scripts.build_for_users.resend")
    def test_no_resend_api_key_skips_everything(self, mock_resend):
        """Without RESEND_API_KEY, no emails are sent at all."""
        sb = MagicMock()
        prof = _make_profile()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEND_API_KEY", None)
            os.environ.pop("ADMIN_ALERT_EMAIL", None)
            _send_failure_notifications(
                sb,
                record_id="rec-1",
                prof=prof,
                error_message="Error",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

        mock_resend.Emails.send.assert_not_called()

    @patch("scripts.build_for_users.resend")
    def test_admin_email_contains_debug_context(self, mock_resend):
        """Admin alert email should contain all debug fields."""
        sb = MagicMock()
        auth_user = MagicMock()
        auth_user.user.email = "user@example.com"
        sb.auth.admin.get_user_by_id.return_value = auth_user

        prof = _make_profile(delivery_method="email")

        with patch.dict(os.environ, {
            "RESEND_API_KEY": "test-key",
            "ADMIN_ALERT_EMAIL": "admin@example.com",
        }):
            _send_failure_notifications(
                sb,
                record_id="rec-123",
                prof=prof,
                error_message="'str' has no attribute 'stem'",
                edition_date_str="2026-03-22",
                delivery_method="email",
            )

        # Admin email is the second call
        admin_call = mock_resend.Emails.send.call_args_list[1][0][0]
        html = admin_call["html"]
        assert "rec-123" in html
        assert "user-1" in html
        assert "email" in html
        assert "2026-03-22" in html
        assert "&#x27;str&#x27; has no attribute &#x27;stem&#x27;" in html


# ─── run_deliver — recency cap (Outcome 1) ──────────────────────────


class TestRunDeliverRecencyCap:
    """Verify run_deliver() never picks up records older than ~36h.

    Stops burst delivery: if the rare on-time deliver cron fires after
    the build cron has been failing for days, only fresh records get sent.
    """

    @patch("scripts.build_for_users._deliver_record")
    @patch("scripts.build_for_users.get_supabase")
    def test_skips_records_older_than_36h(self, mock_get_sb, mock_deliver_record):
        """Three records (2h, 24h, 48h old) — only the first two are eligible."""
        from datetime import datetime, timedelta, timezone as _tz

        now = datetime.now(_tz.utc)
        rec_2h = _make_record(
            id="rec-2h",
            user_id="user-1",
            status="built",
            created_at=(now - timedelta(hours=2)).isoformat(),
            edition_date=now.date().isoformat(),
        )
        rec_24h = _make_record(
            id="rec-24h",
            user_id="user-1",
            status="built",
            created_at=(now - timedelta(hours=24)).isoformat(),
            edition_date=(now - timedelta(days=1)).date().isoformat(),
        )
        rec_48h = _make_record(
            id="rec-48h",
            user_id="user-1",
            status="built",
            created_at=(now - timedelta(hours=48)).isoformat(),
            edition_date=(now - timedelta(days=2)).date().isoformat(),
        )

        # The Supabase Python client filters server-side, so to faithfully
        # exercise the filter we capture the .gte() call AND only return
        # records that satisfy it.
        sb = MagicMock()
        mock_get_sb.return_value = sb

        captured = {}

        def gte_side_effect(column, value):
            captured["column"] = column
            captured["value"] = value
            chain = MagicMock()
            cutoff = datetime.fromisoformat(value)
            filtered = [
                r for r in [rec_2h, rec_24h, rec_48h]
                if datetime.fromisoformat(r["created_at"]) >= cutoff
            ]
            chain.execute.return_value = MagicMock(data=filtered)
            return chain

        # status=built chain → .gte("created_at", cutoff) → .execute()
        built_chain = MagicMock()
        built_chain.select.return_value.eq.return_value.gte.side_effect = (
            gte_side_effect
        )

        # Profile chain — return a UTC user with delivery_time matching now
        prof = _make_profile(
            timezone="UTC",
            delivery_time=now.strftime("%H:%M"),
        )
        profile_chain = MagicMock()
        profile_chain.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=prof)
        )

        def table_router(name):
            if name == "delivery_history":
                return built_chain
            if name == "user_profiles":
                return profile_chain
            return MagicMock()

        sb.table.side_effect = table_router

        run_deliver()

        # The cutoff filter must be on created_at and ~36h ago
        assert captured["column"] == "created_at", (
            f"expected gte on 'created_at', got {captured.get('column')!r}"
        )
        cutoff = datetime.fromisoformat(captured["value"])
        age = now - cutoff
        # 36h ± a small fudge factor for execution time
        assert timedelta(hours=35, minutes=55) <= age <= timedelta(hours=36, minutes=5), (
            f"cutoff age was {age}, expected ~36h"
        )

        # Only records 2h and 24h old should be delivered; 48h must be skipped
        delivered_ids = [
            call_args[0][1]["id"]
            for call_args in mock_deliver_record.call_args_list
        ]
        assert "rec-2h" in delivered_ids
        assert "rec-24h" in delivered_ids
        assert "rec-48h" not in delivered_ids
        assert len(delivered_ids) == 2


# ─── _deliver_record — Resend idempotency (Outcome 3) ───────────────


class TestDeliverRecordIdempotency:
    """A record can never produce more than one email to the recipient.

    Defense-in-depth against future retry paths (PR 3 catch-up sweep,
    manual re-runs, etc.). The DB column `resend_message_id` is the
    durable proof-of-send; passing the record UUID as Resend's
    idempotency_key gives 24h server-side dedupe on top.
    """

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_skips_send_if_message_id_already_present(
        self, mock_tokens, mock_deliver
    ):
        """When resend_message_id is set, deliver() must not be called."""
        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake"

        rec = _make_record(
            status="built",
            delivery_method="email",
            epub_storage_path="auth-1/Morning-Digest-2026-05-03.epub",
            resend_message_id="msg_already_sent",
        )
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")

        _deliver_record(sb, rec, prof)

        # Email must NOT be sent again
        mock_deliver.assert_not_called()

        # Status must still flip to delivered (the email was already sent
        # in a previous run; we just need to mark this record done)
        update_call = sb.table("delivery_history").update.call_args
        assert update_call is not None
        update_data = update_call[0][0]
        assert update_data["status"] == "delivered"

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_captures_message_id_after_email_send(
        self, mock_tokens, mock_deliver
    ):
        """Successful email delivery must store the Resend message id."""
        mock_tokens.return_value = None
        mock_deliver.return_value = "msg_xyz"

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake"

        rec = _make_record(
            status="built",
            delivery_method="email",
            epub_storage_path="auth-1/Morning-Digest-2026-05-03.epub",
            resend_message_id=None,
        )
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")

        _deliver_record(sb, rec, prof)

        # The update payload must include the captured message id
        update_call = sb.table("delivery_history").update.call_args
        update_data = update_call[0][0]
        assert update_data.get("resend_message_id") == "msg_xyz"
        assert update_data["status"] == "delivered"

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_passes_record_id_as_idempotency_key(
        self, mock_tokens, mock_deliver
    ):
        """deliver() is called with idempotency_key=record_id."""
        mock_tokens.return_value = None
        mock_deliver.return_value = "msg_abc"

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake"

        rec = _make_record(
            id="rec-uuid-1",
            status="built",
            delivery_method="email",
            epub_storage_path="auth-1/Morning-Digest-2026-05-03.epub",
            resend_message_id=None,
        )
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")

        _deliver_record(sb, rec, prof)

        kwargs = mock_deliver.call_args.kwargs
        assert kwargs.get("idempotency_key") == "rec-uuid-1"

    @patch("scripts.build_for_users.deliver")
    @patch("scripts.build_for_users.get_token_data")
    def test_calling_twice_only_sends_once(self, mock_tokens, mock_deliver):
        """End-to-end: two _deliver_record calls on the same record = one send.

        Simulates a crash + retry: first call sends and writes message id;
        second call sees the message id and short-circuits.
        """
        mock_tokens.return_value = None
        mock_deliver.return_value = "msg_first"

        sb = MagicMock()
        sb.storage.from_().download.return_value = b"PK\x03\x04fake"

        rec = _make_record(
            id="rec-uuid-2",
            status="built",
            delivery_method="email",
            epub_storage_path="auth-1/Morning-Digest-2026-05-03.epub",
            resend_message_id=None,
        )
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")

        # First call — sends
        _deliver_record(sb, rec, prof)
        assert mock_deliver.call_count == 1

        # Mutate the record to reflect the first call's writeback
        rec_after = dict(rec)
        rec_after["resend_message_id"] = "msg_first"
        rec_after["status"] = "delivered"

        # Second call — short-circuits
        _deliver_record(sb, rec_after, prof)
        assert mock_deliver.call_count == 1, (
            "deliver() was called twice — idempotency guard failed"
        )


# ─── _build_for_user — empty edition path (Outcome 4) ───────────────


class TestBuildForUserEmptyEdition:
    """Empty edition has its own user-facing path.

    When the user's feeds yielded zero articles we send an explanatory
    "your sources were quiet today" email — NOT the generic failure email.
    Different failure mode, different UX.
    """

    @patch("scripts.build_for_users.resend")
    @patch("scripts.build_for_users._send_failure_notifications")
    @patch("scripts.build_for_users.build_newspaper")
    def test_empty_edition_sets_status_empty(
        self, mock_build, mock_failure, mock_resend, tmp_path, monkeypatch
    ):
        """All feeds quiet → status='empty' (not 'failed')."""
        from paper_boy.main import EmptyEditionError

        mock_build.side_effect = EmptyEditionError(feed_names=["Feed 1", "Feed 2"])
        monkeypatch.setenv("RESEND_API_KEY", "re_test")

        sb = MagicMock()
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")
        # auth admin lookup for account email
        sb.auth.admin.get_user_by_id.return_value = MagicMock(
            user=MagicMock(email="x@x.com")
        )

        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "rec-1", date(2026, 5, 3),
            record_delivery_method="email",
        )

        update_call = sb.table("delivery_history").update.call_args
        update_data = update_call[0][0]
        assert update_data["status"] == "empty"
        # Should NOT be marked failed
        assert update_data["status"] != "failed"

        # Generic failure path must NOT have run
        mock_failure.assert_not_called()

    @patch("scripts.build_for_users.resend")
    @patch("scripts.build_for_users._send_failure_notifications")
    @patch("scripts.build_for_users.build_newspaper")
    def test_empty_edition_sends_explanatory_email(
        self, mock_build, mock_failure, mock_resend, tmp_path, monkeypatch
    ):
        """The empty-edition email — not the failure email — is sent to the user."""
        from paper_boy.main import EmptyEditionError

        mock_build.side_effect = EmptyEditionError(
            feed_names=["The Verge", "Hacker News"]
        )
        monkeypatch.setenv("RESEND_API_KEY", "re_test")

        sb = MagicMock()
        prof = _make_profile(delivery_method="email", recipient_email="user@x.com")
        sb.auth.admin.get_user_by_id.return_value = MagicMock(
            user=MagicMock(email="user@x.com")
        )

        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "rec-1", date(2026, 5, 3),
            record_delivery_method="email",
        )

        # Resend was called exactly once with the empty-edition copy
        mock_resend.Emails.send.assert_called_once()
        params = mock_resend.Emails.send.call_args[0][0]
        html = params["html"]
        assert "quiet" in html.lower()
        assert "The Verge" in html
        assert "Hacker News" in html
        # Must NOT contain failure-email phrasing
        assert "we weren't able to deliver" not in html.lower()

    @patch("scripts.build_for_users.resend")
    @patch("scripts.build_for_users._send_failure_notifications")
    @patch("scripts.build_for_users.build_newspaper")
    def test_empty_edition_no_admin_alert(
        self, mock_build, mock_failure, mock_resend, tmp_path, monkeypatch
    ):
        """Empty editions are user-side, not system bugs — no admin spam."""
        from paper_boy.main import EmptyEditionError

        mock_build.side_effect = EmptyEditionError(feed_names=["Feed 1"])
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        monkeypatch.setenv("ADMIN_ALERT_EMAIL", "admin@x.com")

        sb = MagicMock()
        prof = _make_profile(delivery_method="email", recipient_email="x@x.com")
        sb.auth.admin.get_user_by_id.return_value = MagicMock(
            user=MagicMock(email="x@x.com")
        )

        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "rec-1", date(2026, 5, 3),
            record_delivery_method="email",
        )

        # Only the user email — never the admin alert template
        for call_args in mock_resend.Emails.send.call_args_list:
            params = call_args[0][0]
            assert "admin@x.com" not in params.get("to", []), (
                "Admin alert must not fire for empty editions"
            )

    @patch("scripts.build_for_users.resend")
    @patch("scripts.build_for_users.build_newspaper")
    def test_empty_edition_local_user_skips_email(
        self, mock_build, mock_resend, tmp_path, monkeypatch
    ):
        """Local/koreader users see empty state on the dashboard — no email."""
        from paper_boy.main import EmptyEditionError

        mock_build.side_effect = EmptyEditionError(feed_names=["Feed 1"])
        monkeypatch.setenv("RESEND_API_KEY", "re_test")

        sb = MagicMock()
        prof = _make_profile(delivery_method="local")

        feeds = _make_feed_list()

        _build_for_user(
            sb, prof, feeds, "rec-1", date(2026, 5, 3),
            record_delivery_method="local",
        )

        # Status still flips to empty
        update_call = sb.table("delivery_history").update.call_args
        update_data = update_call[0][0]
        assert update_data["status"] == "empty"

        # No email goes out
        mock_resend.Emails.send.assert_not_called()

    def test_skip_already_built_check_uses_neq_failed(self):
        """Sanity: an "empty" record blocks rebuild today (same as built/delivered).

        The partial unique index on (user_id, edition_date) WHERE status != 'failed'
        also includes 'empty' — so a quiet-feed morning won't trigger a rebuild
        loop. Verify by source inspection rather than a runtime mock.
        """
        import inspect
        import scripts.build_for_users as mod

        source = inspect.getsource(mod.run_build_all)
        # The dedup check must use .neq("status", "failed") so "empty" counts
        # as terminal-for-today (no rebuild).
        assert '.neq("status", "failed")' in source, (
            "run_build_all skip-check must include 'empty' in the rebuild guard"
        )
