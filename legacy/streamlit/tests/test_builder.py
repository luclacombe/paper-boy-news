"""Tests for the web app builder service (bridge to paper_boy)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_boy.config import (
    Config,
    DeliveryConfig,
    EmailConfig,
    FeedConfig,
    GoogleDriveConfig,
    NewspaperConfig,
)
from web.services.builder import (
    build_edition,
    config_from_user_data,
    deliver_edition,
    preview_feeds,
)


# --- TestConfigFromUserData ---


class TestConfigFromUserData:
    def test_creates_valid_config(self, sample_user_config):
        """Returns a Config with all fields populated from user data."""
        config = config_from_user_data(sample_user_config)
        assert isinstance(config, Config)
        assert isinstance(config.newspaper, NewspaperConfig)
        assert isinstance(config.delivery, DeliveryConfig)

    def test_maps_feeds_correctly(self, sample_user_config):
        """feeds list[dict] -> list[FeedConfig]."""
        config = config_from_user_data(sample_user_config)
        assert len(config.feeds) == 3
        assert all(isinstance(f, FeedConfig) for f in config.feeds)
        assert config.feeds[0].name == "Tech News"
        assert config.feeds[0].url == "https://example.com/tech/rss"

    def test_maps_newspaper_settings(self, sample_user_config):
        """title, language, max_articles_per_feed, include_images are set."""
        config = config_from_user_data(sample_user_config)
        assert config.newspaper.title == "Morning Digest"
        assert config.newspaper.language == "en"
        assert config.newspaper.max_articles_per_feed == 10
        assert config.newspaper.include_images is True

    def test_maps_google_drive_settings(self, sample_user_config):
        """google_drive_folder -> GoogleDriveConfig.folder_name."""
        config = config_from_user_data(sample_user_config)
        assert isinstance(config.delivery.google_drive, GoogleDriveConfig)
        assert config.delivery.google_drive.folder_name == "Rakuten Kobo"

    def test_maps_email_settings(self, sample_user_config):
        """email_* and kindle_email -> EmailConfig fields."""
        sample_user_config["email_sender"] = "me@gmail.com"
        sample_user_config["email_password"] = "secret"
        sample_user_config["kindle_email"] = "kindle@kindle.com"

        config = config_from_user_data(sample_user_config)
        assert isinstance(config.delivery.email, EmailConfig)
        assert config.delivery.email.sender == "me@gmail.com"
        assert config.delivery.email.password == "secret"
        assert config.delivery.email.recipient == "kindle@kindle.com"

    def test_maps_delivery_method(self, sample_user_config):
        """delivery_method -> DeliveryConfig.method."""
        sample_user_config["delivery_method"] = "google_drive"
        config = config_from_user_data(sample_user_config)
        assert config.delivery.method == "google_drive"

    def test_defaults_for_missing_keys(self):
        """Missing keys in user_config use defaults."""
        config = config_from_user_data({})
        assert config.newspaper.title == "Morning Digest"
        assert config.newspaper.language == "en"
        assert config.delivery.method == "local"
        assert config.delivery.device == "kobo"

    def test_empty_feeds_produces_empty_list(self):
        """No feeds key -> empty feeds list."""
        config = config_from_user_data({"title": "Test"})
        assert config.feeds == []


# --- TestBuildEdition ---


class TestBuildEdition:
    @patch("web.services.builder.build_newspaper")
    def test_builds_epub(self, mock_build, sample_user_config):
        """build_edition calls build_newspaper and returns BuildResult."""
        from paper_boy.main import BuildResult

        mock_build.return_value = BuildResult(
            epub_path=Path("/tmp/paper-boy-2026-03-01.epub"),
            sections=[],
            total_articles=5,
        )

        result = build_edition(sample_user_config, issue_date=date(2026, 3, 1))
        assert result.epub_path == Path("/tmp/paper-boy-2026-03-01.epub")
        mock_build.assert_called_once()

    def test_raises_value_error_when_no_feeds(self):
        """ValueError raised when feeds list is empty."""
        with pytest.raises(ValueError, match="No feeds configured"):
            build_edition({"feeds": []})

    def test_raises_value_error_when_feeds_missing(self):
        """ValueError raised when feeds key is absent."""
        with pytest.raises(ValueError, match="No feeds configured"):
            build_edition({})

    @patch("web.services.builder.build_newspaper")
    def test_uses_temp_dir_when_output_dir_none(self, mock_build, sample_user_config):
        """tempfile.mkdtemp is used when output_dir is not specified."""
        from paper_boy.main import BuildResult

        mock_build.return_value = BuildResult(
            epub_path=Path("/tmp/paperboy_abc/paper-boy-2026-03-01.epub"),
            sections=[],
            total_articles=3,
        )

        build_edition(sample_user_config, issue_date=date(2026, 3, 1))

        call_kwargs = mock_build.call_args[1]
        # output_path should be in a temp directory
        assert "paperboy_" in str(call_kwargs["output_path"]) or "/tmp" in str(call_kwargs["output_path"])

    @patch("web.services.builder.build_newspaper")
    def test_output_filename_includes_date(self, mock_build, sample_user_config):
        """EPUB filename is paper-boy-YYYY-MM-DD.epub."""
        from paper_boy.main import BuildResult

        mock_build.return_value = BuildResult(
            epub_path=Path("/tmp/paper-boy-2026-03-01.epub"),
            sections=[],
            total_articles=3,
        )

        build_edition(sample_user_config, issue_date=date(2026, 3, 1))

        call_kwargs = mock_build.call_args[1]
        assert "2026-03-01" in str(call_kwargs["output_path"])


# --- TestDeliverEdition ---


class TestDeliverEdition:
    def test_local_returns_download_ready(self, sample_user_config):
        """Local delivery returns (True, 'Download ready')."""
        sample_user_config["delivery_method"] = "local"

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)
        assert success is True
        assert msg == "Download ready"

    @patch("web.services.builder.deliver")
    def test_google_drive_returns_success_message(self, mock_deliver, sample_user_config):
        """Google Drive delivery returns (True, 'Uploaded to...')."""
        sample_user_config["delivery_method"] = "google_drive"

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)
        assert success is True
        assert "Google Drive" in msg

    @patch("web.services.builder.deliver")
    def test_email_returns_success_message(self, mock_deliver, sample_user_config):
        """Email delivery returns (True, 'Emailed to...')."""
        sample_user_config["delivery_method"] = "email"
        sample_user_config["kindle_email"] = "kindle@kindle.com"

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)
        assert success is True
        assert "Emailed" in msg

    @patch("web.services.builder.deliver", side_effect=RuntimeError("upload failed"))
    def test_failure_returns_false_with_error(self, mock_deliver, sample_user_config):
        """Exception in deliver returns (False, error_message)."""
        sample_user_config["delivery_method"] = "google_drive"

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)
        assert success is False
        assert "upload failed" in msg

    @patch("web.services.builder.deliver")
    def test_gmail_api_routing_when_tokens_have_gmail_scope(
        self, mock_deliver, sample_user_config
    ):
        """Email delivery routes to gmail_api when tokens include gmail.send scope."""
        sample_user_config["delivery_method"] = "email"
        sample_user_config["kindle_email"] = "kindle@kindle.com"
        sample_user_config["google_tokens"] = {
            "refresh_token": "rt",
            "client_id": "cid",
            "client_secret": "cs",
            "scopes": [
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/gmail.send",
            ],
        }

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)

        assert success is True
        assert "Gmail" in msg
        # Verify deliver was called with method overridden to gmail_api
        call_args = mock_deliver.call_args
        config = call_args[0][1]
        assert config.delivery.method == "email"  # restored after call
        assert call_args[1]["token_data"] is not None

    @patch("web.services.builder.deliver")
    def test_email_smtp_when_no_gmail_scope(self, mock_deliver, sample_user_config):
        """Email delivery uses SMTP when tokens lack gmail.send scope."""
        sample_user_config["delivery_method"] = "email"
        sample_user_config["kindle_email"] = "kindle@kindle.com"
        sample_user_config["google_tokens"] = {
            "refresh_token": "rt",
            "client_id": "cid",
            "client_secret": "cs",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        }

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)

        assert success is True
        assert "Emailed" in msg  # SMTP path, not "via Gmail"

    @patch("web.services.builder.deliver")
    def test_email_smtp_when_no_tokens(self, mock_deliver, sample_user_config):
        """Email delivery uses SMTP when no google_tokens at all."""
        sample_user_config["delivery_method"] = "email"
        sample_user_config["kindle_email"] = "kindle@kindle.com"

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)

        assert success is True
        assert "Emailed" in msg

    @patch("web.services.builder.deliver")
    def test_google_drive_passes_token_data(self, mock_deliver, sample_user_config):
        """Google Drive delivery passes token_data through."""
        sample_user_config["delivery_method"] = "google_drive"
        tokens = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}
        sample_user_config["google_tokens"] = tokens

        deliver_edition("/tmp/test.epub", sample_user_config)

        call_kwargs = mock_deliver.call_args[1]
        assert call_kwargs["token_data"] is tokens

    @patch("web.services.builder.deliver", side_effect=Exception("token expired"))
    def test_gmail_api_failure_returns_error(self, mock_deliver, sample_user_config):
        """Gmail API delivery failure returns (False, error message)."""
        sample_user_config["delivery_method"] = "email"
        sample_user_config["kindle_email"] = "kindle@kindle.com"
        sample_user_config["google_tokens"] = {
            "refresh_token": "rt",
            "client_id": "cid",
            "client_secret": "cs",
            "scopes": ["https://www.googleapis.com/auth/gmail.send"],
        }

        success, msg = deliver_edition("/tmp/test.epub", sample_user_config)

        assert success is False
        assert "token expired" in msg


# --- TestPreviewFeeds ---


class TestPreviewFeeds:
    @patch("web.services.builder.fetch_feeds")
    def test_returns_sections(self, mock_fetch, sample_user_config):
        """preview_feeds returns list of Section objects."""
        from paper_boy.feeds import Section

        mock_fetch.return_value = [Section(name="Tech", articles=[])]

        sections = preview_feeds(sample_user_config)
        assert len(sections) == 1
        assert sections[0].name == "Tech"

    def test_returns_empty_when_no_feeds(self):
        """Empty feeds list returns empty sections list."""
        assert preview_feeds({"feeds": []}) == []
        assert preview_feeds({}) == []
