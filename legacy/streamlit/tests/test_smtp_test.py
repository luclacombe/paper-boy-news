"""Tests for the SMTP connection testing service."""

from __future__ import annotations

import smtplib
import socket
import ssl
from unittest.mock import MagicMock, patch

from web.services.smtp_test import check_smtp_connection


# --- TestSuccessfulConnection ---


class TestSuccessfulConnection:
    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_port_465_uses_smtp_ssl(self, mock_smtp_ssl):
        """Port 465 connects via SMTP_SSL (implicit SSL)."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@gmail.com", "password")

        assert success is True
        assert "successful" in msg.lower()
        mock_smtp_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=10)

    @patch("web.services.smtp_test.smtplib.SMTP")
    def test_port_587_uses_smtp_starttls(self, mock_smtp):
        """Port 587 connects via SMTP + STARTTLS."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        success, msg = check_smtp_connection("smtp.gmail.com", 587, "user@gmail.com", "password")

        assert success is True
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
        mock_server.starttls.assert_called_once()

    @patch("web.services.smtp_test.smtplib.SMTP")
    def test_non_standard_port_uses_starttls(self, mock_smtp):
        """Non-465 ports use SMTP + STARTTLS."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        success, _ = check_smtp_connection("smtp.example.com", 2525, "user@ex.com", "pass")

        assert success is True
        mock_server.starttls.assert_called_once()

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_calls_login_with_credentials(self, mock_smtp_ssl):
        """Login is called with the provided sender and password."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        check_smtp_connection("smtp.gmail.com", 465, "me@gmail.com", "my-app-password")

        mock_server.login.assert_called_once_with("me@gmail.com", "my-app-password")


# --- TestAuthenticationErrors ---


class TestAuthenticationErrors:
    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_error_534_suggests_app_password(self, mock_smtp_ssl):
        """SMTP error 534 tells user to create an App Password."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            534, b"5.7.9 Application-specific password required"
        )
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@gmail.com", "wrong")

        assert success is False
        assert "App Password" in msg

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_error_535_suggests_check_credentials(self, mock_smtp_ssl):
        """SMTP error 535 tells user to check email and password."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"5.7.8 Username and Password not accepted"
        )
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@gmail.com", "bad")

        assert success is False
        assert "Authentication failed" in msg

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_other_auth_error_includes_code(self, mock_smtp_ssl):
        """Non-534/535 auth errors include the SMTP code."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            530, b"Authentication required"
        )
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@gmail.com", "x")

        assert success is False
        assert "530" in msg


# --- TestConnectionErrors ---


class TestConnectionErrors:
    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_connect_error(self, mock_smtp_ssl):
        """SMTPConnectError produces a clear message."""
        mock_smtp_ssl.side_effect = smtplib.SMTPConnectError(421, b"Service not available")

        success, msg = check_smtp_connection("bad-host.com", 465, "user@x.com", "pass")

        assert success is False
        assert "Could not connect" in msg

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_timeout(self, mock_smtp_ssl):
        """Socket timeout produces a clear message."""
        mock_smtp_ssl.side_effect = socket.timeout("timed out")

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@x.com", "pass")

        assert success is False
        assert "timed out" in msg.lower()

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_hostname_resolution_failure(self, mock_smtp_ssl):
        """DNS resolution failure produces a clear message."""
        mock_smtp_ssl.side_effect = socket.gaierror("Name or service not known")

        success, msg = check_smtp_connection("nonexistent.host", 465, "user@x.com", "pass")

        assert success is False
        assert "Could not resolve" in msg

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_connection_refused(self, mock_smtp_ssl):
        """Connection refused produces a clear message."""
        mock_smtp_ssl.side_effect = ConnectionRefusedError()

        success, msg = check_smtp_connection("localhost", 465, "user@x.com", "pass")

        assert success is False
        assert "refused" in msg.lower()

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_ssl_error(self, mock_smtp_ssl):
        """SSL error suggests checking port vs protocol mismatch."""
        mock_smtp_ssl.side_effect = ssl.SSLError("SSL handshake failed")

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@x.com", "pass")

        assert success is False
        assert "SSL" in msg

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_unexpected_error_is_caught(self, mock_smtp_ssl):
        """Unexpected exceptions return False with error detail."""
        mock_smtp_ssl.side_effect = OSError("Unexpected network error")

        success, msg = check_smtp_connection("smtp.gmail.com", 465, "user@x.com", "pass")

        assert success is False
        assert "Unexpected network error" in msg


# --- TestReturnTypes ---


class TestReturnTypes:
    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_success_returns_tuple(self, mock_smtp_ssl):
        """Successful test returns (True, str)."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        result = check_smtp_connection("smtp.gmail.com", 465, "u@g.com", "p")

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    @patch("web.services.smtp_test.smtplib.SMTP_SSL")
    def test_failure_returns_tuple(self, mock_smtp_ssl):
        """Failed test returns (False, str)."""
        mock_smtp_ssl.side_effect = socket.timeout()

        result = check_smtp_connection("smtp.gmail.com", 465, "u@g.com", "p")

        assert isinstance(result, tuple)
        assert result[0] is False
        assert isinstance(result[1], str)
        assert len(result[1]) > 0  # message is not empty
