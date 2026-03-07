"""Tests for dashboard delivery setup checks."""

from __future__ import annotations

import os
from unittest.mock import patch


# --- TestDeliveryNeedsSetup ---


class TestDeliveryNeedsSetup:
    """Tests for _delivery_needs_setup — the conditional logic that determines
    whether the user still needs to configure their delivery method."""

    # -- Local delivery --

    def test_local_never_needs_setup(self):
        """Local delivery never requires additional setup."""
        from web.pages.dashboard import _delivery_needs_setup

        needs, msg = _delivery_needs_setup({"delivery_method": "local"})
        assert needs is False

    # -- Google Drive delivery --

    @patch.dict(os.environ, {}, clear=False)
    def test_google_drive_needs_setup_when_no_credentials(self):
        """Google Drive needs setup when no OAuth tokens and no service account."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)

        from web.pages.dashboard import _delivery_needs_setup

        needs, msg = _delivery_needs_setup({"delivery_method": "google_drive"})
        assert needs is True
        assert "Google" in msg

    def test_google_drive_ready_with_oauth_tokens(self):
        """Google Drive is ready when OAuth tokens with refresh_token exist."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "google_drive",
            "google_tokens": {
                "refresh_token": "1//valid-refresh-token",
                "client_id": "cid",
            },
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is False

    @patch.dict(os.environ, {"GOOGLE_CREDENTIALS": '{"type": "service_account"}'})
    def test_google_drive_ready_with_env_var(self):
        """Google Drive is ready when GOOGLE_CREDENTIALS env var is set."""
        from web.pages.dashboard import _delivery_needs_setup

        needs, msg = _delivery_needs_setup({"delivery_method": "google_drive"})
        assert needs is False

    @patch.dict(os.environ, {}, clear=False)
    def test_google_drive_not_ready_with_empty_tokens(self):
        """Google Drive needs setup when google_tokens exists but has no refresh_token."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)

        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "google_drive",
            "google_tokens": {"token": "access-only"},
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True

    @patch.dict(os.environ, {}, clear=False)
    def test_google_drive_not_ready_with_null_tokens(self):
        """Google Drive needs setup when google_tokens is None."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)

        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "google_drive",
            "google_tokens": None,
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True

    # -- Email delivery (Gmail path) --

    def test_email_gmail_ready_with_tokens_and_kindle_email(self):
        """Gmail delivery is ready when OAuth tokens include gmail.send scope."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "gmail",
            "kindle_email": "user@kindle.com",
            "google_tokens": {
                "refresh_token": "rt",
                "scopes": [
                    "https://www.googleapis.com/auth/gmail.send",
                ],
            },
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is False

    def test_email_gmail_needs_setup_without_tokens(self):
        """Gmail delivery needs setup when no OAuth tokens."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "gmail",
            "kindle_email": "user@kindle.com",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True
        assert "Google" in msg

    def test_email_gmail_needs_setup_without_gmail_scope(self):
        """Gmail delivery needs setup when tokens lack gmail.send scope."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "gmail",
            "kindle_email": "user@kindle.com",
            "google_tokens": {
                "refresh_token": "rt",
                "scopes": ["https://www.googleapis.com/auth/drive.file"],
            },
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True

    def test_email_needs_kindle_email_for_gmail(self):
        """Gmail delivery needs setup when kindle_email is missing."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "gmail",
            "kindle_email": "",
            "google_tokens": {
                "refresh_token": "rt",
                "scopes": ["https://www.googleapis.com/auth/gmail.send"],
            },
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True
        assert "Kindle email" in msg

    # -- Email delivery (SMTP path) --

    def test_email_smtp_ready_with_all_fields(self):
        """SMTP delivery is ready when sender, password, and kindle_email are set."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "smtp",
            "kindle_email": "user@kindle.com",
            "email_sender": "me@gmail.com",
            "email_password": "app-password",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is False

    def test_email_smtp_needs_setup_without_sender(self):
        """SMTP delivery needs setup when sender is empty."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "smtp",
            "kindle_email": "user@kindle.com",
            "email_sender": "",
            "email_password": "app-password",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True
        assert "SMTP" in msg

    def test_email_smtp_needs_setup_without_password(self):
        """SMTP delivery needs setup when password is empty."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "smtp",
            "kindle_email": "user@kindle.com",
            "email_sender": "me@gmail.com",
            "email_password": "",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True

    def test_email_needs_kindle_email_for_smtp(self):
        """SMTP delivery needs setup when kindle_email is missing."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            "email_method": "smtp",
            "kindle_email": "",
            "email_sender": "me@gmail.com",
            "email_password": "pwd",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True
        assert "Kindle email" in msg

    # -- Email defaults to gmail method --

    def test_email_defaults_to_gmail_method(self):
        """When email_method is not set, defaults to 'gmail' path."""
        from web.pages.dashboard import _delivery_needs_setup

        config = {
            "delivery_method": "email",
            # no email_method key
            "kindle_email": "user@kindle.com",
        }
        needs, msg = _delivery_needs_setup(config)
        assert needs is True
        assert "Google" in msg  # gmail path, not SMTP path

    # -- Unknown method --

    def test_unknown_method_does_not_need_setup(self):
        """Unknown delivery methods return no setup needed (graceful fallback)."""
        from web.pages.dashboard import _delivery_needs_setup

        needs, msg = _delivery_needs_setup({"delivery_method": "carrier_pigeon"})
        assert needs is False
