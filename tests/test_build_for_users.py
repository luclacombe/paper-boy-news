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
    build_and_deliver_for_record,
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
        "include_images": True,
        "device": "kobo",
        "delivery_method": "google_drive",
        "google_drive_folder": "Rakuten Kobo",
        "kindle_email": "",
        "email_smtp_host": "smtp.gmail.com",
        "email_smtp_port": 465,
        "email_sender": "",
        "email_password": "",
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

    def test_gmail_api_detection(self):
        """Email method with gmail.send scope should route to gmail_api."""
        prof = _make_profile(
            delivery_method="email",
            google_tokens={
                "token": "t",
                "refreshToken": "r",
                "scopes": ["https://www.googleapis.com/auth/gmail.send"],
            },
        )
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.delivery.method == "gmail_api"

    def test_email_without_gmail_scope(self):
        """Email method without gmail.send scope stays as regular email."""
        prof = _make_profile(
            delivery_method="email",
            google_tokens={
                "token": "t",
                "refreshToken": "r",
                "scopes": ["https://www.googleapis.com/auth/drive.file"],
            },
        )
        config = build_config_from_profile(prof, _make_feed_list())
        assert config.delivery.method == "email"

    def test_email_without_tokens(self):
        """Email method without any Google tokens stays as regular email."""
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
            email_sender="me@gmail.com",
            email_password="pass",
            kindle_email="kindle@kindle.com",
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

    def test_generate_delivery_message(self):
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
