"""Test SMTP credentials without sending an email."""

from __future__ import annotations

import smtplib
import socket
import ssl


def check_smtp_connection(
    smtp_host: str,
    smtp_port: int,
    sender: str,
    password: str,
    timeout: int = 10,
) -> tuple[bool, str]:
    """Test SMTP credentials by authenticating without sending.

    Returns (success, message) tuple.
    """
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout) as server:
                server.login(sender, password)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                server.starttls()
                server.login(sender, password)
        return True, "Connection successful! Your email credentials are valid."

    except smtplib.SMTPAuthenticationError as e:
        code = e.smtp_code
        if code == 534:
            return False, (
                "Gmail requires an App Password. "
                "Enable 2-Step Verification in your Google Account, "
                "then create an App Password at myaccount.google.com/apppasswords"
            )
        if code == 535:
            return False, (
                "Authentication failed. Check that your email address "
                "and App Password are correct."
            )
        msg = e.smtp_error.decode(errors="replace") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        return False, f"Authentication error ({code}): {msg}"

    except smtplib.SMTPConnectError:
        return False, f"Could not connect to {smtp_host}:{smtp_port}. Check the SMTP host and port."

    except socket.timeout:
        return False, f"Connection to {smtp_host}:{smtp_port} timed out."

    except socket.gaierror:
        return False, f"Could not resolve hostname: {smtp_host}"

    except ConnectionRefusedError:
        return False, f"Connection refused by {smtp_host}:{smtp_port}. Check the port number."

    except ssl.SSLError:
        return False, (
            f"SSL error connecting to {smtp_host}:{smtp_port}. "
            "Port 465 uses SSL, port 587 uses STARTTLS."
        )

    except Exception as e:
        return False, f"Connection error: {e}"
