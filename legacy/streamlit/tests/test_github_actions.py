"""Tests for GitHub Actions integration service."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


# --- Helpers ---


def _make_mock_st(token=None, repo=None):
    """Build a mock st module with secrets configured."""
    mock_st = MagicMock()
    if token and repo:
        mock_st.secrets = {"github": {"token": token, "repo": repo}}
    else:
        # Simulate KeyError when accessing secrets
        mock_st.secrets.__getitem__ = MagicMock(side_effect=KeyError("github"))
    return mock_st


def _make_workflow_run(
    status="completed",
    conclusion="success",
    created_at="2026-03-01T06:00:00Z",
    run_id=12345,
):
    """Build a GitHub Actions workflow run dict."""
    return {
        "status": status,
        "conclusion": conclusion,
        "created_at": created_at,
        "id": run_id,
        "html_url": f"https://github.com/test/repo/actions/runs/{run_id}",
    }


# --- TestIsConfigured ---


class TestIsConfigured:
    @patch("web.services.github_actions.st")
    def test_true_when_secrets_set(self, mock_st):
        """Returns True when GitHub config is available via secrets."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "owner/repo"}}

        from web.services.github_actions import is_configured

        assert is_configured() is True

    @patch.dict(os.environ, {}, clear=False)
    @patch("web.services.github_actions.st")
    def test_false_when_not_configured(self, mock_st):
        """Returns False when config returns None."""
        mock_st.secrets.__getitem__ = MagicMock(side_effect=KeyError("github"))
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_REPO", None)

        from web.services.github_actions import is_configured

        assert is_configured() is False


# --- TestTriggerBuild ---


class TestTriggerBuild:
    @patch("web.services.github_actions.requests.post")
    @patch("web.services.github_actions.st")
    def test_posts_workflow_dispatch(self, mock_st, mock_post):
        """POST request sent to correct URL with auth header."""
        mock_st.secrets = {"github": {"token": "test-token", "repo": "owner/repo"}}
        mock_post.return_value = MagicMock(status_code=204)

        from web.services.github_actions import trigger_build

        trigger_build()

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "owner/repo" in call_kwargs[0][0] or "owner/repo" in str(call_kwargs)
        assert "Bearer test-token" in str(call_kwargs)

    @patch("web.services.github_actions.requests.post")
    @patch("web.services.github_actions.st")
    def test_returns_true_on_204(self, mock_st, mock_post):
        """Returns True when GitHub responds with 204."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_post.return_value = MagicMock(status_code=204)

        from web.services.github_actions import trigger_build

        assert trigger_build() is True

    @patch("web.services.github_actions.requests.post")
    @patch("web.services.github_actions.st")
    def test_returns_false_on_non_204(self, mock_st, mock_post):
        """Returns False when status code is not 204."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_post.return_value = MagicMock(status_code=404)

        from web.services.github_actions import trigger_build

        assert trigger_build() is False

    @patch.dict(os.environ, {}, clear=False)
    @patch("web.services.github_actions.st")
    def test_returns_false_when_not_configured(self, mock_st):
        """Returns False when GitHub config is unavailable."""
        mock_st.secrets.__getitem__ = MagicMock(side_effect=KeyError("github"))
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_REPO", None)

        from web.services.github_actions import trigger_build

        assert trigger_build() is False

    @patch("web.services.github_actions.requests.post")
    @patch("web.services.github_actions.st")
    def test_returns_false_on_request_exception(self, mock_st, mock_post):
        """Network error returns False."""
        import requests

        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_post.side_effect = requests.RequestException("timeout")

        from web.services.github_actions import trigger_build

        assert trigger_build() is False

    @patch("web.services.github_actions.requests.post")
    @patch("web.services.github_actions.st")
    def test_includes_user_id_in_payload(self, mock_st, mock_post):
        """user_id is included in inputs when provided."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_post.return_value = MagicMock(status_code=204)

        from web.services.github_actions import trigger_build

        trigger_build(user_id="user-42")

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert payload["inputs"]["user_id"] == "user-42"


# --- TestGetRecentBuilds ---


class TestGetRecentBuilds:
    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_returns_list_of_editions(self, mock_st, mock_get):
        """Maps workflow runs to edition dicts."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "workflow_runs": [_make_workflow_run()]
                }
            ),
        )

        from web.services.github_actions import get_recent_builds

        editions = get_recent_builds()
        assert len(editions) == 1
        assert "date" in editions[0]
        assert "status_label" in editions[0]

    @pytest.mark.parametrize(
        "status,conclusion,expected_label",
        [
            ("completed", "success", "Delivered"),
            ("completed", "failure", "Failed"),
            ("in_progress", None, "Building..."),
            ("queued", None, "Queued"),
        ],
    )
    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_maps_status_to_label(
        self, mock_st, mock_get, status, conclusion, expected_label
    ):
        """GitHub status/conclusion is mapped to the correct label."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "workflow_runs": [
                        _make_workflow_run(status=status, conclusion=conclusion)
                    ]
                }
            ),
        )

        from web.services.github_actions import get_recent_builds

        editions = get_recent_builds()
        assert editions[0]["status_label"] == expected_label

    @patch.dict(os.environ, {}, clear=False)
    @patch("web.services.github_actions.st")
    def test_returns_empty_when_not_configured(self, mock_st):
        """Returns [] when GitHub config is unavailable."""
        mock_st.secrets.__getitem__ = MagicMock(side_effect=KeyError("github"))
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_REPO", None)

        from web.services.github_actions import get_recent_builds

        assert get_recent_builds() == []

    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_returns_empty_on_api_error(self, mock_st, mock_get):
        """Returns [] when API returns non-200."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(status_code=500)

        from web.services.github_actions import get_recent_builds

        assert get_recent_builds() == []

    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_returns_empty_on_request_exception(self, mock_st, mock_get):
        """Returns [] on network error."""
        import requests

        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.side_effect = requests.RequestException("timeout")

        from web.services.github_actions import get_recent_builds

        assert get_recent_builds() == []

    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_respects_limit_parameter(self, mock_st, mock_get):
        """per_page query param matches limit argument."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"workflow_runs": []}),
        )

        from web.services.github_actions import get_recent_builds

        get_recent_builds(limit=5)

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["per_page"] == 5


# --- TestGetBuildStatus ---


class TestGetBuildStatus:
    @pytest.mark.parametrize(
        "status,conclusion,expected",
        [
            ("completed", "success", "delivered"),
            ("completed", "failure", "failed"),
            ("in_progress", None, "building"),
            ("queued", None, "building"),
        ],
    )
    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_returns_correct_status(
        self, mock_st, mock_get, status, conclusion, expected
    ):
        """Status/conclusion is mapped to the correct return value."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={"status": status, "conclusion": conclusion}
            ),
        )

        from web.services.github_actions import get_build_status

        assert get_build_status(12345) == expected

    @patch.dict(os.environ, {}, clear=False)
    @patch("web.services.github_actions.st")
    def test_returns_none_when_not_configured(self, mock_st):
        """Returns None when config unavailable."""
        mock_st.secrets.__getitem__ = MagicMock(side_effect=KeyError("github"))
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_REPO", None)

        from web.services.github_actions import get_build_status

        assert get_build_status(12345) is None

    @patch("web.services.github_actions.requests.get")
    @patch("web.services.github_actions.st")
    def test_returns_none_on_api_error(self, mock_st, mock_get):
        """Returns None on non-200 status."""
        mock_st.secrets = {"github": {"token": "tok", "repo": "o/r"}}
        mock_get.return_value = MagicMock(status_code=404)

        from web.services.github_actions import get_build_status

        assert get_build_status(99999) is None
