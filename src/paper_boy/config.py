"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FeedConfig:
    name: str
    url: str
    category: str = ""
    articles_per_day: float = 0.0      # from feed_stats, 0 = unknown
    estimated_read_min: float = 0.0    # from feed_stats, 0 = unknown


@dataclass
class GoogleDriveConfig:
    folder_name: str = "Rakuten Kobo"
    credentials_file: str = "credentials.json"


@dataclass
class EmailConfig:
    recipient: str = ""


@dataclass
class DeliveryConfig:
    method: str = "local"
    device: str = "kobo"
    google_drive: GoogleDriveConfig = field(default_factory=GoogleDriveConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    keep_days: int = 30


@dataclass
class NewspaperConfig:
    title: str = "Morning Digest"
    language: str = "en"
    total_article_budget: int = 7
    reading_time_minutes: int = 0  # 0 = use total_article_budget instead
    include_images: bool = True
    image_max_width: int = 800
    image_max_height: int = 1200
    image_quality: int = 80
    image_min_dimension: int = 100


@dataclass
class Config:
    newspaper: NewspaperConfig
    feeds: list[FeedConfig]
    delivery: DeliveryConfig


def load_config(path: str | Path) -> Config:
    """Load and validate configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Config file is empty")

    # Parse newspaper section
    np_raw = raw.get("newspaper", {})
    newspaper = NewspaperConfig(
        title=np_raw.get("title", "Morning Digest"),
        language=np_raw.get("language", "en"),
        total_article_budget=np_raw.get(
            "total_article_budget",
            np_raw.get("max_articles_per_feed", 7),
        ),
        reading_time_minutes=np_raw.get("reading_time_minutes", 0),
        include_images=np_raw.get("include_images", True),
        image_max_width=np_raw.get("image_max_width", 800),
        image_max_height=np_raw.get("image_max_height", 1200),
        image_quality=np_raw.get("image_quality", 80),
        image_min_dimension=np_raw.get("image_min_dimension", 100),
    )

    # Parse feeds
    feeds_raw = raw.get("feeds", [])
    if not feeds_raw:
        raise ValueError("No feeds configured")
    feeds = [
        FeedConfig(
            name=f["name"],
            url=f["url"],
            category=f.get("category", ""),
            articles_per_day=float(f.get("articles_per_day", 0.0)),
            estimated_read_min=float(f.get("estimated_read_min", 0.0)),
        )
        for f in feeds_raw
    ]

    # Parse delivery
    del_raw = raw.get("delivery", {})
    gd_raw = del_raw.get("google_drive", {})
    google_drive = GoogleDriveConfig(
        folder_name=gd_raw.get("folder_name", "Rakuten Kobo"),
        credentials_file=gd_raw.get("credentials_file", "credentials.json"),
    )
    email_raw = del_raw.get("email", {})
    email_config = EmailConfig(
        recipient=email_raw.get("recipient", ""),
    )
    delivery = DeliveryConfig(
        method=del_raw.get("method", "local"),
        device=del_raw.get("device", "kobo"),
        google_drive=google_drive,
        email=email_config,
        keep_days=del_raw.get("keep_days", 30),
    )

    return Config(newspaper=newspaper, feeds=feeds, delivery=delivery)
