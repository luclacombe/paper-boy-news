"""User config persistence service.

Phase 1: Backed by st.session_state (ephemeral).
Phase 1.5: Will be replaced with Supabase calls.
"""

import json
import os
from datetime import datetime
from typing import Optional

import streamlit as st


# Default config for new users
DEFAULT_CONFIG = {
    "title": "Morning Digest",
    "feeds": [],
    "device": "kobo",
    "delivery_method": "local",
    "google_drive_folder": "Rakuten Kobo",
    "google_tokens": None,
    "kindle_email": "",
    "email_method": "gmail",
    "email_smtp_host": "smtp.gmail.com",
    "email_smtp_port": 465,
    "email_sender": "",
    "email_password": "",
    "max_articles_per_feed": 10,
    "reading_time": "20 min",
    "include_images": True,
    "delivery_time": "06:00",
    "timezone": "UTC",
    "language": "en",
}

# Path for optional local persistence
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "user_config.json")


def _ensure_session_state():
    """Initialize session state with default config if not present."""
    if "user_config" not in st.session_state:
        # Try loading from local file
        config = _load_from_file()
        if config:
            st.session_state["user_config"] = config
        else:
            st.session_state["user_config"] = DEFAULT_CONFIG.copy()

    if "delivery_history" not in st.session_state:
        st.session_state["delivery_history"] = _load_history_from_file()

    if "onboarding_complete" not in st.session_state:
        config = st.session_state["user_config"]
        st.session_state["onboarding_complete"] = len(config.get("feeds", [])) > 0


def get_user_config() -> dict:
    """Get the current user's configuration."""
    _ensure_session_state()
    return st.session_state["user_config"]


def save_user_config(config: dict):
    """Save the user's configuration."""
    _ensure_session_state()
    st.session_state["user_config"] = config
    st.session_state["onboarding_complete"] = len(config.get("feeds", [])) > 0
    _save_to_file(config)


def update_user_config(**kwargs):
    """Update specific fields in the user's configuration."""
    _ensure_session_state()
    config = st.session_state["user_config"]
    config.update(kwargs)
    save_user_config(config)


def get_feeds() -> list[dict]:
    """Get the user's configured feeds."""
    return get_user_config().get("feeds", [])


def set_feeds(feeds: list[dict]):
    """Set the user's configured feeds."""
    update_user_config(feeds=feeds)


def add_feed(name: str, url: str, category: str = "Custom"):
    """Add a feed to the user's configuration."""
    feeds = get_feeds()
    # Avoid duplicates by URL
    if any(f["url"] == url for f in feeds):
        return
    feeds.append({"name": name, "url": url, "category": category})
    set_feeds(feeds)


def remove_feed(url: str):
    """Remove a feed by URL."""
    feeds = [f for f in get_feeds() if f["url"] != url]
    set_feeds(feeds)


def is_onboarding_complete() -> bool:
    """Check if the user has completed onboarding."""
    _ensure_session_state()
    return st.session_state.get("onboarding_complete", False)


def complete_onboarding():
    """Mark onboarding as complete."""
    st.session_state["onboarding_complete"] = True


def get_delivery_history() -> list[dict]:
    """Get the user's delivery history."""
    _ensure_session_state()
    return st.session_state.get("delivery_history", [])


def add_delivery_record(record: dict):
    """Add a delivery record to history."""
    _ensure_session_state()
    history = st.session_state.get("delivery_history", [])
    history.insert(0, record)  # Most recent first
    # Keep last 30 records
    st.session_state["delivery_history"] = history[:30]
    _save_history_to_file(st.session_state["delivery_history"])


# === Local file persistence (optional, for dev) ===

def _load_from_file() -> Optional[dict]:
    """Try to load config from a local JSON file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_to_file(config: dict):
    """Save config to a local JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        pass


HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "delivery_history.json")


def _load_history_from_file() -> list[dict]:
    """Try to load delivery history from a local JSON file."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_history_to_file(history: list[dict]):
    """Save delivery history to a local JSON file."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass
