"""Tests for delivery backends — Google Drive, Resend email, and local."""

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
    deliver_resend,
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

    @patch("paper_boy.delivery.deliver_resend")
    def test_dispatches_to_email(self, mock_resend, email_config, tmp_path):
        """method='email' calls deliver_resend."""
        epub = _make_epub_file(tmp_path)
        deliver(epub, email_config)
        mock_resend.assert_called_once_with(
            epub, email_config,
            article_count=0, source_count=0, idempotency_key=None,
        )

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


# --- TestDeliverResend ---


class TestDeliverResend:
    @pytest.fixture(autouse=True)
    def _mock_resend(self):
        """Mock the resend module since it may not be installed in test env."""
        self.mock_resend = MagicMock()
        with patch.dict("sys.modules", {"resend": self.mock_resend}):
            yield

    def test_sends_epub_via_resend(self, email_config, tmp_path, monkeypatch):
        """EPUB is sent as attachment via Resend API."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        epub = _make_epub_file(tmp_path)

        deliver_resend(epub, email_config)

        self.mock_resend.Emails.send.assert_called_once()
        call_args = self.mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["kindle@kindle.com"]
        assert "paper-boy-2026-03-01.epub" in call_args["attachments"][0]["filename"]

    def test_raises_if_no_recipient(self, make_config, tmp_path, monkeypatch):
        """ValueError raised when recipient is empty."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        config = make_config(method="email")  # recipient defaults to ""
        epub = _make_epub_file(tmp_path)
        with pytest.raises(ValueError, match="recipient"):
            deliver_resend(epub, config)

    def test_reads_epub_and_attaches(self, make_config, tmp_path, monkeypatch):
        """EPUB file content is read and included as attachment."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        config = make_config(method="email", recipient="user@example.com")
        epub = _make_epub_file(tmp_path)
        epub_content = epub.read_bytes()

        deliver_resend(epub, config)

        call_args = self.mock_resend.Emails.send.call_args[0][0]
        attachment = call_args["attachments"][0]
        assert attachment["content"] == list(epub_content)

    def test_uses_newspaper_title_in_subject(self, make_config, tmp_path, monkeypatch):
        """Email subject includes the newspaper title."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        config = make_config(method="email", recipient="user@example.com", title="My Daily News")
        epub = _make_epub_file(tmp_path)

        deliver_resend(epub, config)

        call_args = self.mock_resend.Emails.send.call_args[0][0]
        assert "My Daily News" in call_args["subject"]

    def test_raises_if_no_api_key(self, make_config, tmp_path, monkeypatch):
        """RuntimeError raised when RESEND_API_KEY is not set."""
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        config = make_config(method="email", recipient="user@example.com")
        epub = _make_epub_file(tmp_path)
        with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
            deliver_resend(epub, config)

    def test_returns_message_id_from_resend(self, email_config, tmp_path, monkeypatch):
        """deliver_resend returns the message id from Resend's response."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        epub = _make_epub_file(tmp_path)

        self.mock_resend.Emails.send.return_value = {"id": "msg_abc123"}

        result = deliver_resend(epub, email_config)
        assert result == "msg_abc123"

    def test_passes_idempotency_key_when_provided(
        self, email_config, tmp_path, monkeypatch
    ):
        """When idempotency_key is provided, it is passed to Resend's options dict."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        epub = _make_epub_file(tmp_path)

        deliver_resend(epub, email_config, idempotency_key="record-uuid-1")

        # Resend SDK signature: Emails.send(params, options)
        call_args = self.mock_resend.Emails.send.call_args
        assert len(call_args[0]) == 2, (
            "Expected Emails.send(params, options) with two positional args"
        )
        options = call_args[0][1]
        assert options == {"idempotency_key": "record-uuid-1"}

    def test_no_options_when_idempotency_key_absent(
        self, email_config, tmp_path, monkeypatch
    ):
        """No options dict when idempotency_key is None — preserves single-arg call."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        epub = _make_epub_file(tmp_path)

        deliver_resend(epub, email_config)

        call_args = self.mock_resend.Emails.send.call_args
        # Must remain a single-arg call when no idempotency key — keeps the
        # call profile identical to historical behavior for callers that
        # don't opt in.
        assert len(call_args[0]) == 1


class TestDeliverReturnsMessageId:
    """deliver() must propagate the Resend message_id back to the caller.

    The caller (scripts/build_for_users._deliver_record) stores it on
    delivery_history.resend_message_id as durable proof-of-send so the
    next retry knows not to send a second email.
    """

    @patch("paper_boy.delivery.deliver_resend")
    def test_email_method_returns_message_id(self, mock_resend, email_config, tmp_path):
        """For method='email', deliver returns whatever deliver_resend returns."""
        mock_resend.return_value = "msg_xyz"
        epub = _make_epub_file(tmp_path)

        result = deliver(epub, email_config, idempotency_key="rec-1")

        mock_resend.assert_called_once_with(
            epub, email_config, article_count=0, source_count=0,
            idempotency_key="rec-1",
        )
        assert result == "msg_xyz"

    @patch("paper_boy.delivery.deliver_google_drive")
    def test_non_email_methods_return_none(self, mock_gdrive, gdrive_config, tmp_path):
        """For non-email methods, deliver returns None (no message id to track)."""
        epub = _make_epub_file(tmp_path)
        result = deliver(epub, gdrive_config)
        assert result is None


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
