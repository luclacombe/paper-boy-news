"""Tests for GitHub Actions workflow files.

These guard against silent regressions in build/delivery infrastructure
that we can't reach from Python unit tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
WORKFLOW = WORKFLOWS_DIR / "build-newspaper.yml"
MIGRATE_WORKFLOW = WORKFLOWS_DIR / "supabase-migrate.yml"

BUILD_CRON = "45 3,7,11,15,19,23 * * *"
DELIVER_CRON = "0,30 * * * *"


def _load(path: Path = WORKFLOW) -> dict:
    return yaml.safe_load(path.read_text())


def _on_block(path: Path = WORKFLOW) -> dict:
    """Return the workflow's `on:` block.

    PyYAML's YAML 1.1 boolean coercion turns the unquoted key `on:` into
    Python `True`, so `data["on"]` is empty. Accept either form so the
    test stays robust if the YAML is later quoted.
    """
    data = _load(path)
    block = data.get("on")
    if block is None:
        block = data.get(True)
    assert block is not None, f"could not find `on:` block in {path.name}"
    return block


def _find_step(name_substring: str) -> dict:
    """Return the first step whose name contains the given substring."""
    data = _load()
    steps = data["jobs"]["build"]["steps"]
    for step in steps:
        if name_substring in step.get("name", ""):
            return step
    raise AssertionError(
        f"step named like {name_substring!r} not found; saw {[s.get('name') for s in steps]}"
    )


class TestPlaywrightStepFaultTolerance:
    """A flaky Playwright install must never block builds for non-FT users.

    On 2026-05-02 the Playwright install hung for 17 minutes and aborted the
    whole workflow — every user missed that day's edition silently. Hardening:
      - continue-on-error: failure is a warning, not a fatal step
      - timeout-minutes: cap waiting time so a hang can't block the runner
    The FT extractor (`_extract_ft_articles`) already returns an empty
    Section when playwright is unimportable, so non-FT users build fine.
    """

    def test_step_has_continue_on_error(self):
        step = _find_step("Install Playwright")
        assert step.get("continue-on-error") is True, (
            "Playwright install must not abort the workflow when it fails"
        )

    def test_step_has_timeout(self):
        step = _find_step("Install Playwright")
        timeout = step.get("timeout-minutes")
        assert timeout is not None, "Playwright install needs a timeout cap"
        assert 1 <= timeout <= 10, (
            f"timeout-minutes={timeout} is outside the sane range (1..10)"
        )

    def test_step_emits_warning_on_failure(self):
        """When the install fails the step should leave a workflow annotation."""
        step = _find_step("Install Playwright")
        run_block = step.get("run", "")
        assert "::warning::" in run_block, (
            "the install step should emit a ::warning:: annotation on failure"
        )


class TestRepositoryDispatchTypes:
    """The CF Worker fires `build` and `deliver` repository_dispatch events.

    The legacy `build-newspaper` type stays for the on-demand "Get it now"
    flow (web/src/actions/build.ts → web/src/lib/github-dispatch.ts).
    """

    def test_all_three_dispatch_types_present(self):
        types = _on_block()["repository_dispatch"]["types"]
        assert "build-newspaper" in types, "on-demand path must keep working"
        assert "build" in types, "CF Worker fires `build` for scheduled builds"
        assert "deliver" in types, "CF Worker fires `deliver` for scheduled delivers"


class TestScheduleSafetyNet:
    """The GH Actions cron triggers stay as a safety net during the CF migration.

    Removing them is a separate follow-up PR after a week of clean CF cron
    operation. Until then, double-firing is harmless: run_build_all() skips
    records that aren't `failed`, run_deliver()'s recency cap (PR 1) plus
    the resend_message_id idempotency (PR 1) make a duplicate dispatch a
    no-op.
    """

    def test_build_cron_preserved(self):
        crons = [entry["cron"] for entry in _on_block()["schedule"]]
        assert BUILD_CRON in crons

    def test_deliver_cron_preserved(self):
        crons = [entry["cron"] for entry in _on_block()["schedule"]]
        assert DELIVER_CRON in crons


class TestSetBuildModeStep:
    """A `Set BUILD_MODE` shell step resolves the mode for every event.

    This replaces the previous job-level `env: BUILD_MODE: <expression>`
    so we can:
      - support the new `build` / `deliver` `repository_dispatch` types
      - keep the safety-net `schedule:` cron triggers
      - keep the on-demand `build-newspaper` (record_id-driven) type
      - log the resolution for observability

    Subsequent steps' `if: env.BUILD_MODE == 'build'` continue to work
    because the step writes BUILD_MODE to `$GITHUB_ENV`.
    """

    def test_step_exists_and_is_first(self):
        data = _load()
        steps = data["jobs"]["build"]["steps"]
        assert steps, "no steps in build job"
        assert "BUILD_MODE" in steps[0].get("name", ""), (
            f"Set BUILD_MODE must be the FIRST step so subsequent `if: env.BUILD_MODE == ...` "
            f"conditions can read the resolved value; saw first step name={steps[0].get('name')!r}"
        )

    def test_step_reads_event_metadata_from_env(self):
        step = _find_step("Set BUILD_MODE")
        env = step.get("env", {})
        for required in ("EVENT_NAME", "EVENT_ACTION", "EVENT_SCHEDULE"):
            assert required in env, f"missing env.{required}"

    def test_step_writes_to_github_env(self):
        step = _find_step("Set BUILD_MODE")
        run = step.get("run", "")
        assert "BUILD_MODE=" in run and "GITHUB_ENV" in run, (
            "the step must export BUILD_MODE so subsequent steps' env.BUILD_MODE works"
        )

    def test_step_handles_all_event_branches(self):
        """Structural smoke test — every dispatch type and cron must be matched."""
        step = _find_step("Set BUILD_MODE")
        run = step.get("run", "")
        for token in (
            "repository_dispatch",
            "schedule",
            "build-newspaper",
            BUILD_CRON,
            DELIVER_CRON,
        ):
            assert token in run, f"Set BUILD_MODE step missing branch for {token!r}"
        # `build` and `deliver` appear as case labels on bare words; assert
        # both appear at least once in the run block.
        assert "build)" in run or '"build")' in run, "missing build case"
        assert "deliver)" in run or '"deliver")' in run, "missing deliver case"

    @staticmethod
    def _run_resolution(event_name: str, event_action: str, event_schedule: str) -> str:
        """Execute the Set BUILD_MODE step's shell logic in a subprocess.

        Replaces the `>> "$GITHUB_ENV"` write with a stdout `echo` so we can
        capture the resolved value, then runs under bash with the workflow's
        env: variables set.
        """
        step = _find_step("Set BUILD_MODE")
        run = step["run"]
        # Swap the GITHUB_ENV write for a marker echo we can grep.
        script = run.replace(
            'echo "BUILD_MODE=$MODE" >> "$GITHUB_ENV"',
            'echo "RESOLVED:$MODE"',
        )
        result = subprocess.run(
            ["bash", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "EVENT_NAME": event_name,
                "EVENT_ACTION": event_action,
                "EVENT_SCHEDULE": event_schedule,
            },
        )
        assert result.returncode == 0, f"shell exited {result.returncode}: {result.stderr!r}"
        for line in result.stdout.splitlines():
            if line.startswith("RESOLVED:"):
                return line[len("RESOLVED:"):]
        raise AssertionError(f"no RESOLVED: line in {result.stdout!r}")

    def test_resolution_repository_dispatch_build(self):
        assert self._run_resolution("repository_dispatch", "build", "") == "build"

    def test_resolution_repository_dispatch_deliver(self):
        assert self._run_resolution("repository_dispatch", "deliver", "") == "deliver"

    def test_resolution_repository_dispatch_build_newspaper(self):
        # build-newspaper is the on-demand record_id-driven path; BUILD_MODE
        # stays empty so build_for_users.py main() takes the BUILD_RECORD_ID
        # branch.
        assert self._run_resolution("repository_dispatch", "build-newspaper", "") == ""

    def test_resolution_schedule_build_cron(self):
        assert self._run_resolution("schedule", "", BUILD_CRON) == "build"

    def test_resolution_schedule_deliver_cron(self):
        assert self._run_resolution("schedule", "", DELIVER_CRON) == "deliver"

    def test_resolution_workflow_dispatch_is_empty(self):
        # workflow_dispatch (manual debug fire) leaves BUILD_MODE empty so
        # main() falls into the legacy run_scheduled() branch — we don't
        # want manual fires to silently treat themselves as scheduled work.
        assert self._run_resolution("workflow_dispatch", "", "") == ""

    def test_resolution_unknown_event_is_empty(self):
        assert self._run_resolution("push", "", "") == ""


class TestRecordIdValidationGate:
    """The `Validate record_id format` step runs only for the on-demand path.

    Before PR 2 it gated on `event_name == 'repository_dispatch'`. After PR 2
    we have three dispatch types — only `build-newspaper` carries a record_id
    in the client_payload. The other two would otherwise fail validation
    against an empty string.
    """

    def test_gates_on_build_newspaper_action(self):
        step = _find_step("Validate record_id format")
        condition = step.get("if", "")
        assert "repository_dispatch" in condition
        assert "build-newspaper" in condition, (
            "validate-record-id step must gate on event.action == 'build-newspaper' "
            "so build/deliver dispatches don't hit the regex check"
        )


# ─── Supabase migration workflow ─────────────────────────────────────


class TestSupabaseMigrateWorkflow:
    """The auto-deploy workflow is the response to the 2026-05-04 schema
    drift incident. Structural invariants we must preserve:

    - PR runs include the safety check + lint
    - Push-to-main runs the deploy job
    - Deploy uses `--linked` (against the prod project ref)
    - Concurrency is configured (no parallel pushes)
    - Required secrets are referenced by name (so missing secrets surface
      as a clear configuration issue, not silent skips)
    """

    def test_workflow_file_exists(self):
        assert MIGRATE_WORKFLOW.exists(), (
            "supabase-migrate.yml must exist — it's the deploy half of "
            "the schema-drift incident response"
        )

    def test_path_filter_targets_migrations(self):
        """PR + push triggers must filter on supabase/migrations/** so
        unrelated commits don't trip the workflow."""
        on = _on_block(MIGRATE_WORKFLOW)
        for trigger in ("pull_request", "push"):
            paths = on[trigger].get("paths", [])
            assert any("supabase/migrations" in p for p in paths), (
                f"{trigger} trigger must filter on supabase/migrations/**, "
                f"got {paths!r}"
            )

    def test_concurrency_group_serializes_pushes(self):
        data = _load(MIGRATE_WORKFLOW)
        concurrency = data.get("concurrency")
        assert concurrency, "workflow must declare a concurrency group"
        assert "supabase" in concurrency["group"].lower()
        # Aborting a half-applied migration is worse than waiting
        assert concurrency.get("cancel-in-progress") is False, (
            "cancel-in-progress must be false — aborting mid-migration "
            "leaves the DB in a partially-applied state"
        )

    def test_check_job_runs_only_on_pr(self):
        data = _load(MIGRATE_WORKFLOW)
        if_expr = data["jobs"]["check"].get("if", "")
        assert "pull_request" in if_expr

    def test_deploy_job_does_not_run_on_pr(self):
        data = _load(MIGRATE_WORKFLOW)
        if_expr = data["jobs"]["deploy"].get("if", "")
        assert "pull_request" not in if_expr or "!= 'pull_request'" in if_expr or "push" in if_expr, (
            "deploy job must not run on PR — only on push to main / dispatch"
        )

    def test_deploy_uses_linked_flag(self):
        """`--linked` is what tells the CLI to push against the project
        configured in `supabase link`. Without it we'd push to a sandbox."""
        data = _load(MIGRATE_WORKFLOW)
        steps = data["jobs"]["deploy"]["steps"]
        push_step = next(
            (s for s in steps if "Push" in s.get("name", "") and s.get("run")),
            None,
        )
        assert push_step is not None, "no `Push migrations` step found"
        assert "--linked" in push_step["run"], (
            "`supabase db push` must use --linked so it targets the prod "
            "project, not a local sandbox"
        )

    def test_deploy_references_required_secrets(self):
        """Missing secrets should surface as a clear configuration issue."""
        text = MIGRATE_WORKFLOW.read_text()
        for secret in ("SUPABASE_ACCESS_TOKEN", "SUPABASE_DB_PASSWORD"):
            assert f"secrets.{secret}" in text, (
                f"workflow must reference {secret} via secrets.{secret} so "
                "GitHub surfaces a missing-secret error if it isn't set"
            )

    def test_check_job_runs_safety_checker(self):
        data = _load(MIGRATE_WORKFLOW)
        steps = data["jobs"]["check"]["steps"]
        joined = "\n".join(s.get("run", "") for s in steps)
        assert "scripts/check_migrations.py" in joined, (
            "check job must run scripts/check_migrations.py — that's the "
            "single source of truth for the safety rules"
        )

    def test_deploy_job_runs_safety_checker_as_final_guard(self):
        """Even though the PR check covers this, run again on the merged
        commit so a force-pushed main can't bypass the rules."""
        data = _load(MIGRATE_WORKFLOW)
        steps = data["jobs"]["deploy"]["steps"]
        joined = "\n".join(s.get("run", "") for s in steps)
        assert "scripts/check_migrations.py" in joined, (
            "deploy job must run the safety checker as a final guard"
        )

    def test_setup_cli_pinned_to_sha(self):
        """All third-party actions in this repo are SHA-pinned. Match that."""
        text = MIGRATE_WORKFLOW.read_text()
        # supabase/setup-cli must appear with a 40-char hex SHA before the version comment
        import re
        for match in re.finditer(r"supabase/setup-cli@([^\s]+)", text):
            ref = match.group(1)
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (
                f"supabase/setup-cli must be SHA-pinned (got {ref!r}) — "
                "the rest of this repo's workflows pin to commit SHAs"
            )
