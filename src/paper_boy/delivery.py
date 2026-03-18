"""Delivery backends — upload generated EPUB to cloud storage."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_boy.config import Config

logger = logging.getLogger(__name__)


def deliver(
    epub_path: Path,
    config: Config,
    *,
    token_data: dict | None = None,
    article_count: int = 0,
    source_count: int = 0,
) -> None:
    """Deliver the generated EPUB using the configured method.

    Args:
        epub_path: Path to the EPUB file.
        config: Paper Boy configuration.
        token_data: Optional Google OAuth2 token data (from web app).
        article_count: Number of articles in the edition (for email template).
        source_count: Number of sources in the edition (for email template).
    """
    method = config.delivery.method

    if method == "google_drive":
        deliver_google_drive(epub_path, config, token_data=token_data)
    elif method == "email":
        deliver_resend(epub_path, config, article_count=article_count, source_count=source_count)
    elif method == "local":
        logger.info("Local delivery: file at %s", epub_path)
    else:
        raise ValueError(f"Unknown delivery method: {method}")


def deliver_google_drive(
    epub_path: Path, config: Config, *, token_data: dict | None = None
) -> None:
    """Upload EPUB to Google Drive folder.

    Uses OAuth2 user tokens if provided, otherwise falls back to service account.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise RuntimeError(
            "Google Drive libraries not installed. "
            "Install with: pip install google-api-python-client google-auth-oauthlib"
        )

    creds = _get_google_credentials(config, token_data=token_data)
    service = build("drive", "v3", credentials=creds)

    # Find or create the target folder
    folder_name = config.delivery.google_drive.folder_name
    folder_id = _find_or_create_folder(service, folder_name)

    # Upload the EPUB
    file_metadata = {
        "name": epub_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(
        str(epub_path),
        mimetype="application/epub+zip",
        resumable=True,
    )

    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id,name"
    ).execute()

    logger.info(
        "Uploaded %s to Google Drive folder '%s' (id: %s)",
        uploaded["name"],
        folder_name,
        uploaded["id"],
    )

    # Clean up old issues
    _cleanup_old_issues(service, folder_id, config.delivery.keep_days)


def deliver_resend(
    epub_path: Path, config: Config, *, article_count: int = 0, source_count: int = 0
) -> None:
    """Send EPUB via Resend email API."""
    import re

    import resend

    from paper_boy.email_template import render_delivery_email

    email_cfg = config.delivery.email
    if not email_cfg.recipient:
        raise ValueError(
            "Email delivery requires a recipient email address. "
            "Configure this in your delivery settings."
        )

    # Defense-in-depth: validate email format even though the web app validates too
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email_cfg.recipient):
        raise ValueError(f"Invalid recipient email address: {email_cfg.recipient}")

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY environment variable is not set.")

    resend.api_key = api_key

    # Build edition date from filename (e.g. "Morning-Digest-2026-03-18.epub")
    stem = epub_path.stem
    date_part = "-".join(stem.rsplit("-", 3)[-3:])  # "2026-03-18"
    try:
        from datetime import datetime as dt

        edition_date = dt.strptime(date_part, "%Y-%m-%d").strftime("%B %-d, %Y")
    except (ValueError, IndexError):
        edition_date = date_part

    title = config.newspaper.title
    html = render_delivery_email(
        title=title,
        edition_date=edition_date,
        article_count=article_count,
        source_count=source_count,
    )

    with open(epub_path, "rb") as f:
        epub_bytes = f.read()

    params: resend.Emails.SendParams = {
        "from": "Paper Boy News <delivery@paper-boy-news.com>",
        "to": [email_cfg.recipient],
        "subject": f"{title} — {edition_date}",
        "html": html,
        "attachments": [
            {
                "filename": epub_path.name,
                "content": list(epub_bytes),
            }
        ],
    }

    resend.Emails.send(params)

    logger.info(
        "Sent %s to %s via Resend",
        epub_path.name,
        email_cfg.recipient,
    )


def _get_google_credentials(config: Config, *, token_data: dict | None = None):
    """Get Google credentials from OAuth2 tokens, env var, or file.

    Tries in order:
    1. OAuth2 user tokens (from web app)
    2. GOOGLE_CREDENTIALS environment variable (service account, for CI)
    3. credentials.json file (service account, for local dev)
    """
    scopes = [
        "https://www.googleapis.com/auth/drive.file",
    ]

    # Path 1: OAuth2 user credentials (from web app)
    if token_data and token_data.get("refresh_token"):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data["refresh_token"],
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=token_data.get("scopes", scopes),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data["token"] = creds.token
            token_data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
            logger.info("Refreshed OAuth2 access token")
        return creds

    # Path 2: Service account from environment variable (GitHub Actions)
    from google.oauth2 import service_account

    env_creds = os.environ.get("GOOGLE_CREDENTIALS")
    if env_creds:
        info = json.loads(env_creds)
        return service_account.Credentials.from_service_account_info(
            info, scopes=scopes
        )

    # Path 3: Service account credentials file
    creds_path = Path(config.delivery.google_drive.credentials_file)
    if creds_path.exists():
        return service_account.Credentials.from_service_account_file(
            str(creds_path), scopes=scopes
        )

    raise FileNotFoundError(
        "Google credentials not found. Connect your Google account in settings, "
        "set GOOGLE_CREDENTIALS env var, or provide a credentials file."
    )


def _find_or_create_folder(service, folder_name: str) -> str:
    """Find an existing folder by name, or create it."""
    safe_name = folder_name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get("files", [])

    if folders:
        folder_id = folders[0]["id"]
        logger.debug("Found existing folder '%s' (id: %s)", folder_name, folder_id)
        return folder_id

    # Create the folder
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=folder_metadata, fields="id").execute()
    folder_id = folder["id"]
    logger.info("Created folder '%s' (id: %s)", folder_name, folder_id)
    return folder_id


def _cleanup_old_issues(service, folder_id: str, keep_days: int) -> None:
    """Remove Paper Boy EPUBs older than keep_days from the folder."""
    if keep_days <= 0:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")

    query = (
        f"'{folder_id}' in parents "
        f"and mimeType = 'application/epub+zip' "
        f"and createdTime < '{cutoff_str}' "
        f"and trashed = false"
    )

    results = service.files().list(q=query, fields="files(id, name)").execute()
    old_files = results.get("files", [])

    for f in old_files:
        service.files().delete(fileId=f["id"]).execute()
        logger.info("Cleaned up old issue: %s", f["name"])

    if old_files:
        logger.info("Removed %d old issue(s)", len(old_files))
