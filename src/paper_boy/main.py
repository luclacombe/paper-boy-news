"""Main orchestration — fetch, build, deliver."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List

from paper_boy.cache import ContentCache
from paper_boy.config import Config
from paper_boy.delivery import deliver
from paper_boy.epub import build_epub
from paper_boy.feeds import FeedObservation, Section, fetch_feeds, get_feed_observations

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a newspaper build, including the fetched content."""

    epub_path: Path
    sections: List[Section]
    total_articles: int
    feed_observations: List[FeedObservation] = field(default_factory=list)


def build_newspaper(
    config: Config,
    output_path: str | Path | None = None,
    issue_date: date | None = None,
    cache: ContentCache | None = None,
) -> BuildResult:
    """Fetch feeds and build the newspaper EPUB.

    Returns a BuildResult with the EPUB path and fetched sections.
    """
    if issue_date is None:
        issue_date = date.today()

    logger.info("Building %s for %s", config.newspaper.title, issue_date)

    # Fetch all feeds
    logger.info("Fetching %d feed(s)...", len(config.feeds))
    sections = fetch_feeds(config, cache=cache)

    total_articles = sum(len(s.articles) for s in sections)
    if total_articles == 0:
        raise RuntimeError("No articles were extracted from any feed")

    logger.info(
        "Extracted %d articles across %d sections",
        total_articles,
        len(sections),
    )

    # Build EPUB
    epub_path = build_epub(sections, config, issue_date, output_path)
    logger.info("Built EPUB: %s", epub_path)

    return BuildResult(
        epub_path=epub_path,
        sections=sections,
        total_articles=total_articles,
        feed_observations=get_feed_observations(),
    )


def build_and_deliver(
    config: Config,
    output_path: str | Path | None = None,
    issue_date: date | None = None,
    cache: ContentCache | None = None,
) -> BuildResult:
    """Build the newspaper and deliver it."""
    result = build_newspaper(config, output_path, issue_date, cache=cache)

    # Deliver
    deliver(
        result.epub_path, config,
        article_count=result.total_articles,
        source_count=len(result.sections),
    )

    return result
