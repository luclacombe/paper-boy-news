"""Seed feed_stats table with feed observation data.

Two modes:
  1. RSS scan (default): Fetches each catalog RSS feed, counts entries and
     freshness. Fast but no extraction stats (word counts, images).
  2. From build (--from-build): Reads feed observations saved by a local
     `paper-boy build` run. Full extraction stats including real word counts,
     extraction rates, and image counts.

Usage:
  python scripts/seed_feed_stats.py                 # RSS scan only
  python scripts/seed_feed_stats.py --from-build    # From local build data

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.
"""

from __future__ import annotations

import calendar
import json
import logging
import os
import signal
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from supabase import create_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "web" / "src" / "data" / "feed-catalog.yaml"
OBSERVATIONS_PATH = Path(__file__).resolve().parent.parent / "audit" / "feed-observations.json"
FEED_TIMEOUT = 30
READING_WPM = 238

# Domain-specific feeds that don't use standard RSS
SKIP_DOMAINS = {"bloomberg.com", "reuters.com", "scientificamerican.com", "ft.com", "businessoffashion.com"}


def entry_age_hours(entry) -> float | None:
    """Return entry age in hours, or None if no date."""
    date_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
    if not date_tuple:
        return None
    try:
        entry_ts = calendar.timegm(date_tuple[:9])
        return (time.time() - entry_ts) / 3600
    except (TypeError, OverflowError, ValueError):
        return None


def scan_feed(url: str, name: str) -> dict | None:
    """Fetch a single RSS feed and compute entry-level stats."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc
    if any(skip in domain for skip in SKIP_DOMAINS):
        logger.info("Skipping domain-specific feed: %s (%s)", name, domain)
        return None

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Feed fetch timed out after {FEED_TIMEOUT}s")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(FEED_TIMEOUT)
    try:
        feed = feedparser.parse(url)
    except TimeoutError:
        logger.warning("Timeout fetching %s", name)
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if feed.bozo and not feed.entries:
        logger.warning("Failed to parse %s: %s", name, feed.bozo_exception)
        return None

    entries = feed.entries[:20]  # Match _FETCH_CAP_PER_FEED
    total = len(entries)

    fresh_24h = 0
    fresh_48h = 0
    for e in entries:
        age = entry_age_hours(e)
        if age is not None:
            if age <= 24:
                fresh_24h += 1
            if age <= 48:
                fresh_48h += 1
        else:
            fresh_24h += 1
            fresh_48h += 1

    # Estimate per-article read time from RSS content length (rough proxy)
    # Real word counts come from extraction during actual builds
    avg_word_count = 800.0  # Conservative default for news articles
    estimated_read_min = avg_word_count / READING_WPM
    articles_per_day = float(fresh_24h)
    daily_read_min = articles_per_day * estimated_read_min

    today = date.today().isoformat()
    history = [{
        "date": today,
        "fresh_24h": fresh_24h,
        "extracted": 0,  # No extraction in seed
        "avg_words": 0,
    }]

    return {
        "url": url,
        "name": name,
        "observed_at": datetime.now(ZoneInfo("UTC")).isoformat(),
        "sample_count": 1,
        "total_entries": total,
        "fresh_24h": fresh_24h,
        "fresh_48h": fresh_48h,
        "attempted": 0,
        "extracted": 0,
        "avg_word_count": 0,
        "median_word_count": 0,
        "avg_images": 0,
        "articles_per_day": round(articles_per_day, 2),
        "estimated_read_min": round(estimated_read_min, 2),
        "daily_read_min": round(daily_read_min, 2),
        "history": history,
    }


def observation_to_row(obs: dict) -> dict:
    """Convert a FeedObservation dict (from JSON) to a feed_stats upsert row."""
    today = date.today().isoformat()
    median_wc = obs.get("median_word_count", 0)
    estimated_read_min = median_wc / READING_WPM if median_wc > 0 else 0.0
    articles_per_day = float(obs.get("fresh_24h", 0))
    daily_read_min = articles_per_day * estimated_read_min

    history = [{
        "date": today,
        "fresh_24h": obs.get("fresh_24h", 0),
        "extracted": obs.get("extracted", 0),
        "avg_words": obs.get("avg_word_count", 0),
    }]

    return {
        "url": obs["feed_url"],
        "name": obs["feed_name"],
        "observed_at": datetime.now(ZoneInfo("UTC")).isoformat(),
        "sample_count": 1,
        "total_entries": obs.get("total_entries", 0),
        "fresh_24h": obs.get("fresh_24h", 0),
        "fresh_48h": obs.get("fresh_48h", 0),
        "attempted": obs.get("attempted", 0),
        "extracted": obs.get("extracted", 0),
        "avg_word_count": obs.get("avg_word_count", 0),
        "median_word_count": median_wc,
        "avg_images": obs.get("avg_images", 0),
        "articles_per_day": round(articles_per_day, 2),
        "estimated_read_min": round(estimated_read_min, 2),
        "daily_read_min": round(daily_read_min, 2),
        "history": history,
    }


def upsert_with_history(sb, row: dict) -> None:
    """Upsert a row into feed_stats, merging with existing history."""
    existing = (
        sb.table("feed_stats")
        .select("sample_count, history")
        .eq("url", row["url"])
        .limit(1)
        .execute()
    )

    if existing.data:
        old = existing.data[0]
        row["sample_count"] = old["sample_count"] + 1
        history = old.get("history") or []

        today_entry = row["history"][0]
        # Update or append today's entry
        updated = False
        for i, h in enumerate(history):
            if h.get("date") == today_entry["date"]:
                history[i] = today_entry
                updated = True
                break
        if not updated:
            history.append(today_entry)

        # Prune > 30 days
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        history = [h for h in history if h.get("date", "") >= cutoff]

        row["history"] = history

        # Recompute rolling averages from full history
        if history:
            fresh_values = [h.get("fresh_24h", 0) for h in history]
            row["articles_per_day"] = round(
                sum(fresh_values) / len(fresh_values), 2
            )
            row["daily_read_min"] = round(
                row["articles_per_day"] * row["estimated_read_min"], 2
            )

    sb.table("feed_stats").upsert(row, on_conflict="url").execute()


def run_scan(sb) -> None:
    """Mode 1: RSS scan of all catalog feeds."""
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)

    feeds: list[tuple[str, str]] = []
    for category in catalog.get("categories", []):
        for feed in category.get("feeds", []):
            feeds.append((feed["url"], feed["name"]))

    logger.info("Scanning %d catalog feeds...", len(feeds))

    upserted = 0
    for url, name in feeds:
        row = scan_feed(url, name)
        if row:
            upsert_with_history(sb, row)
            logger.info(
                "  %s: %d entries, %d fresh (24h), ~%.1f min/day",
                name, row["total_entries"], row["fresh_24h"], row["daily_read_min"],
            )
            upserted += 1

    logger.info("Seeded feed stats for %d/%d feeds", upserted, len(feeds))


def run_from_build(sb) -> None:
    """Mode 2: Push observations from a local build."""
    if not OBSERVATIONS_PATH.exists():
        logger.error(
            "No observations file found at %s\n"
            "Run 'paper-boy build' first to generate observations.",
            OBSERVATIONS_PATH,
        )
        sys.exit(1)

    with open(OBSERVATIONS_PATH) as f:
        observations = json.load(f)

    logger.info(
        "Loading %d feed observations from %s",
        len(observations), OBSERVATIONS_PATH,
    )

    upserted = 0
    for obs in observations:
        row = observation_to_row(obs)
        upsert_with_history(sb, row)
        logger.info(
            "  %s: %d extracted, avg %d words, median %d words, ~%.1f min/day",
            obs["feed_name"],
            obs.get("extracted", 0),
            obs.get("avg_word_count", 0),
            obs.get("median_word_count", 0),
            row["daily_read_min"],
        )
        upserted += 1

    logger.info("Pushed feed stats for %d feeds from build data", upserted)


def main():
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not sb_url or not sb_key:
        logger.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sb = create_client(sb_url, sb_key)

    if "--from-build" in sys.argv:
        run_from_build(sb)
    else:
        run_scan(sb)


if __name__ == "__main__":
    main()
