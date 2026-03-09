"""Tests for config loading."""

import tempfile
from pathlib import Path

import pytest

from paper_boy.config import load_config


def _write_config(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_load_valid_config():
    path = _write_config("""
newspaper:
  title: "Test Paper"
  language: "en"
  total_article_budget: 5

feeds:
  - name: "Tech"
    url: "https://example.com/rss"

delivery:
  method: "local"
""")
    config = load_config(path)
    assert config.newspaper.title == "Test Paper"
    assert config.newspaper.total_article_budget == 5
    assert len(config.feeds) == 1
    assert config.feeds[0].name == "Tech"
    assert config.delivery.method == "local"


def test_load_config_defaults():
    path = _write_config("""
feeds:
  - name: "News"
    url: "https://example.com/rss"
""")
    config = load_config(path)
    assert config.newspaper.title == "Morning Digest"
    assert config.newspaper.language == "en"
    assert config.delivery.method == "local"
    assert config.delivery.keep_days == 30


def test_load_config_no_feeds():
    path = _write_config("""
newspaper:
  title: "Test"
""")
    with pytest.raises(ValueError, match="No feeds configured"):
        load_config(path)


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_load_config_empty():
    path = _write_config("")
    with pytest.raises(ValueError, match="empty"):
        load_config(path)
