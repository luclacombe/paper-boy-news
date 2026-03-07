"""POST /build — Build a newspaper EPUB from feeds."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from datetime import date

from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.models import BuildRequest, BuildResponse

from paper_boy.config import (
    Config,
    DeliveryConfig,
    EmailConfig,
    FeedConfig,
    GoogleDriveConfig,
    NewspaperConfig,
)
from paper_boy.main import build_newspaper

logger = logging.getLogger(__name__)
router = APIRouter()


def _config_from_request(req: BuildRequest) -> Config:
    """Construct a paper_boy Config from API request."""
    feeds = [FeedConfig(name=f.name, url=f.url) for f in req.feeds]

    newspaper = NewspaperConfig(
        title=req.title,
        language=req.language,
        max_articles_per_feed=req.max_articles_per_feed,
        include_images=req.include_images,
    )

    delivery = DeliveryConfig(
        method="local",
        device=req.device,
        google_drive=GoogleDriveConfig(),
        email=EmailConfig(),
    )

    return Config(newspaper=newspaper, feeds=feeds, delivery=delivery)


@router.post("/build", response_model=BuildResponse)
async def build(req: BuildRequest, _user_id: str = Depends(verify_token)):
    """Build a newspaper and return base64-encoded EPUB."""
    try:
        if not req.feeds:
            return BuildResponse(success=False, error="No feeds provided")

        config = _config_from_request(req)

        with tempfile.TemporaryDirectory(prefix="paperboy_") as tmp_dir:
            issue_date = (
                date.fromisoformat(req.edition_date)
                if req.edition_date
                else date.today()
            )
            output_path = os.path.join(
                tmp_dir, f"paper-boy-{issue_date.isoformat()}.epub"
            )

            result = build_newspaper(config, output_path=output_path, issue_date=issue_date)

            # Read and base64-encode the EPUB
            with open(result.epub_path, "rb") as f:
                epub_bytes = f.read()
            epub_base64 = base64.b64encode(epub_bytes).decode()

            # Extract section/headline metadata
            sections = [
                {
                    "name": s.name,
                    "headlines": [a.title for a in s.articles[:5]],
                }
                for s in result.sections
            ]

            # Compute file size
            file_size_bytes = len(epub_bytes)
            if file_size_bytes >= 1_048_576:
                file_size = f"{file_size_bytes / 1_048_576:.1f} MB"
            else:
                file_size = f"{file_size_bytes / 1024:.0f} KB"

            return BuildResponse(
                success=True,
                epub_base64=epub_base64,
                total_articles=result.total_articles,
                sections=sections,
                file_size=file_size,
                file_size_bytes=file_size_bytes,
            )
    except Exception as e:
        logger.exception("Build failed")
        return BuildResponse(success=False, error=str(e))
