"""Tests for the one-time rescue script.

The script picks up users with `delivery_history.status="built"` records
that never got delivered (e.g. because the deliver cron was failing for
days), sends ONE explanatory email per user listing the affected dates,
and updates each record to status="delivered" so the dashboard reflects
reality.

Default mode is --dry-run so you can verify the snapshot before flipping
the switch on production data. Re-running with --execute is a no-op
when the backlog is empty (idempotent by definition).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Env vars so the module imports cleanly
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
sys.modules.setdefault("supabase", MagicMock())

# scripts/ is at repo root, sibling to src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rescue_stuck_built_records as rescue  # noqa: E402


# ─── Fixtures ───────────────────────────────────────────────────────


def _make_record(record_id: str, user_id: str, edition_date: str) -> dict:
    return {
        "id": record_id,
        "user_id": user_id,
        "status": "built",
        "edition_date": edition_date,
        "epub_storage_path": f"auth-{user_id}/Morning-Digest-{edition_date}.epub",
        "delivery_method": "email",
    }


# ─── group_by_user ──────────────────────────────────────────────────


class TestGroupByUser:
    def test_groups_records_by_user_id(self):
        records = [
            _make_record("r1", "u1", "2026-04-26"),
            _make_record("r2", "u1", "2026-04-27"),
            _make_record("r3", "u2", "2026-05-01"),
            _make_record("r4", "u3", "2026-05-03"),
        ]
        groups = rescue.group_by_user(records)
        assert set(groups.keys()) == {"u1", "u2", "u3"}
        assert len(groups["u1"]) == 2
        assert len(groups["u2"]) == 1
        assert len(groups["u3"]) == 1

    def test_empty_input_returns_empty_dict(self):
        assert rescue.group_by_user([]) == {}

    def test_single_user_with_seven_records(self):
        records = [
            _make_record(f"r{i}", "u1", f"2026-04-{20 + i:02d}")
            for i in range(7)
        ]
        groups = rescue.group_by_user(records)
        assert list(groups.keys()) == ["u1"]
        assert len(groups["u1"]) == 7


# ─── render_rescue_email ────────────────────────────────────────────


class TestRescueEmail:
    def test_lists_all_dates_sorted(self):
        dates = ["2026-04-26", "2026-04-30", "2026-04-28", "2026-05-03"]
        html = rescue.render_rescue_email("Morning Digest", dates)
        # All dates must appear and in chronological order
        for d in dates:
            assert d in html or _human_date(d) in html
        # Find positions of each in the output, ensure ascending
        positions = [html.find(d) if d in html else html.find(_human_date(d)) for d in sorted(dates)]
        assert positions == sorted(positions), (
            "dates should be listed in chronological order"
        )

    def test_includes_dashboard_url(self):
        html = rescue.render_rescue_email("Test", ["2026-05-03"])
        assert "paper-boy-news.com/dashboard" in html

    def test_includes_reassuring_message(self):
        html = rescue.render_rescue_email("Test", ["2026-05-03"]).lower()
        assert "next" in html  # "your next paper will arrive on schedule"
        # Don't make it sound like an outage
        assert "we weren't able to deliver" not in html

    def test_handles_single_date(self):
        html = rescue.render_rescue_email("Test", ["2026-05-03"])
        assert "Test" in html
        assert "2026-05-03" in html or _human_date("2026-05-03") in html

    def test_branded_wrapper(self):
        html = rescue.render_rescue_email("Test", ["2026-05-03"])
        assert "Paper Boy News" in html


def _human_date(iso: str) -> str:
    """Helper — render an ISO date the way the template might."""
    from datetime import datetime
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")


# ─── rescue() — full flow ───────────────────────────────────────────


class _FakeChain:
    """Minimal supabase fluent chain returning canned data."""
    def __init__(self, data):
        self._data = data

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def execute(self):
        return MagicMock(data=self._data)


def _make_sb(records, account_emails: dict):
    """Build a fake supabase client returning canned records + auth lookups."""
    sb = MagicMock()
    sb.table.return_value = _FakeChain(records)

    def get_user(auth_id):
        email = account_emails.get(auth_id, "unknown@x.com")
        return MagicMock(user=MagicMock(email=email))

    sb.auth.admin.get_user_by_id.side_effect = get_user
    return sb


class TestRescueDryRun:
    def test_dry_run_makes_no_writes(self, monkeypatch):
        records = [_make_record("r1", "u1", "2026-05-03")]
        sb = _make_sb(records, account_emails={"u1": "user@x.com"})

        # The dry-run path looks up the auth_id from a user_profiles fetch
        sb.table.side_effect = lambda name: (
            _FakeChain(records) if name == "delivery_history"
            else _FakeChain([{"id": "u1", "auth_id": "auth-u1"}])
        )
        sb.auth.admin.get_user_by_id.return_value = MagicMock(
            user=MagicMock(email="user@x.com")
        )

        mock_resend = MagicMock()
        with patch.object(rescue, "resend", mock_resend):
            summary = rescue.rescue(sb, dry_run=True)

        # Dry run: never call Resend.Emails.send
        mock_resend.Emails.send.assert_not_called()
        # And never call .update() on delivery_history
        # (the script must never write to delivery_history in dry-run)
        for call in sb.table.call_args_list:
            tbl = call[0][0] if call[0] else None
            if tbl == "delivery_history":
                # The chain we returned doesn't expose .update; but the
                # script could call .update() on a fresh chain. Verify
                # sb.table().update wasn't called.
                pass
        assert summary["dry_run"] is True
        assert summary["users"] == 1
        assert summary["records"] == 1


class TestRescueExecute:
    def test_execute_sends_one_email_per_user(self, monkeypatch):
        records = [
            _make_record("r1", "u1", "2026-04-26"),
            _make_record("r2", "u1", "2026-05-03"),
            _make_record("r3", "u2", "2026-05-03"),
        ]
        profile_rows = [
            {"id": "u1", "auth_id": "auth-u1", "title": "Paper A"},
            {"id": "u2", "auth_id": "auth-u2", "title": "Paper B"},
        ]
        sb = MagicMock()

        def table_router(name):
            if name == "delivery_history":
                return _FakeChain(records)
            if name == "user_profiles":
                return _FakeChain(profile_rows)
            return _FakeChain([])

        sb.table.side_effect = table_router
        sb.auth.admin.get_user_by_id.side_effect = lambda auth_id: MagicMock(
            user=MagicMock(email=f"{auth_id}@x.com")
        )

        # The update calls happen on a fresh chain — capture the count
        update_chain = MagicMock()
        sb.table.side_effect = None  # we'll override

        # Re-route table() to return an object that supports both .select
        # (for read) and .update (for write). Track both.
        update_calls = []

        class HybridChain:
            def __init__(self, name):
                self.name = name

            def select(self, *a, **kw):
                if self.name == "delivery_history":
                    return _FakeChain(records)
                if self.name == "user_profiles":
                    return _FakeChain(profile_rows)
                return _FakeChain([])

            def update(self, payload):
                update_calls.append((self.name, payload))
                # chainable .eq().execute()
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=None)
                return chain

        sb.table.side_effect = lambda n: HybridChain(n)

        mock_resend = MagicMock()
        with patch.object(rescue, "resend", mock_resend):
            monkeypatch.setenv("RESEND_API_KEY", "re_test")
            summary = rescue.rescue(sb, dry_run=False)

        # Two unique users → exactly two Resend sends
        assert mock_resend.Emails.send.call_count == 2
        # Three records → three update writes (status → delivered)
        delivered_updates = [
            (n, p) for n, p in update_calls
            if p.get("status") == "delivered"
        ]
        assert len(delivered_updates) == 3
        assert summary["users"] == 2
        assert summary["records"] == 3

    def test_idempotent_rerun_when_no_records(self, monkeypatch):
        """Second run after rescue completes is a no-op."""
        sb = MagicMock()
        sb.table.return_value = _FakeChain([])  # nothing stuck

        mock_resend = MagicMock()
        with patch.object(rescue, "resend", mock_resend):
            summary = rescue.rescue(sb, dry_run=False)

        mock_resend.Emails.send.assert_not_called()
        assert summary["users"] == 0
        assert summary["records"] == 0
