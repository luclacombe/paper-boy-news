"""Feed catalog service — loads and queries the curated RSS feed list."""

import os
from functools import lru_cache

import yaml


CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "feed_catalog.yaml")


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    """Load the feed catalog from YAML."""
    with open(CATALOG_PATH) as f:
        return yaml.safe_load(f)


def get_bundles() -> list[dict]:
    """Get all starter bundles.

    Returns a list of dicts with keys: name, description, feeds (list of feed IDs).
    """
    return _load_catalog()["bundles"]


def get_categories() -> list[dict]:
    """Get all feed categories with their feeds.

    Returns a list of dicts with keys: name, feeds (list of feed dicts).
    Each feed dict has: id, name, url, description.
    """
    return _load_catalog()["categories"]


def get_all_feeds() -> dict[str, dict]:
    """Get a flat dict of all feeds, keyed by feed ID.

    Returns: {"guardian-world": {"id": "guardian-world", "name": "The Guardian", ...}, ...}
    """
    feeds = {}
    for category in get_categories():
        for feed in category["feeds"]:
            feeds[feed["id"]] = feed
    return feeds


def get_feeds_for_bundle(bundle_name: str) -> list[dict]:
    """Get the full feed details for a given bundle name.

    Returns a list of feed dicts (id, name, url, description).
    """
    all_feeds = get_all_feeds()
    for bundle in get_bundles():
        if bundle["name"] == bundle_name:
            return [all_feeds[fid] for fid in bundle["feeds"] if fid in all_feeds]
    return []


def describe_feed_selection(feed_urls: set[str]) -> str:
    """Describe a feed selection as bundles + extras.

    Examples:
        "Morning Briefing"
        "Morning Briefing + 3 extra sources"
        "Morning Briefing and Tech & Science"
        "Morning Briefing, Tech & Science, and Business & Finance + 1 extra source"
        "15 sources"  (no complete bundles matched)
    """
    matched_bundles = []
    covered_urls: set[str] = set()
    for bundle in get_bundles():
        bundle_feeds = get_feeds_for_bundle(bundle["name"])
        if bundle_feeds and all(f["url"] in feed_urls for f in bundle_feeds):
            matched_bundles.append(bundle["name"])
            for f in bundle_feeds:
                covered_urls.add(f["url"])

    extra_count = len(feed_urls - covered_urls)

    if not matched_bundles:
        count = len(feed_urls)
        return f"{count} source{'s' if count != 1 else ''}"

    if len(matched_bundles) == 1:
        bundle_text = matched_bundles[0]
    elif len(matched_bundles) == 2:
        bundle_text = f"{matched_bundles[0]} and {matched_bundles[1]}"
    else:
        bundle_text = ", ".join(matched_bundles[:-1]) + f", and {matched_bundles[-1]}"

    if extra_count > 0:
        return f"{bundle_text} + {extra_count} extra source{'s' if extra_count != 1 else ''}"
    return bundle_text


def validate_rss_url(url: str) -> bool:
    """Basic validation of an RSS feed URL."""
    if not url:
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False
    if "." not in url:
        return False
    return True
