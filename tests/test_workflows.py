"""Tests for GitHub Actions workflow files.

These guard against silent regressions in build/delivery infrastructure
that we can't reach from Python unit tests.
"""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-newspaper.yml"


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


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
