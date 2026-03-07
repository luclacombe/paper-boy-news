"""Send emails via the Gmail API (OAuth2-based, no App Password needed)."""

from __future__ import annotations

import base64
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def send_via_gmail(
    epub_path: Path | str,
    recipient: str,
    subject: str,
    credentials: Credentials,
) -> None:
    """Send an EPUB file as an email attachment via the Gmail API.

    Args:
        epub_path: Path to the EPUB file.
        recipient: Recipient email address (e.g. Kindle address).
        subject: Email subject line.
        credentials: Google OAuth2 credentials with gmail.send scope.
    """
    epub_path = Path(epub_path)

    msg = MIMEMultipart()
    msg["To"] = recipient
    msg["Subject"] = subject

    part = MIMEBase("application", "epub+zip")
    with open(epub_path, "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{epub_path.name}"',
    )
    msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = build("gmail", "v1", credentials=credentials)
    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    logger.info("Sent %s to %s via Gmail API", epub_path.name, recipient)
