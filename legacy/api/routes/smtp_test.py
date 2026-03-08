"""POST /smtp-test — Test SMTP credentials without sending an email."""

from __future__ import annotations

import smtplib
import socket
import ssl

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.models import SmtpTestRequest, SmtpTestResponse

router = APIRouter()


@router.post("/smtp-test", response_model=SmtpTestResponse)
async def smtp_test(req: SmtpTestRequest, _user_id: str = Depends(verify_token)):
    """Test SMTP credentials by authenticating without sending."""
    # Block connections to localhost/private IPs (SSRF prevention)
    import ipaddress

    try:
        addr_info = socket.getaddrinfo(req.smtp_host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _, _, _, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return SmtpTestResponse(
                    success=False,
                    message="SMTP host resolves to a private/internal address. Use a public SMTP server.",
                )
    except (socket.gaierror, ValueError, OSError):
        pass  # DNS resolution failed — let smtplib handle the error naturally

    try:
        if req.smtp_port == 465:
            with smtplib.SMTP_SSL(req.smtp_host, req.smtp_port, timeout=10) as server:
                server.login(req.sender, req.password)
        else:
            with smtplib.SMTP(req.smtp_host, req.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(req.sender, req.password)
        return SmtpTestResponse(
            success=True,
            message="Connection successful! Your email credentials are valid.",
        )

    except smtplib.SMTPAuthenticationError as e:
        code = e.smtp_code
        if code == 534:
            return SmtpTestResponse(
                success=False,
                message=(
                    "Gmail requires an App Password. "
                    "Enable 2-Step Verification in your Google Account, "
                    "then create an App Password at myaccount.google.com/apppasswords"
                ),
            )
        if code == 535:
            return SmtpTestResponse(
                success=False,
                message=(
                    "Authentication failed. Check that your email address "
                    "and App Password are correct."
                ),
            )
        msg = (
            e.smtp_error.decode(errors="replace")
            if isinstance(e.smtp_error, bytes)
            else str(e.smtp_error)
        )
        return SmtpTestResponse(success=False, message=f"Authentication error ({code}): {msg}")

    except smtplib.SMTPConnectError:
        return SmtpTestResponse(
            success=False,
            message=f"Could not connect to {req.smtp_host}:{req.smtp_port}. Check the SMTP host and port.",
        )

    except socket.timeout:
        return SmtpTestResponse(
            success=False,
            message=f"Connection to {req.smtp_host}:{req.smtp_port} timed out.",
        )

    except socket.gaierror:
        return SmtpTestResponse(
            success=False,
            message=f"Could not resolve hostname: {req.smtp_host}",
        )

    except ConnectionRefusedError:
        return SmtpTestResponse(
            success=False,
            message=f"Connection refused by {req.smtp_host}:{req.smtp_port}. Check the port number.",
        )

    except ssl.SSLError:
        return SmtpTestResponse(
            success=False,
            message=(
                f"SSL error connecting to {req.smtp_host}:{req.smtp_port}. "
                "Port 465 uses SSL, port 587 uses STARTTLS."
            ),
        )

    except Exception as e:
        return SmtpTestResponse(success=False, message=f"Connection error: {e}")
