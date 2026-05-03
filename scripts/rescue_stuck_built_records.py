"""One-time rescue for users with stuck `built` delivery_history records.

Background: between 2026-04-26 and 2026-05-03 the deliver phase silently
broke (see audit). Users have EPUBs in Storage with `status="built"`,
downloadable from the dashboard, but they don't know that. This script:

    1. Queries delivery_history for status="built" records
    2. Groups by user_id
    3. Sends ONE explainer email per user listing the affected dates +
       a link to the dashboard
    4. Updates each rescued record to status="delivered" so the dashboard
       reflects reality

Idempotent: re-running with --execute on a clean backlog is a no-op
(the status="built" filter produces zero rows).

Default mode is --dry-run. Real run requires --execute.

Environment variables required:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    RESEND_API_KEY      (only required for --execute)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from html import escape as _escape
from pathlib import Path

# Make the core library importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from supabase import create_client
import resend

from paper_boy.email_template import (  # type: ignore[import-not-found]
    _CAPTION,
    _EDITION_RED,
    _INK,
    _WARM_GRAY,
    _WRAPPER_END,
    _WRAPPER_START,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── helpers ────────────────────────────────────────────────────────


def group_by_user(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by user_id, preserving insertion order within each group."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["user_id"]].append(r)
    return dict(groups)


def _human_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")
    except (ValueError, IndexError):
        return iso


def render_rescue_email(title: str, edition_dates: list[str]) -> str:
    """Render the explainer email for a single user.

    Lists every date that's been recovered (sorted ascending) and points
    the user at the dashboard where the EPUBs are already downloadable.
    Reassures that the underlying issue is fixed.
    """
    sorted_dates = sorted(edition_dates)
    items = "".join(
        f'<li style="margin:2px 0;color:{_INK};font-size:13px;">{_escape(_human_date(d))}</li>'
        for d in sorted_dates
    )

    return f"""\
{_WRAPPER_START}
  <!-- Content -->
  <tr><td style="padding:28px 0 8px;text-align:center;">
    <p style="margin:0;font-size:24px;font-weight:700;color:{_INK};font-family:'Palatino Linotype',Palatino,Georgia,serif;">
      {_escape(title)}
    </p>
    <p style="margin:6px 0 0;font-size:13px;color:{_CAPTION};font-style:italic;">
      A small delivery hiccup
    </p>
  </td></tr>

  <!-- Thin rule -->
  <tr><td style="padding:12px 40px;"><div style="border-top:1px solid {_WARM_GRAY};"></div></td></tr>

  <!-- Body -->
  <tr><td style="padding:4px 0 16px;text-align:center;">
    <p style="margin:0 0 8px;font-size:16px;line-height:1.7;color:{_INK};">
      Sorry — your recent editions were ready but our delivery pipeline
      stalled. They're sitting on your dashboard, ready to download.
    </p>
    <p style="margin:0;font-size:14px;line-height:1.7;color:{_CAPTION};">
      We've fixed the underlying issue. Your next paper will arrive on schedule.
    </p>
  </td></tr>

  <!-- Recovered editions -->
  <tr><td style="padding:4px 40px 16px;">
    <p style="margin:0 0 6px;font-size:11px;color:{_CAPTION};letter-spacing:1px;text-transform:uppercase;text-align:center;">
      Editions ready for download
    </p>
    <ul style="margin:0;padding:0;list-style:none;text-align:center;">
      {items}
    </ul>
  </td></tr>

  <!-- Dashboard CTA -->
  <tr><td style="padding:0 0 20px;text-align:center;">
    <p style="margin:0;font-size:13px;line-height:1.6;color:{_CAPTION};">
      Open your
      <a href="https://www.paper-boy-news.com/dashboard" style="color:{_EDITION_RED};text-decoration:underline;">dashboard</a>
      to grab them.
    </p>
  </td></tr>

{_WRAPPER_END}"""


# ─── main flow ──────────────────────────────────────────────────────


def rescue(sb, *, dry_run: bool = True) -> dict:
    """Run the rescue. Returns a summary dict.

    summary = {
        "dry_run": bool,
        "users": int,           # unique users with at least one stuck record
        "records": int,         # total stuck records
        "emails_sent": int,
        "records_updated": int,
        "skipped_users": list,  # users where we couldn't look up an email
    }
    """
    summary = {
        "dry_run": dry_run,
        "users": 0,
        "records": 0,
        "emails_sent": 0,
        "records_updated": 0,
        "skipped_users": [],
    }

    records_resp = (
        sb.table("delivery_history")
        .select("*")
        .eq("status", "built")
        .execute()
    )
    records = records_resp.data or []
    if not records:
        logger.info("No stuck records — nothing to rescue.")
        return summary

    grouped = group_by_user(records)
    summary["users"] = len(grouped)
    summary["records"] = len(records)

    if not dry_run:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            raise RuntimeError(
                "RESEND_API_KEY is required for --execute (set in env or "
                "source web/.env.local.cloud)."
            )
        resend.api_key = api_key

    for user_id, user_records in grouped.items():
        # Look up the user's profile + auth email
        profile_resp = (
            sb.table("user_profiles")
            .select("id, auth_id, title")
            .eq("id", user_id)
            .execute()
        )
        profile_rows = profile_resp.data or []
        if not profile_rows:
            logger.warning("No profile for user %s — skipping", user_id)
            summary["skipped_users"].append(user_id)
            continue
        prof = profile_rows[0]
        title = prof.get("title", "Morning Digest")

        try:
            auth_user = sb.auth.admin.get_user_by_id(prof["auth_id"])
            account_email = auth_user.user.email
        except Exception as e:
            logger.warning(
                "Could not fetch email for user %s: %s — skipping", user_id, e,
            )
            summary["skipped_users"].append(user_id)
            continue

        edition_dates = sorted(r["edition_date"] for r in user_records)

        if dry_run:
            logger.info(
                "[dry-run] user=%s email=%s records=%d dates=%s..%s",
                user_id, account_email, len(user_records),
                edition_dates[0], edition_dates[-1],
            )
            continue

        # Send the explainer email (one per user)
        html = render_rescue_email(title=title, edition_dates=edition_dates)
        try:
            resend.Emails.send(
                {
                    "from": "Paper Boy News <delivery@paper-boy-news.com>",
                    "to": [account_email],
                    "subject": f"{title} | recovered editions ready",
                    "html": html,
                },
                {"idempotency_key": f"rescue/{user_id}"},
            )
            summary["emails_sent"] += 1
            logger.info(
                "Sent rescue email to %s (user=%s, %d editions)",
                account_email, user_id, len(user_records),
            )
        except Exception as e:
            logger.error(
                "Failed to send rescue email to %s: %s — leaving records as-is",
                account_email, e,
            )
            continue

        # Mark each record as delivered (only after successful send)
        for r in user_records:
            sb.table("delivery_history").update(
                {
                    "status": "delivered",
                    "delivery_message": "Recovered — see explainer email",
                }
            ).eq("id", r["id"]).execute()
            summary["records_updated"] += 1

    return summary


def _make_supabase_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually send emails and update records (default is dry-run)",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        logger.info("DRY RUN — no emails will be sent, no records will change.")
    else:
        logger.info("EXECUTE MODE — sending emails and updating records.")

    sb = _make_supabase_client()
    summary = rescue(sb, dry_run=dry_run)

    print()
    print("─" * 60)
    print(f"Mode:               {'dry-run' if summary['dry_run'] else 'execute'}")
    print(f"Unique users:       {summary['users']}")
    print(f"Stuck records:      {summary['records']}")
    print(f"Emails sent:        {summary['emails_sent']}")
    print(f"Records updated:    {summary['records_updated']}")
    if summary["skipped_users"]:
        print(f"Skipped users:      {len(summary['skipped_users'])}")
        for uid in summary["skipped_users"]:
            print(f"  - {uid}")
    print("─" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
