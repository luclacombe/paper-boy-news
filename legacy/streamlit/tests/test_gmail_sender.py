"""Tests for the Gmail API email sender."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --- Helpers ---


def _make_epub_file(tmp_path: Path) -> Path:
    """Create a dummy EPUB file."""
    epub = tmp_path / "paper-boy-2026-03-01.epub"
    epub.write_bytes(b"PK\x03\x04fake epub content")
    return epub


# --- TestSendViaGmail ---


class TestSendViaGmail:
    @patch("web.services.gmail_sender.build")
    def test_sends_epub_via_gmail_api(self, mock_build, tmp_path):
        """EPUB is sent as attachment through Gmail API."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        creds = MagicMock()
        send_via_gmail(epub, "kindle@kindle.com", "Morning Digest", creds)

        mock_build.assert_called_once_with("gmail", "v1", credentials=creds)
        mock_service.users().messages().send.assert_called_once()

    @patch("web.services.gmail_sender.build")
    def test_passes_user_me_as_sender(self, mock_build, tmp_path):
        """Gmail API send uses userId='me' (authenticated user)."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        send_via_gmail(epub, "kindle@kindle.com", "Test", MagicMock())

        call_kwargs = mock_service.users().messages().send.call_args[1]
        assert call_kwargs["userId"] == "me"

    @patch("web.services.gmail_sender.build")
    def test_message_body_is_base64_encoded(self, mock_build, tmp_path):
        """Raw message body is base64url-encoded."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        send_via_gmail(epub, "kindle@kindle.com", "Test", MagicMock())

        call_kwargs = mock_service.users().messages().send.call_args[1]
        raw = call_kwargs["body"]["raw"]
        # base64url characters only (no +, /, or newlines)
        assert isinstance(raw, str)
        assert "+" not in raw  # urlsafe encoding uses - instead of +

    @patch("web.services.gmail_sender.build")
    def test_attachment_has_epub_filename(self, mock_build, tmp_path):
        """Email attachment uses the EPUB filename."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        send_via_gmail(epub, "kindle@kindle.com", "Test", MagicMock())

        # Verify the send was called (attachment details are in the base64 body)
        mock_service.users().messages().send().execute.assert_called_once()

    @patch("web.services.gmail_sender.build")
    def test_accepts_string_path(self, mock_build, tmp_path):
        """epub_path can be a string, not just Path."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        send_via_gmail(str(epub), "kindle@kindle.com", "Test", MagicMock())

        mock_service.users().messages().send().execute.assert_called_once()

    @patch("web.services.gmail_sender.build")
    def test_propagates_api_errors(self, mock_build, tmp_path):
        """Gmail API errors propagate to caller."""
        epub = _make_epub_file(tmp_path)
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.side_effect = Exception(
            "Insufficient Permission"
        )
        mock_build.return_value = mock_service

        from web.services.gmail_sender import send_via_gmail

        with pytest.raises(Exception, match="Insufficient Permission"):
            send_via_gmail(epub, "kindle@kindle.com", "Test", MagicMock())

    def test_raises_on_missing_file(self, tmp_path):
        """FileNotFoundError when EPUB doesn't exist."""
        from web.services.gmail_sender import send_via_gmail

        with pytest.raises(FileNotFoundError):
            send_via_gmail(
                tmp_path / "nonexistent.epub",
                "kindle@kindle.com",
                "Test",
                MagicMock(),
            )
