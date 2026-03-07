"""POST /feeds/validate — Validate an RSS feed URL."""

from __future__ import annotations

import logging

import feedparser
from fastapi import APIRouter, Depends

from api.auth import verify_token
from api.models import FeedValidateRequest, FeedValidateResponse
from paper_boy.url_validation import is_safe_url

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/feeds/validate", response_model=FeedValidateResponse)
async def validate_feed(req: FeedValidateRequest, _user_id: str = Depends(verify_token)):
    """Parse an RSS/Atom feed URL and check if it's valid."""
    if not is_safe_url(req.url):
        return FeedValidateResponse(valid=False, error="URL not allowed: only public HTTP/HTTPS URLs are accepted")

    try:
        feed = feedparser.parse(req.url)

        if feed.bozo and not feed.entries:
            error_msg = str(feed.bozo_exception) if feed.bozo_exception else "Invalid RSS feed"
            return FeedValidateResponse(valid=False, error=error_msg)

        if not feed.entries:
            return FeedValidateResponse(valid=False, error="No articles found in feed")

        name = feed.feed.get("title", "") if hasattr(feed, "feed") else ""
        return FeedValidateResponse(valid=True, name=name or None)

    except Exception as e:
        logger.exception("Feed validation failed for URL: %s", req.url)
        return FeedValidateResponse(valid=False, error="Could not validate this feed URL. Please check the URL and try again.")
