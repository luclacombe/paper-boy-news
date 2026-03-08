"""Tests for POST /deliver endpoint."""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

# A minimal valid base64 blob to use as EPUB content.
FAKE_EPUB_B64 = base64.b64encode(b"PK\x00\x00fake-epub-content").decode()


class TestDeliverEndpoint:
    """Tests for the /deliver API route."""

    @patch("api.routes.deliver.deliver")
    def test_deliver_local_success(self, mock_deliver, api_client, auth_header):
        """Local delivery returns 'Download ready' message."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": FAKE_EPUB_B64,
                "delivery_method": "local",
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Download ready"

    @patch("api.routes.deliver.deliver")
    def test_deliver_google_drive_message(self, mock_deliver, api_client, auth_header):
        """Google Drive delivery message includes folder name."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": FAKE_EPUB_B64,
                "delivery_method": "google_drive",
                "google_drive_folder": "My Kobo",
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is True
        assert "My Kobo" in data["message"]

    @patch("api.routes.deliver.deliver")
    def test_deliver_gmail_api_routing(self, mock_deliver, api_client, auth_header):
        """Email + Gmail scope routes to gmail_api internally."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": FAKE_EPUB_B64,
                "delivery_method": "email",
                "kindle_email": "me@kindle.com",
                "google_tokens": {
                    "token": "t",
                    "refresh_token": "r",
                    "scopes": ["https://www.googleapis.com/auth/gmail.send"],
                },
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is True
        assert "via Gmail" in data["message"]

        # Verify deliver() was called with gmail_api method
        call_config = mock_deliver.call_args[0][1]
        assert call_config.delivery.method == "gmail_api"

    @patch("api.routes.deliver.deliver")
    def test_deliver_email_message(self, mock_deliver, api_client, auth_header):
        """Email delivery message includes recipient."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": FAKE_EPUB_B64,
                "delivery_method": "email",
                "kindle_email": "user@kindle.com",
                "email_sender": "me@gmail.com",
                "email_password": "secret",
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is True
        assert "user@kindle.com" in data["message"]

    @patch("api.routes.deliver.deliver", side_effect=Exception("upload failed"))
    def test_deliver_exception_returns_failure(self, mock_deliver, api_client, auth_header):
        """Delivery exceptions are caught and returned as success=False."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": FAKE_EPUB_B64,
                "delivery_method": "google_drive",
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is False
        assert "Delivery failed" in data["message"]

    def test_deliver_invalid_base64(self, api_client, auth_header):
        """Invalid base64 in epub_base64 returns error gracefully."""
        resp = api_client.post(
            "/deliver",
            json={
                "epub_base64": "!!!not-valid-base64!!!",
                "delivery_method": "local",
            },
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is False
