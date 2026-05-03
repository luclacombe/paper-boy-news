"""Tests for email template rendering."""

from __future__ import annotations

from paper_boy.email_template import (
    render_delivery_email,
    render_empty_edition_email,
    render_failure_email,
    render_admin_alert_email,
)


class TestRenderDeliveryEmail:
    def test_contains_title_and_date(self):
        html = render_delivery_email("Morning Digest", "March 22, 2026", 10, 5)
        assert "Morning Digest" in html
        assert "March 22, 2026" in html

    def test_contains_branded_wrapper(self):
        html = render_delivery_email("Test", "March 22, 2026", 5, 3)
        assert "Paper Boy News" in html
        assert "www.paper-boy-news.com" in html


class TestRenderFailureEmail:
    def test_contains_title_and_date(self):
        html = render_failure_email("Morning Digest", "March 22, 2026")
        assert "Morning Digest" in html
        assert "March 22, 2026" in html

    def test_contains_branded_wrapper(self):
        html = render_failure_email("Test", "March 22, 2026")
        assert "Paper Boy News" in html
        assert "www.paper-boy-news.com" in html

    def test_contains_dashboard_link(self):
        html = render_failure_email("Test", "March 22, 2026")
        assert "paper-boy-news.com/dashboard" in html

    def test_does_not_expose_error_details(self):
        html = render_failure_email("Test", "March 22, 2026")
        assert "exception" not in html.lower()
        assert "traceback" not in html.lower()
        assert "stem" not in html.lower()

    def test_contains_reassuring_message(self):
        html = render_failure_email("Test", "March 22, 2026")
        assert "notified" in html.lower()
        assert "next edition" in html.lower()

    def test_escapes_html_in_title(self):
        html = render_failure_email("<script>alert('xss')</script>", "March 22, 2026")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderEmptyEditionEmail:
    """The "your sources were quiet today" email — different UX from failure.

    Empty editions are user-side (their feeds were quiet), not a system bug.
    The template should explicitly call that out and link to /settings to
    add more sources rather than implying our system is broken.
    """

    def test_contains_title_and_date(self):
        html = render_empty_edition_email(
            "Morning Digest", "May 3, 2026", feed_names=["The Verge"]
        )
        assert "Morning Digest" in html
        assert "May 3, 2026" in html

    def test_contains_branded_wrapper(self):
        html = render_empty_edition_email(
            "Test", "May 3, 2026", feed_names=["The Verge"]
        )
        assert "Paper Boy News" in html
        assert "www.paper-boy-news.com" in html

    def test_explains_empty_editions_are_not_an_outage(self):
        html = render_empty_edition_email(
            "Test", "May 3, 2026", feed_names=["The Verge"]
        ).lower()
        assert "quiet" in html, "must call out 'your feeds were quiet today'"
        # No language that implies a system failure / outage
        assert "we weren't able to deliver" not in html
        assert "we've been notified" not in html

    def test_links_to_settings_to_add_more_sources(self):
        html = render_empty_edition_email(
            "Test", "May 3, 2026", feed_names=["The Verge"]
        )
        assert "paper-boy-news.com/settings" in html

    def test_lists_feeds_we_tried(self):
        html = render_empty_edition_email(
            "Test", "May 3, 2026",
            feed_names=["The Verge", "Hacker News", "AP News"],
        )
        for name in ("The Verge", "Hacker News", "AP News"):
            assert name in html

    def test_escapes_html_in_feed_names(self):
        html = render_empty_edition_email(
            "Test", "May 3, 2026",
            feed_names=["<script>alert('xss')</script>"],
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_handles_empty_feed_list_gracefully(self):
        html = render_empty_edition_email("Test", "May 3, 2026", feed_names=[])
        # Doesn't crash; still includes the core message
        assert "Test" in html
        assert "May 3, 2026" in html


class TestRenderAdminAlertEmail:
    def test_contains_all_debug_fields(self):
        html = render_admin_alert_email(
            record_id="abc-123",
            user_id="user-456",
            delivery_method="email",
            edition_date="2026-03-22",
            error_message="'str' has no attribute 'stem'",
        )
        assert "abc-123" in html
        assert "user-456" in html
        assert "email" in html
        assert "2026-03-22" in html
        assert "attribute" in html

    def test_contains_branded_wrapper(self):
        html = render_admin_alert_email("r", "u", "local", "2026-01-01", "err")
        assert "Paper Boy News" in html

    def test_contains_timestamp(self):
        html = render_admin_alert_email("r", "u", "local", "2026-01-01", "err")
        assert "UTC" in html

    def test_escapes_html_in_error_message(self):
        html = render_admin_alert_email("r", "u", "local", "2026-01-01", "<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
