"""Shared fixtures and helpers for the Paper Boy test suite."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from paper_boy.config import (
    Config,
    DeliveryConfig,
    EmailConfig,
    FeedConfig,
    GoogleDriveConfig,
    NewspaperConfig,
)
from paper_boy.feeds import Article, Section


# --- Image helper ---


def _make_test_image(width: int = 400, height: int = 300, color: str = "red") -> bytes:
    """Create an in-memory JPEG image and return its bytes."""
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- Config factories ---


@pytest.fixture
def make_config():
    """Factory fixture that returns a function to build Config objects."""

    def _make(
        title="Test Digest",
        language="en",
        max_articles_per_feed=10,
        include_images=True,
        image_max_width=800,
        image_max_height=1200,
        image_quality=80,
        image_min_dimension=100,
        method="local",
        device="kobo",
        folder_name="Rakuten Kobo",
        credentials_file="credentials.json",
        keep_days=30,
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        sender="",
        password="",
        recipient="",
        feeds=None,
    ) -> Config:
        if feeds is None:
            feeds = [
                FeedConfig(name="Test Feed", url="https://example.com/rss"),
            ]
        return Config(
            newspaper=NewspaperConfig(
                title=title,
                language=language,
                max_articles_per_feed=max_articles_per_feed,
                include_images=include_images,
                image_max_width=image_max_width,
                image_max_height=image_max_height,
                image_quality=image_quality,
                image_min_dimension=image_min_dimension,
            ),
            feeds=feeds,
            delivery=DeliveryConfig(
                method=method,
                device=device,
                google_drive=GoogleDriveConfig(
                    folder_name=folder_name,
                    credentials_file=credentials_file,
                ),
                email=EmailConfig(
                    smtp_host=smtp_host,
                    smtp_port=smtp_port,
                    sender=sender,
                    password=password,
                    recipient=recipient,
                ),
                keep_days=keep_days,
            ),
        )

    return _make


@pytest.fixture
def local_config(make_config):
    """Pre-built Config with local delivery."""
    return make_config()


@pytest.fixture
def email_config(make_config):
    """Pre-built Config with email delivery and credentials."""
    return make_config(
        method="email",
        sender="me@gmail.com",
        password="app-secret",
        recipient="kindle@kindle.com",
    )


@pytest.fixture
def gdrive_config(make_config):
    """Pre-built Config with Google Drive delivery."""
    return make_config(method="google_drive")


# --- Data model factories ---


@pytest.fixture
def make_article():
    """Factory fixture that returns a function to build Article objects."""

    def _make(
        title="Test Article",
        url="https://example.com/article/1",
        author=None,
        date=None,
        html_content="<p>Test content.</p>",
        images=None,
    ) -> Article:
        return Article(
            title=title,
            url=url,
            author=author,
            date=date,
            html_content=html_content,
            images=images if images is not None else [],
        )

    return _make


@pytest.fixture
def make_section(make_article):
    """Factory fixture that returns a function to build Section objects."""

    def _make(name="World News", num_articles=2) -> Section:
        articles = [
            make_article(
                title=f"Article {i + 1}",
                url=f"https://example.com/article/{i + 1}",
            )
            for i in range(num_articles)
        ]
        return Section(name=name, articles=articles)

    return _make


@pytest.fixture
def make_sections(make_section):
    """Factory fixture that returns a function to build a list of Section objects."""

    def _make(num_sections=2, articles_per_section=2) -> list[Section]:
        names = ["World News", "Technology", "Science", "Business", "Opinion"]
        return [
            make_section(
                name=names[i % len(names)],
                num_articles=articles_per_section,
            )
            for i in range(num_sections)
        ]

    return _make


# --- Web app fixtures ---


@pytest.fixture
def sample_user_config():
    """A fully populated user config dict as used by the web app."""
    return {
        "title": "Morning Digest",
        "feeds": [
            {"name": "Tech News", "url": "https://example.com/tech/rss", "category": "Technology"},
            {"name": "World", "url": "https://example.com/world/rss", "category": "World News"},
            {"name": "Science", "url": "https://example.com/science/rss", "category": "Science"},
        ],
        "device": "kobo",
        "delivery_method": "local",
        "google_drive_folder": "Rakuten Kobo",
        "kindle_email": "",
        "email_smtp_host": "smtp.gmail.com",
        "email_smtp_port": 465,
        "email_sender": "",
        "email_password": "",
        "max_articles_per_feed": 10,
        "include_images": True,
        "delivery_time": "06:00",
        "language": "en",
    }
