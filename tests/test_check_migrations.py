"""Tests for scripts/check_migrations.py.

The checker is the pre-merge half of the schema-drift incident response —
it has to catch missing intent comments, bad filenames, and surface
destructive operations as warnings without blocking legitimate use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_migrations as cm  # noqa: E402


# ─── Filename naming ─────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "20260503000000_resend_message_id.sql",
    "20240101000000_init.sql",
    "20260317000001_security_hardening.sql",
])
def test_filename_pattern_accepts_valid(name: str, tmp_path: Path):
    p = tmp_path / name
    p.write_text("-- intent\nCREATE TABLE IF NOT EXISTS x (id int);\n")
    finding = cm._check_file(p)
    assert finding.errors == [], finding.errors


@pytest.mark.parametrize("name", [
    "init.sql",                            # missing timestamp
    "2026050300_too_short.sql",            # 10-digit timestamp
    "202605030000000_extra_digit.sql",     # 15-digit timestamp
    "20260503000000_BadCase.sql",          # uppercase
    "20260503000000_with-dash.sql",        # dash not allowed
    "20260503000000.sql",                  # missing description
])
def test_filename_pattern_rejects_invalid(name: str, tmp_path: Path):
    p = tmp_path / name
    p.write_text("-- intent\nCREATE TABLE IF NOT EXISTS x (id int);\n")
    finding = cm._check_file(p)
    assert any("filename" in err for err in finding.errors), (
        f"expected filename error for {name!r}, got {finding.errors!r}"
    )


# ─── Intent comment ───────────────────────────────────────────────────


def test_missing_intent_is_an_error(tmp_path: Path):
    p = tmp_path / "20260503000000_no_comment.sql"
    p.write_text("CREATE TABLE IF NOT EXISTS x (id int);\n")
    finding = cm._check_file(p)
    assert any("intent" in err for err in finding.errors)


def test_bare_dashes_dont_count_as_intent(tmp_path: Path):
    p = tmp_path / "20260503000000_bare.sql"
    p.write_text("--\n-- \nCREATE TABLE IF NOT EXISTS x (id int);\n")
    finding = cm._check_file(p)
    assert any("intent" in err for err in finding.errors)


def test_intent_comment_passes(tmp_path: Path):
    p = tmp_path / "20260503000000_intent.sql"
    p.write_text(
        "-- Add resend_message_id for email idempotency.\n"
        "CREATE TABLE IF NOT EXISTS x (id int);\n"
    )
    finding = cm._check_file(p)
    assert finding.errors == []


# ─── Destructive operations (warnings, not errors) ──────────────────


@pytest.mark.parametrize("sql,label", [
    ("DROP TABLE old_users;", "DROP TABLE"),
    ("ALTER TABLE x DROP COLUMN y;", "DROP COLUMN"),
    ("DROP INDEX idx_foo;", "DROP INDEX"),
    ("ALTER TABLE x DROP CONSTRAINT fk_y;", "DROP CONSTRAINT"),
    ("DROP POLICY \"only owners\" ON x;", "DROP POLICY"),
    ("DROP TRIGGER on_user_created ON auth.users;", "DROP TRIGGER"),
    ("TRUNCATE TABLE feed_stats;", "TRUNCATE"),
    ("ALTER TABLE x ALTER COLUMN y TYPE bigint;", "ALTER COLUMN ... TYPE"),
    ("ALTER TABLE x ALTER COLUMN y SET NOT NULL;", "ALTER COLUMN ... SET NOT NULL"),
    ("ALTER TABLE x DISABLE ROW LEVEL SECURITY;", "DISABLE RLS"),
])
def test_destructive_operations_produce_warnings_not_errors(
    sql: str, label: str, tmp_path: Path
):
    p = tmp_path / "20260503000000_destructive.sql"
    p.write_text(f"-- destructive operation\n{sql}\n")
    finding = cm._check_file(p)
    assert finding.errors == [], (
        f"destructive ops must be warnings only; got error for {sql!r}"
    )
    assert any(label in w for w in finding.warnings), (
        f"expected warning for {label!r}, got {finding.warnings!r}"
    )


def test_destructive_in_comment_is_ignored(tmp_path: Path):
    """Commented-out destructive operations must not trigger warnings —
    common during migration drafting."""
    p = tmp_path / "20260503000000_safe.sql"
    p.write_text(
        "-- Considered DROP TABLE old_users but rolled back.\n"
        "/* DROP COLUMN deprecated_field; */\n"
        "CREATE TABLE IF NOT EXISTS x (id int);\n"
    )
    finding = cm._check_file(p)
    assert finding.warnings == [], finding.warnings


# ─── Idempotency hints (notes) ───────────────────────────────────────


def test_create_table_without_if_not_exists_is_a_note(tmp_path: Path):
    p = tmp_path / "20260503000000_create.sql"
    p.write_text("-- create things\nCREATE TABLE x (id int);\n")
    finding = cm._check_file(p)
    assert any("CREATE TABLE" in n for n in finding.notes)
    assert finding.errors == []


def test_create_table_if_not_exists_clean(tmp_path: Path):
    p = tmp_path / "20260503000000_create.sql"
    p.write_text("-- create things\nCREATE TABLE IF NOT EXISTS x (id int);\n")
    finding = cm._check_file(p)
    assert finding.notes == [], finding.notes


def test_add_column_without_if_not_exists_is_a_note(tmp_path: Path):
    p = tmp_path / "20260503000000_alter.sql"
    p.write_text("-- add a column\nALTER TABLE x ADD COLUMN y text;\n")
    finding = cm._check_file(p)
    assert any("ADD COLUMN" in n for n in finding.notes)


def test_add_column_if_not_exists_clean(tmp_path: Path):
    """Mirrors the actual `20260503000000_resend_message_id.sql` shape."""
    p = tmp_path / "20260503000000_alter.sql"
    p.write_text(
        "-- Email idempotency: durable proof-of-send.\n"
        "ALTER TABLE delivery_history ADD COLUMN IF NOT EXISTS resend_message_id text;\n"
    )
    finding = cm._check_file(p)
    assert finding.errors == []
    assert finding.warnings == []
    assert finding.notes == []


# ─── Report rendering + verdict ──────────────────────────────────────


def test_verdict_pass(tmp_path: Path):
    p = tmp_path / "20260503000000_clean.sql"
    p.write_text(
        "-- clean migration\n"
        "ALTER TABLE x ADD COLUMN IF NOT EXISTS y text;\n"
    )
    findings = [cm._check_file(p)]
    report, exit_code = cm.render_report(findings, scope="test")
    assert "**Verdict:** PASS" in report
    assert "PASS WITH WARNINGS" not in report
    assert exit_code == 0


def test_verdict_pass_with_warnings(tmp_path: Path):
    p = tmp_path / "20260503000000_destructive.sql"
    p.write_text(
        "-- legitimate destructive change\n"
        "ALTER TABLE x DROP COLUMN deprecated;\n"
    )
    findings = [cm._check_file(p)]
    report, exit_code = cm.render_report(findings, scope="test")
    assert "**Verdict:** PASS WITH WARNINGS" in report
    # Warnings should NOT block CI
    assert exit_code == 0


def test_verdict_fail_on_naming(tmp_path: Path):
    p = tmp_path / "bad_name.sql"
    p.write_text("-- intent\nCREATE TABLE IF NOT EXISTS x (id int);\n")
    findings = [cm._check_file(p)]
    report, exit_code = cm.render_report(findings, scope="test")
    assert "**Verdict:** FAIL" in report
    assert exit_code == 1


def test_verdict_fail_on_missing_intent(tmp_path: Path):
    p = tmp_path / "20260503000000_no_comment.sql"
    p.write_text("CREATE TABLE IF NOT EXISTS x (id int);\n")
    findings = [cm._check_file(p)]
    report, exit_code = cm.render_report(findings, scope="test")
    assert "**Verdict:** FAIL" in report
    assert exit_code == 1


def test_empty_scope_renders_clean_message(tmp_path: Path):
    report, exit_code = cm.render_report([], scope="changed in `main..HEAD`")
    assert "nothing to check" in report.lower()
    assert exit_code == 0


def test_real_repo_migrations_have_no_hard_errors():
    """The current set of committed migrations must not have hard errors —
    this is what the deploy job is about to push to prod."""
    if not cm.MIGRATIONS_DIR.exists():
        pytest.skip("supabase/migrations not present")
    findings = [cm._check_file(p) for p in cm._all_migration_files()]
    errors = {f.name: f.errors for f in findings if f.errors}
    assert not errors, (
        f"committed migrations must not have hard errors; got {errors}"
    )
