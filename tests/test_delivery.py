"""Tests for delivery backends — Google Drive, email, and local."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_boy.delivery import (
    _cleanup_old_issues,
    _find_or_create_folder,
    _get_google_credentials,
    deliver,
    deliver_email,
    deliver_gmail_api,
)


# --- Helpers ---


def _make_epub_file(tmp_path: Path) -> Path:
    """Create a dummy EPUB file for delivery tests."""
    epub = tmp_path / "paper-boy-2026-03-01.epub"
    epub.write_bytes(b"PK\x03\x04fake epub content")
    return epub


def _make_mock_drive_service():
    """Build a mock Google Drive service with chained method calls."""
    service = MagicMock()
    # files().list().execute() chain
    service.files().list().execute.return_value = {"files": []}
    # files().create().execute() chain for folder creation
    service.files().create().execute.return_value = {"id": "folder-123"}
    return service


# --- TestDeliver (router) ---


class TestDeliver:
    @patch("paper_boy.delivery.deliver_google_drive")
    def test_dispatches_to_google_drive(self, mock_gdrive, gdrive_config, tmp_path):
        """method='google_drive' calls deliver_google_drive."""
        epub = _make_epub_file(tmp_path)
        deliver(epub, gdrive_config)
        mock_gdrive.assert_called_once_with(epub, gdrive_config, token_data=None)

    @patch("paper_boy.delivery.deliver_email")
    def test_dispatches_to_email(self, mock_email, email_config, tmp_path):
        """method='email' calls deliver_email."""
        epub = _make_epub_file(tmp_path)
        deliver(epub, email_config)
        mock_email.assert_called_once_with(epub, email_config)

    @patch("paper_boy.delivery.deliver_gmail_api")
    def test_dispatches_to_gmail_api(self, mock_gmail, make_config, tmp_path):
        """method='gmail_api' calls deliver_gmail_api."""
        config = make_config(method="gmail_api", recipient="k@kindle.com")
        epub = _make_epub_file(tmp_path)
        token_data = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}
        deliver(epub, config, token_data=token_data)
        mock_gmail.assert_called_once_with(epub, config, token_data=token_data)

    @patch("paper_boy.delivery.deliver_google_drive")
    def test_passes_token_data_to_google_drive(self, mock_gdrive, gdrive_config, tmp_path):
        """token_data kwarg is forwarded to deliver_google_drive."""
        epub = _make_epub_file(tmp_path)
        tokens = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}
        deliver(epub, gdrive_config, token_data=tokens)
        mock_gdrive.assert_called_once_with(epub, gdrive_config, token_data=tokens)

    def test_local_delivery_no_error(self, local_config, tmp_path):
        """method='local' just logs, no error raised."""
        epub = _make_epub_file(tmp_path)
        deliver(epub, local_config)  # should not raise

    def test_unknown_method_raises_value_error(self, make_config, tmp_path):
        """Unknown method raises ValueError with method name."""
        config = make_config(method="pigeon")
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="pigeon"):
            deliver(epub, config)


# --- TestDeliverEmail ---


class TestDeliverEmail:
    @patch("smtplib.SMTP_SSL")
    def test_sends_email_with_attachment(self, mock_smtp_cls, email_config, tmp_path):
        """EPUB is sent as attachment via SMTP_SSL."""
        epub = _make_epub_file(tmp_path)
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        deliver_email(epub, email_config)

        mock_server.login.assert_called_once_with("me@gmail.com", "app-secret")
        mock_server.send_message.assert_called_once()

    def test_raises_if_no_sender(self, make_config, tmp_path):
        """ValueError raised when sender is empty."""
        config = make_config(method="email", recipient="k@kindle.com", password="pwd")
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="sender and recipient"):
            deliver_email(epub, config)

    def test_raises_if_no_recipient(self, make_config, tmp_path):
        """ValueError raised when recipient is empty."""
        config = make_config(method="email", sender="me@gmail.com", password="pwd")
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="sender and recipient"):
            deliver_email(epub, config)

    def test_raises_if_no_password(self, make_config, tmp_path):
        """ValueError raised when password is empty."""
        config = make_config(
            method="email", sender="me@gmail.com", recipient="k@kindle.com"
        )
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="app password"):
            deliver_email(epub, config)

    @patch("smtplib.SMTP_SSL")
    def test_uses_correct_smtp_host_and_port(self, mock_smtp_cls, make_config, tmp_path):
        """SMTP_SSL is called with configured host and port."""
        config = make_config(
            method="email",
            sender="me@gmail.com",
            password="pwd",
            recipient="k@kindle.com",
            smtp_host="smtp.custom.com",
            smtp_port=587,
        )
        epub = _make_epub_file(tmp_path)
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        deliver_email(epub, config)

        mock_smtp_cls.assert_called_once_with("smtp.custom.com", 587)


# --- TestGetGoogleCredentials ---


class TestGetGoogleCredentials:
    @staticmethod
    def _mock_google_modules():
        """Create properly wired mock Google modules for lazy import."""
        mock_sa = MagicMock()
        mock_oauth2 = MagicMock()
        mock_oauth2.service_account = mock_sa
        mock_google = MagicMock()
        mock_google.oauth2 = mock_oauth2
        modules = {
            "google": mock_google,
            "google.oauth2": mock_oauth2,
            "google.oauth2.service_account": mock_sa,
        }
        return mock_sa, modules

    @patch.dict(os.environ, {"GOOGLE_CREDENTIALS": json.dumps({"type": "service_account"})})
    def test_loads_from_env_var(self, gdrive_config):
        """GOOGLE_CREDENTIALS env var is parsed as JSON."""
        mock_sa, modules = self._mock_google_modules()
        mock_sa.Credentials.from_service_account_info.return_value = MagicMock()

        with patch.dict("sys.modules", modules):
            creds = _get_google_credentials(gdrive_config)

        mock_sa.Credentials.from_service_account_info.assert_called_once()
        assert creds is not None

    @patch.dict(os.environ, {}, clear=False)
    def test_loads_from_file(self, make_config, tmp_path):
        """credentials_file path is used when env var is absent."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)

        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        config = make_config(method="google_drive", credentials_file=str(creds_file))

        mock_sa, modules = self._mock_google_modules()
        mock_sa.Credentials.from_service_account_file.return_value = MagicMock()

        with patch.dict("sys.modules", modules):
            creds = _get_google_credentials(config)

        mock_sa.Credentials.from_service_account_file.assert_called_once()
        assert creds is not None

    @patch.dict(os.environ, {}, clear=False)
    def test_raises_file_not_found_when_neither(self, gdrive_config):
        """FileNotFoundError raised when no credentials source exists."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)

        mock_sa, modules = self._mock_google_modules()
        with patch.dict("sys.modules", modules):
            with pytest.raises(FileNotFoundError, match="Google credentials not found"):
                _get_google_credentials(gdrive_config)


# --- TestFindOrCreateFolder ---


class TestFindOrCreateFolder:
    def test_returns_existing_folder_id(self):
        """Returns folder ID when query finds existing folder."""
        service = MagicMock()
        service.files().list().execute.return_value = {
            "files": [{"id": "existing-folder-id", "name": "Rakuten Kobo"}]
        }

        result = _find_or_create_folder(service, "Rakuten Kobo")
        assert result == "existing-folder-id"

    def test_creates_folder_when_none_found(self):
        """Creates folder and returns new ID when no folder matches."""
        service = MagicMock()
        service.files().list().execute.return_value = {"files": []}
        service.files().create().execute.return_value = {"id": "new-folder-id"}

        result = _find_or_create_folder(service, "Rakuten Kobo")
        assert result == "new-folder-id"


# --- TestCleanupOldIssues ---


class TestCleanupOldIssues:
    def test_deletes_old_files(self):
        """Files older than keep_days are deleted."""
        service = MagicMock()
        service.files().list().execute.return_value = {
            "files": [
                {"id": "old-1", "name": "paper-boy-2025-01-01.epub"},
                {"id": "old-2", "name": "paper-boy-2025-01-02.epub"},
            ]
        }

        _cleanup_old_issues(service, "folder-id", keep_days=30)

        assert service.files().delete.call_count >= 1

    def test_no_op_when_keep_days_zero(self):
        """keep_days=0 means no cleanup attempt."""
        service = MagicMock()
        _cleanup_old_issues(service, "folder-id", keep_days=0)
        service.files().list.assert_not_called()

    def test_no_op_when_no_old_files(self):
        """No deletions when no files match the cutoff."""
        service = MagicMock()
        service.files().list().execute.return_value = {"files": []}

        _cleanup_old_issues(service, "folder-id", keep_days=30)
        service.files().delete.assert_not_called()


# --- TestDeliverGmailApi ---


class TestDeliverGmailApi:
    @patch("paper_boy.delivery._get_google_credentials")
    @patch("googleapiclient.discovery.build")
    def test_sends_epub_via_gmail_api(self, mock_build, mock_get_creds, make_config, tmp_path):
        """EPUB is sent as attachment through Gmail API."""
        config = make_config(method="gmail_api", recipient="kindle@kindle.com")
        epub = _make_epub_file(tmp_path)
        token_data = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_get_creds.return_value = MagicMock()

        deliver_gmail_api(epub, config, token_data=token_data)

        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_get_creds.return_value)
        mock_service.users().messages().send.assert_called_once()

    def test_raises_if_no_recipient(self, make_config, tmp_path):
        """ValueError raised when recipient email is empty."""
        config = make_config(method="gmail_api")  # recipient defaults to ""
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="recipient"):
            deliver_gmail_api(epub, config, token_data={"refresh_token": "rt"})

    @patch("paper_boy.delivery._get_google_credentials")
    @patch("googleapiclient.discovery.build")
    def test_passes_token_data_to_get_credentials(
        self, mock_build, mock_get_creds, make_config, tmp_path
    ):
        """token_data is forwarded to _get_google_credentials."""
        config = make_config(method="gmail_api", recipient="k@kindle.com")
        epub = _make_epub_file(tmp_path)
        tokens = {"refresh_token": "rt", "client_id": "cid", "client_secret": "cs"}

        mock_build.return_value = MagicMock()
        mock_get_creds.return_value = MagicMock()

        deliver_gmail_api(epub, config, token_data=tokens)

        mock_get_creds.assert_called_once_with(config, token_data=tokens)

    @patch("paper_boy.delivery._get_google_credentials")
    @patch("googleapiclient.discovery.build")
    def test_uses_newspaper_title_as_subject(
        self, mock_build, mock_get_creds, make_config, tmp_path
    ):
        """Email subject is the configured newspaper title."""
        config = make_config(
            method="gmail_api", recipient="k@kindle.com", title="My Daily News"
        )
        epub = _make_epub_file(tmp_path)

        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_get_creds.return_value = MagicMock()

        deliver_gmail_api(epub, config, token_data={"refresh_token": "rt"})

        call_kwargs = mock_service.users().messages().send.call_args[1]
        assert call_kwargs["userId"] == "me"


# --- TestGetGoogleCredentialsOAuth ---


class TestGetGoogleCredentialsOAuth:
    """Tests for the OAuth2 token_data path in _get_google_credentials."""

    def _make_token_data(self, **overrides):
        """Build a valid token_data dict with optional overrides."""
        data = {
            "token": "ya29.access-token",
            "refresh_token": "1//refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
            "expiry": None,
        }
        data.update(overrides)
        return data

    @patch("google.auth.transport.requests.Request")
    @patch("google.oauth2.credentials.Credentials")
    def test_oauth2_path_takes_priority(self, mock_creds_cls, mock_request, gdrive_config):
        """OAuth2 token_data is used when provided, even if env var exists."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_cls.return_value = mock_creds

        token_data = self._make_token_data()
        result = _get_google_credentials(gdrive_config, token_data=token_data)

        assert result is mock_creds
        mock_creds_cls.assert_called_once()

    @patch("google.auth.transport.requests.Request")
    @patch("google.oauth2.credentials.Credentials")
    def test_refreshes_expired_oauth2_token(self, mock_creds_cls, mock_request, gdrive_config):
        """Expired OAuth2 credentials are refreshed."""
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "1//refresh"
        mock_creds.token = "new-access-token"
        mock_creds.expiry = MagicMock()
        mock_creds.expiry.isoformat.return_value = "2026-03-02T13:00:00"
        mock_creds_cls.return_value = mock_creds

        token_data = self._make_token_data()
        _get_google_credentials(gdrive_config, token_data=token_data)

        mock_creds.refresh.assert_called_once()
        assert token_data["token"] == "new-access-token"
        assert token_data["expiry"] == "2026-03-02T13:00:00"

    @patch.dict(os.environ, {}, clear=False)
    def test_skips_oauth2_when_no_refresh_token(self, gdrive_config):
        """Falls through to service account when token_data lacks refresh_token."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)
        token_data = {"token": "access-only"}  # no refresh_token

        # Should fall through and hit FileNotFoundError (no service account either)
        with pytest.raises(FileNotFoundError):
            _get_google_credentials(gdrive_config, token_data=token_data)

    @patch.dict(os.environ, {}, clear=False)
    def test_skips_oauth2_when_token_data_none(self, gdrive_config):
        """Falls through to service account when token_data is None."""
        os.environ.pop("GOOGLE_CREDENTIALS", None)
        with pytest.raises(FileNotFoundError):
            _get_google_credentials(gdrive_config, token_data=None)
