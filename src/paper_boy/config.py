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


@dataclass
class GoogleDriveConfig:
    folder_name: str = "Rakuten Kobo"
    credentials_file: str = "credentials.json"


@dataclass
class EmailConfig:
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    sender: str = ""
    password: str = ""
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
    max_articles_per_feed: int = 10
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
        max_articles_per_feed=np_raw.get("max_articles_per_feed", 10),
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
        FeedConfig(name=f["name"], url=f["url"], category=f.get("category", ""))
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
        smtp_host=email_raw.get("smtp_host", "smtp.gmail.com"),
        smtp_port=email_raw.get("smtp_port", 465),
        sender=email_raw.get("sender", ""),
        password=email_raw.get("password", ""),
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
