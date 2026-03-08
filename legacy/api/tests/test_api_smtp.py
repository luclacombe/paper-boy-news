"""Tests for POST /smtp-test endpoint."""

from __future__ import annotations

import smtplib
import socket
import ssl
from unittest.mock import MagicMock, patch

import pytest

SMTP_PAYLOAD = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "sender": "me@gmail.com",
    "password": "app-password",
}


class TestSmtpTestEndpoint:
    """Tests for the /smtp-test API route."""

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_ssl_connection_success(self, mock_smtp, api_client, auth_header):
        """Port 465 connects via SMTP_SSL and returns success."""
        ctx = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is True
        assert "successful" in data["message"].lower()

    @patch("api.routes.smtp_test.smtplib.SMTP")
    def test_starttls_connection_success(self, mock_smtp, api_client, auth_header):
        """Port 587 connects via SMTP + STARTTLS and returns success."""
        ctx = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        payload = {**SMTP_PAYLOAD, "smtp_port": 587}
        resp = api_client.post("/smtp-test", json=payload, headers=auth_header)
        data = resp.json()
        assert data["success"] is True

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_auth_error_534_suggests_app_password(self, mock_smtp, api_client, auth_header):
        """534 error returns App Password guidance."""
        mock_smtp.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPAuthenticationError(534, b"App Password required")
        )
        mock_smtp.return_value.__exit__ = MagicMock(return_value=True)

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is False
        assert "App Password" in data["message"]

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_auth_error_535_suggests_check_credentials(self, mock_smtp, api_client, auth_header):
        """535 error returns credential check message."""
        mock_smtp.return_value.__enter__ = MagicMock(
            side_effect=smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        )
        mock_smtp.return_value.__exit__ = MagicMock(return_value=True)

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is False
        assert "Authentication failed" in data["message"]

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_timeout_returns_clear_message(self, mock_smtp, api_client, auth_header):
        """Socket timeout returns timeout message."""
        mock_smtp.side_effect = socket.timeout("Connection timed out")

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is False
        assert "timed out" in data["message"]

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_dns_failure_returns_hostname_message(self, mock_smtp, api_client, auth_header):
        """DNS resolution failure returns hostname message."""
        mock_smtp.side_effect = socket.gaierror("Name resolution failed")

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is False
        assert "resolve hostname" in data["message"].lower()

    @patch("api.routes.smtp_test.smtplib.SMTP_SSL")
    def test_connection_refused_returns_port_message(self, mock_smtp, api_client, auth_header):
        """Connection refused returns port check message."""
        mock_smtp.side_effect = ConnectionRefusedError()

        resp = api_client.post("/smtp-test", json=SMTP_PAYLOAD, headers=auth_header)
        data = resp.json()
        assert data["success"] is False
        assert "refused" in data["message"].lower()
