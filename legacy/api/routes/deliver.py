"""POST /deliver — Deliver a built EPUB to the user's device."""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.models import DeliverRequest, DeliverResponse

from paper_boy.config import (
    Config,
    DeliveryConfig,
    EmailConfig,
    FeedConfig,
    GoogleDriveConfig,
    NewspaperConfig,
)
from paper_boy.delivery import deliver

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/deliver", response_model=DeliverResponse)
async def deliver_epub(req: DeliverRequest, _user_id: str = Depends(verify_token)):
    """Deliver a base64-encoded EPUB via the specified method."""
    try:
        # Decode EPUB to temp file
        epub_bytes = base64.b64decode(req.epub_base64)
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp.write(epub_bytes)
            epub_path = Path(tmp.name)

        # Build config
        config = Config(
            newspaper=NewspaperConfig(title=req.title),
            feeds=[FeedConfig(name="", url="")],
            delivery=DeliveryConfig(
                method=req.delivery_method,
                device=req.device,
                google_drive=GoogleDriveConfig(
                    folder_name=req.google_drive_folder,
                ),
                email=EmailConfig(
                    smtp_host=req.email_smtp_host,
                    smtp_port=req.email_smtp_port,
                    sender=req.email_sender,
                    password=req.email_password,
                    recipient=req.kindle_email,
                ),
            ),
        )

        token_data = req.google_tokens

        # Detect Gmail API routing
        effective_method = req.delivery_method
        if effective_method == "email" and token_data:
            scopes = token_data.get("scopes", [])
            if "https://www.googleapis.com/auth/gmail.send" in scopes:
                effective_method = "gmail_api"

        # Override method if routing to Gmail API
        config.delivery.method = effective_method
        deliver(epub_path, config, token_data=token_data)

        # Clean up temp file
        epub_path.unlink(missing_ok=True)

        # Generate success message
        if effective_method == "google_drive":
            message = f"Uploaded to Google Drive ({config.delivery.google_drive.folder_name})"
        elif effective_method == "gmail_api":
            message = f"Sent to {config.delivery.email.recipient} via Gmail"
        elif effective_method == "email":
            message = f"Emailed to {config.delivery.email.recipient}"
        elif effective_method == "local":
            message = "Download ready"
        else:
            message = "Delivered"

        return DeliverResponse(success=True, message=message)

    except Exception as e:
        logger.exception("Delivery failed")
        return DeliverResponse(success=False, message="Delivery failed. Please check your delivery settings and try again.")
