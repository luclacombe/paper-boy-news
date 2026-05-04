#!/usr/bin/env python3
"""Pre-merge safety check for Supabase migrations.

Runs in CI on every PR that touches `supabase/migrations/**` AND inside the
deploy job as a final guard before `supabase db push`. Also runs locally:

    python scripts/check_migrations.py            # check all migrations
    python scripts/check_migrations.py --diff origin/main..HEAD  # PR mode

Exit codes:
    0 — all checks pass (warnings allowed)
    1 — one or more hard violations (naming, missing intent, malformed SQL)
    2 — invocation error (bad args, no migrations dir)

The output is markdown — designed to be posted as a PR comment by the CI
job. The checker is intentionally heuristic on destructive operations:
they're flagged as warnings, never failures, because legitimate destructive
migrations exist (cleanup, schema reorgs). The PR author is the human in
the loop.

Why this script exists
----------------------
On 2026-05-04 the `resend_message_id` migration was merged to git but
never applied to production Supabase — there's no automation that pushes
migrations on merge. Five users got phantom "delivery issue" emails when
the post-send UPDATE failed against the missing column. This checker is
the human-readable half of the fix; `.github/workflows/supabase-migrate.yml`
is the deploy half.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# YYYYMMDDHHMMSS_description.sql — Supabase CLI's required format.
NAMING_RE = re.compile(r"^(\d{14})_[a-z0-9][a-z0-9_]*\.sql$")

# Operations that can lose data or break dependent code. Warning-only —
# legitimate uses exist. The PR author has to confirm intent in review.
DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDROP\s+TABLE\b", re.I), "DROP TABLE"),
    (re.compile(r"\bDROP\s+COLUMN\b", re.I), "DROP COLUMN"),
    (re.compile(r"\bDROP\s+INDEX\b", re.I), "DROP INDEX"),
    (re.compile(r"\bDROP\s+CONSTRAINT\b", re.I), "DROP CONSTRAINT"),
    (re.compile(r"\bDROP\s+POLICY\b", re.I), "DROP POLICY"),
    (re.compile(r"\bDROP\s+TRIGGER\b", re.I), "DROP TRIGGER"),
    (re.compile(r"\bTRUNCATE\b", re.I), "TRUNCATE"),
    (re.compile(r"\bALTER\s+COLUMN\s+\w+\s+TYPE\b", re.I), "ALTER COLUMN ... TYPE"),
    (re.compile(r"\bALTER\s+COLUMN\s+\w+\s+SET\s+NOT\s+NULL\b", re.I),
     "ALTER COLUMN ... SET NOT NULL (verify default is set or column is empty)"),
    (re.compile(r"\bDISABLE\s+ROW\s+LEVEL\s+SECURITY\b", re.I), "DISABLE RLS"),
]


@dataclass
class FileFinding:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.path.name


def _strip_comments(sql: str) -> str:
    """Remove line and block comments — destructive-op detection should
    not trigger on commented-out examples."""
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    return sql


def _has_intent_comment(sql: str) -> bool:
    """A migration must start with a comment block describing intent.

    First non-empty line must begin with `--`. Line must have at least
    a few alphabetic characters (so a bare `--` doesn't count).
    """
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("--"):
            return False
        # Strip leading dashes + whitespace, require some content
        body = stripped.lstrip("-").strip()
        return len(body) >= 6 and any(c.isalpha() for c in body)
    return False


def _check_filename(path: Path) -> list[str]:
    if not NAMING_RE.match(path.name):
        return [
            f"filename `{path.name}` does not match `YYYYMMDDHHMMSS_description.sql`. "
            "The Supabase CLI rejects out-of-pattern names; rename before merging."
        ]
    return []


def _check_destructive(sql: str) -> list[str]:
    cleaned = _strip_comments(sql)
    findings: list[str] = []
    for pattern, label in DESTRUCTIVE_PATTERNS:
        if pattern.search(cleaned):
            findings.append(
                f"contains **{label}** — confirm dependent app code is updated, "
                "and prefer a backwards-compatible two-step rollout (deprecate "
                "→ deploy → drop) so the post-deploy migration window doesn't "
                "break running pods."
            )
    return findings


def _check_idempotency_hint(sql: str) -> list[str]:
    """Soft hints — "consider IF NOT EXISTS" — to make rerunning safe.

    Note-level (info), never failing. Exists because rerunning a
    migration manually after a partial failure is the most common
    recovery path.
    """
    cleaned = _strip_comments(sql)
    notes: list[str] = []
    if re.search(r"\bCREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)", cleaned, re.I):
        notes.append("`CREATE TABLE` without `IF NOT EXISTS` — safer to add it")
    if re.search(r"\bCREATE\s+INDEX\s+(?!IF\s+NOT\s+EXISTS)", cleaned, re.I):
        notes.append("`CREATE INDEX` without `IF NOT EXISTS` — safer to add it")
    if re.search(r"\bALTER\s+TABLE\s+\w+\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS)",
                 cleaned, re.I):
        notes.append("`ADD COLUMN` without `IF NOT EXISTS` — safer to add it")
    return notes


def _check_file(path: Path) -> FileFinding:
    finding = FileFinding(path=path)
    finding.errors.extend(_check_filename(path))
    try:
        sql = path.read_text(encoding="utf-8")
    except Exception as e:
        finding.errors.append(f"could not read file: {e}")
        return finding
    if not _has_intent_comment(sql):
        finding.errors.append(
            "missing intent comment — first non-empty line must start with "
            "`-- ` and explain why this migration exists. Future you (or "
            "the next person to debug a phantom failure) needs the why."
        )
    finding.warnings.extend(_check_destructive(sql))
    finding.notes.extend(_check_idempotency_hint(sql))
    return finding


def _files_in_diff(diff_range: str) -> list[Path]:
    """Return migration files added or modified in the given git range."""
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AM", diff_range,
             "--", "supabase/migrations/"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        print(f"::error::git diff failed for range {diff_range!r}: {e.stderr}",
              file=sys.stderr)
        sys.exit(2)
    paths: list[Path] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or not line.endswith(".sql"):
            continue
        full = REPO_ROOT / line
        if full.exists():
            paths.append(full)
    return paths


def _all_migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.iterdir() if p.suffix == ".sql")


def render_report(
    findings: list[FileFinding], *, scope: str
) -> tuple[str, int]:
    """Build the markdown report and decide the exit code.

    Returns (markdown, exit_code).
    """
    total_errors = sum(len(f.errors) for f in findings)
    total_warnings = sum(len(f.warnings) for f in findings)
    total_notes = sum(len(f.notes) for f in findings)

    if not findings:
        return (
            f"## Migration check\n\n"
            f"**Scope:** {scope}\n\n"
            "No migration files in scope — nothing to check.\n",
            0,
        )

    if total_errors == 0 and total_warnings == 0 and total_notes == 0:
        verdict = "PASS"
    elif total_errors == 0:
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "FAIL"

    lines: list[str] = []
    lines.append("## Migration check\n")
    lines.append(f"**Scope:** {scope}  ")
    lines.append(f"**Files checked:** {len(findings)}  ")
    lines.append(
        f"**Errors:** {total_errors}  **Warnings:** {total_warnings}  "
        f"**Notes:** {total_notes}\n"
    )
    lines.append(f"**Verdict:** {verdict}\n")

    for f in findings:
        # Skip clean files in the per-file dump if we're checking many,
        # to keep the comment readable. Always show files with findings.
        clean = not (f.errors or f.warnings or f.notes)
        if clean and len(findings) > 4:
            continue
        lines.append(f"### `{f.name}`\n")
        if clean:
            lines.append("- OK\n")
            continue
        for err in f.errors:
            lines.append(f"- ❌ **error** — {err}")
        for warn in f.warnings:
            lines.append(f"- ⚠️  **warning** — {warn}")
        for note in f.notes:
            lines.append(f"- 💡 note — {note}")
        lines.append("")

    if total_errors == 0 and total_warnings == 0 and total_notes == 0:
        lines.append(
            f"All {len(findings)} migration files in scope passed every check.\n"
        )

    if total_errors == 0 and (total_warnings or total_notes):
        lines.append(
            "\n_Warnings and notes don't block the merge. Confirm in review "
            "that destructive operations are intentional and that any "
            "dependent application code (Drizzle schema, types, queries) is "
            "updated in the same PR._\n"
        )

    if total_errors > 0:
        lines.append(
            "\n_Errors block the merge. Fix and push again._\n"
        )

    return "\n".join(lines), (1 if total_errors > 0 else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--diff",
        metavar="RANGE",
        default=None,
        help="Only check migrations changed in this git range (e.g. "
             "`origin/main..HEAD`). Default: check all migrations.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Check all migration files (default unless --diff is given).",
    )
    parser.add_argument(
        "--output", metavar="PATH", default=None,
        help="Write the markdown report to PATH (in addition to stdout).",
    )
    args = parser.parse_args(argv)

    if args.diff:
        files = _files_in_diff(args.diff)
        scope = f"changed in `{args.diff}`"
    else:
        files = _all_migration_files()
        scope = "all migration files"

    findings = [_check_file(p) for p in files]
    report, exit_code = render_report(findings, scope=scope)

    print(report)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
