"""Tests for the web app database (persistence) service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# --- Helpers ---


def _make_mock_st(initial_state=None):
    """Create a mock streamlit module with dict-based session_state."""
    mock_st = MagicMock()
    mock_st.session_state = initial_state if initial_state is not None else {}
    return mock_st


def _sample_feed(name="Tech", url="https://example.com/rss", category="Technology"):
    """Shorthand for a feed dict."""
    return {"name": name, "url": url, "category": category}


# Patch streamlit before importing database module in each test.
# We use a module-level patch context for import.


@pytest.fixture(autouse=True)
def _reset_default_config():
    """Reset DEFAULT_CONFIG between tests to prevent shallow-copy mutation leaks."""
    from web.services.database import DEFAULT_CONFIG

    original_feeds = list(DEFAULT_CONFIG["feeds"])
    DEFAULT_CONFIG["feeds"] = []
    yield
    DEFAULT_CONFIG["feeds"] = original_feeds


class TestSessionStateInit:
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_initializes_default_config(self, mock_st, mock_load, mock_hist):
        """First access creates DEFAULT_CONFIG in session_state."""
        mock_st.session_state = {}
        from web.services.database import DEFAULT_CONFIG, _ensure_session_state

        _ensure_session_state()

        config = mock_st.session_state["user_config"]
        assert config["title"] == DEFAULT_CONFIG["title"]
        assert config["feeds"] == []

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file")
    @patch("web.services.database.st")
    def test_loads_config_from_file_if_exists(self, mock_st, mock_load, mock_hist):
        """_load_from_file result is used when available."""
        mock_st.session_state = {}
        saved_config = {"title": "Saved Paper", "feeds": [_sample_feed()]}
        mock_load.return_value = saved_config

        from web.services.database import _ensure_session_state

        _ensure_session_state()

        assert mock_st.session_state["user_config"]["title"] == "Saved Paper"

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_initializes_delivery_history(self, mock_st, mock_load, mock_hist):
        """delivery_history initialized from file or empty list."""
        mock_st.session_state = {}

        from web.services.database import _ensure_session_state

        _ensure_session_state()

        assert mock_st.session_state["delivery_history"] == []

    @patch("web.services.database._load_history_from_file")
    @patch("web.services.database._load_from_file")
    @patch("web.services.database.st")
    def test_loads_history_from_file(self, mock_st, mock_load, mock_hist):
        """delivery_history loaded from file when available."""
        mock_st.session_state = {}
        mock_load.return_value = None
        records = [{"status": "delivered", "date": "2026-03-01"}]
        mock_hist.return_value = records

        from web.services.database import _ensure_session_state

        _ensure_session_state()

        assert mock_st.session_state["delivery_history"] == records

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file")
    @patch("web.services.database.st")
    def test_sets_onboarding_complete_from_feeds(self, mock_st, mock_load, mock_hist):
        """onboarding_complete is True when feeds is non-empty."""
        mock_st.session_state = {}
        mock_load.return_value = {"title": "Test", "feeds": [_sample_feed()]}

        from web.services.database import _ensure_session_state

        _ensure_session_state()

        assert mock_st.session_state["onboarding_complete"] is True


class TestGetUserConfig:
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_returns_config_dict(self, mock_st, mock_load, mock_hist):
        """Returns the config from session_state."""
        mock_st.session_state = {}

        from web.services.database import get_user_config

        config = get_user_config()
        assert isinstance(config, dict)
        assert "title" in config

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_initializes_on_first_call(self, mock_st, mock_load, mock_hist):
        """Calls _ensure_session_state if not initialized."""
        mock_st.session_state = {}

        from web.services.database import get_user_config

        get_user_config()
        assert "user_config" in mock_st.session_state


class TestSaveUserConfig:
    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_updates_session_state(self, mock_st, mock_load, mock_hist, mock_save):
        """Config is stored in session_state."""
        mock_st.session_state = {}

        from web.services.database import save_user_config

        new_config = {"title": "New Title", "feeds": [_sample_feed()]}
        save_user_config(new_config)

        assert mock_st.session_state["user_config"]["title"] == "New Title"

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_persists_to_file(self, mock_st, mock_load, mock_hist, mock_save):
        """_save_to_file is called."""
        mock_st.session_state = {}

        from web.services.database import save_user_config

        config = {"title": "Test", "feeds": []}
        save_user_config(config)

        mock_save.assert_called_once_with(config)

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_updates_onboarding_complete(self, mock_st, mock_load, mock_hist, mock_save):
        """onboarding_complete is recalculated from feeds."""
        mock_st.session_state = {}

        from web.services.database import save_user_config

        save_user_config({"title": "Test", "feeds": [_sample_feed()]})
        assert mock_st.session_state["onboarding_complete"] is True

        save_user_config({"title": "Test", "feeds": []})
        assert mock_st.session_state["onboarding_complete"] is False


class TestUpdateUserConfig:
    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_merges_kwargs(self, mock_st, mock_load, mock_hist, mock_save):
        """Keyword arguments are merged into existing config."""
        mock_st.session_state = {}

        from web.services.database import update_user_config

        update_user_config(title="Updated Title")

        assert mock_st.session_state["user_config"]["title"] == "Updated Title"

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_preserves_unmodified_keys(self, mock_st, mock_load, mock_hist, mock_save):
        """Keys not in kwargs remain unchanged."""
        mock_st.session_state = {}

        from web.services.database import get_user_config, update_user_config

        original_lang = get_user_config()["language"]
        update_user_config(title="Changed")

        assert mock_st.session_state["user_config"]["language"] == original_lang


class TestFeedManagement:
    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_get_feeds_returns_list(self, mock_st, mock_load, mock_hist, mock_save):
        """get_feeds returns a list from config."""
        mock_st.session_state = {}

        from web.services.database import get_feeds

        feeds = get_feeds()
        assert isinstance(feeds, list)

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_add_feed_appends(self, mock_st, mock_load, mock_hist, mock_save):
        """add_feed adds a new feed to the list."""
        mock_st.session_state = {}

        from web.services.database import add_feed, get_feeds

        add_feed("New Feed", "https://new.com/rss", "Custom")

        feeds = get_feeds()
        assert any(f["url"] == "https://new.com/rss" for f in feeds)

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_add_feed_no_duplicate_by_url(self, mock_st, mock_load, mock_hist, mock_save):
        """add_feed does nothing if URL already exists."""
        mock_st.session_state = {}

        from web.services.database import add_feed, get_feeds

        add_feed("Feed A", "https://a.com/rss")
        add_feed("Feed A Copy", "https://a.com/rss")

        feeds = get_feeds()
        matching = [f for f in feeds if f["url"] == "https://a.com/rss"]
        assert len(matching) == 1

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_remove_feed_by_url(self, mock_st, mock_load, mock_hist, mock_save):
        """remove_feed removes matching feed."""
        mock_st.session_state = {}

        from web.services.database import add_feed, get_feeds, remove_feed

        add_feed("Feed X", "https://x.com/rss")
        remove_feed("https://x.com/rss")

        feeds = get_feeds()
        assert not any(f["url"] == "https://x.com/rss" for f in feeds)

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_remove_feed_nonexistent_url_no_error(
        self, mock_st, mock_load, mock_hist, mock_save
    ):
        """remove_feed with unknown URL does not raise."""
        mock_st.session_state = {}

        from web.services.database import remove_feed

        remove_feed("https://does-not-exist.com/rss")  # should not raise

    @patch("web.services.database._save_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_set_feeds_replaces_list(self, mock_st, mock_load, mock_hist, mock_save):
        """set_feeds replaces entire feed list."""
        mock_st.session_state = {}

        from web.services.database import get_feeds, set_feeds

        new_feeds = [_sample_feed("A", "https://a.com"), _sample_feed("B", "https://b.com")]
        set_feeds(new_feeds)

        feeds = get_feeds()
        assert len(feeds) == 2
        assert feeds[0]["name"] == "A"


class TestOnboarding:
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_is_onboarding_complete_false_no_feeds(self, mock_st, mock_load, mock_hist):
        """Returns False when feeds list is empty."""
        mock_st.session_state = {}

        from web.services.database import is_onboarding_complete

        assert is_onboarding_complete() is False

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file")
    @patch("web.services.database.st")
    def test_is_onboarding_complete_true_with_feeds(self, mock_st, mock_load, mock_hist):
        """Returns True when feeds list is non-empty."""
        mock_st.session_state = {}
        mock_load.return_value = {"title": "Test", "feeds": [_sample_feed()]}

        from web.services.database import is_onboarding_complete

        assert is_onboarding_complete() is True

    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_complete_onboarding_sets_flag(self, mock_st, mock_load, mock_hist):
        """complete_onboarding sets session_state flag."""
        mock_st.session_state = {}

        from web.services.database import _ensure_session_state, complete_onboarding

        _ensure_session_state()
        complete_onboarding()

        assert mock_st.session_state["onboarding_complete"] is True


class TestDeliveryHistory:
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_get_delivery_history_returns_list(self, mock_st, mock_load, mock_hist):
        """Returns list from session_state."""
        mock_st.session_state = {}

        from web.services.database import get_delivery_history

        history = get_delivery_history()
        assert isinstance(history, list)

    @patch("web.services.database._save_history_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_add_delivery_record_prepends(
        self, mock_st, mock_load, mock_hist, mock_save_hist
    ):
        """New record is inserted at index 0."""
        mock_st.session_state = {}

        from web.services.database import add_delivery_record, get_delivery_history

        add_delivery_record({"status": "delivered", "edition": 1})
        add_delivery_record({"status": "delivered", "edition": 2})

        history = get_delivery_history()
        assert history[0]["edition"] == 2
        assert history[1]["edition"] == 1

    @patch("web.services.database._save_history_to_file")
    @patch("web.services.database._load_history_from_file", return_value=[])
    @patch("web.services.database._load_from_file", return_value=None)
    @patch("web.services.database.st")
    def test_add_delivery_record_caps_at_30(
        self, mock_st, mock_load, mock_hist, mock_save_hist
    ):
        """History is capped at 30 records."""
        mock_st.session_state = {}

        from web.services.database import add_delivery_record, get_delivery_history

        for i in range(35):
            add_delivery_record({"status": "delivered", "edition": i})

        history = get_delivery_history()
        assert len(history) <= 30
