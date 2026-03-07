"""GitHub Actions integration for triggering and monitoring builds."""

import os
from datetime import datetime
from typing import List, Optional, Tuple

import requests
import streamlit as st


def _get_github_config() -> Optional[Tuple[str, str]]:
    """Get GitHub token and repo from Streamlit secrets or environment.

    Returns (token, repo) tuple, or None if not configured.
    """
    # Try Streamlit secrets first
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        return token, repo
    except (KeyError, FileNotFoundError):
        pass

    # Fall back to environment variables
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO")
    if token and repo:
        return token, repo

    return None


def is_configured() -> bool:
    """Check if GitHub Actions integration is configured."""
    return _get_github_config() is not None


def trigger_build(user_id: str = "") -> bool:
    """Trigger a GitHub Actions workflow build.

    Args:
        user_id: Optional user ID for per-user builds.

    Returns:
        True if the workflow was triggered successfully.
    """
    config = _get_github_config()
    if not config:
        return False

    token, repo = config
    url = f"https://api.github.com/repos/{repo}/actions/workflows/daily-news.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "ref": "main",
        "inputs": {"user_id": user_id} if user_id else {},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 204
    except requests.RequestException:
        return False


def get_recent_builds(limit: int = 10) -> List[dict]:
    """Get recent build runs, presented as 'editions'.

    Returns a list of dicts with keys: date, status, status_label,
    article_count (estimated), run_id.
    """
    config = _get_github_config()
    if not config:
        return []

    token, repo = config
    url = f"https://api.github.com/repos/{repo}/actions/workflows/daily-news.yml/runs"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            url, headers=headers, params={"per_page": limit}, timeout=10
        )
        if response.status_code != 200:
            return []

        runs = response.json().get("workflow_runs", [])
    except requests.RequestException:
        return []

    editions = []
    for run in runs:
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion")

        if status == "completed" and conclusion == "success":
            status_label = "Delivered"
        elif status == "completed" and conclusion == "failure":
            status_label = "Failed"
        elif status == "in_progress":
            status_label = "Building..."
        elif status == "queued":
            status_label = "Queued"
        else:
            status_label = "Unknown"

        created = run.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            date_str = dt.strftime("%A, %B %-d, %Y")
            time_str = dt.strftime("%-I:%M %p")
        except (ValueError, AttributeError):
            date_str = created[:10] if created else "Unknown"
            time_str = ""

        editions.append({
            "date": date_str,
            "time": time_str,
            "status": status_label.lower().replace("...", "").replace(" ", "_").rstrip("_"),
            "status_label": status_label,
            "run_id": run.get("id"),
            "run_url": run.get("html_url", ""),
        })

    return editions


def get_build_status(run_id: int) -> Optional[str]:
    """Check the status of a specific build run.

    Returns: "delivered", "failed", "building", "queued", or None.
    """
    config = _get_github_config()
    if not config:
        return None

    token, repo = config
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        run = response.json()
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion")

        if status == "completed" and conclusion == "success":
            return "delivered"
        elif status == "completed":
            return "failed"
        elif status in ("in_progress", "queued"):
            return "building"
    except requests.RequestException:
        pass

    return None
