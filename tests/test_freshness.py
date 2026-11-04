"""The daily freshness check: the wiring of freshness.yml.

The check runs through the organisation's workflow and actions, which prove
themselves there. What can go wrong here is the call: a trigger that is not a
schedule, a permission beyond issues, an artifact the report does not expect, a
smoke run without the pause, or an exit code the action reads differently.
"""

from __future__ import annotations

import re
from pathlib import Path

import smoke

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "freshness.yml").read_text("utf-8")
ORG = "benethos-hub/.github/"


def _step(name: str) -> str:
    return WORKFLOW.split(f"- name: {name}\n", 1)[1].split("\n      - ", 1)[0]


def _job(name: str) -> str:
    return WORKFLOW.split(f"\n  {name}:\n", 1)[1].split("\n\n  ", 1)[0]


def test_it_runs_on_a_schedule_and_by_hand_only():
    on = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in on
    assert "workflow_dispatch:" in on
    assert "push" not in on
    assert "pull_request" not in on


def test_the_newest_job_is_the_organisations_with_the_smoke_run_as_the_check():
    step = _step("Test the newest versions allowed")
    assert f"uses: {ORG}actions/python/freshness-newest@main" in step
    assert "extras: dev" in step, "the test tools live in the dev extra"
    assert "check: uv run --frozen python tests/smoke.py --pause 1" in step


def test_the_artifact_is_named_as_the_report_expects():
    """freshness-<job>, named in extra-jobs, from the folder the action fills."""
    assert "findings: ${{ runner.temp }}/freshness/newest" in _step(
        "Test the newest versions allowed"
    )
    upload = _step("Leave the result for the report")
    assert "name: freshness-newest" in upload
    assert "path: ${{ runner.temp }}/freshness/newest" in upload


def test_the_report_is_the_organisations_and_knows_the_job():
    job = _job("freshness")
    assert f"uses: {ORG}.github/workflows/freshness.yml@main" in job
    assert "needs: newest" in job
    assert "extra-jobs: newest" in job
    assert "if: ${{ !cancelled() }}" in job, "a dead job is a line in the report"


def test_the_index_job_checks_the_published_release_with_the_smoke_run():
    job = _job("freshness")
    assert "index: true" in job
    assert "index-check: $FRESHNESS_PYTHON tests/smoke.py --pause 1" in job


def test_the_two_issues_have_titles_of_their_own():
    titles = re.findall(r"^\s+(?:issue-|alarm-)title: (.+)$", WORKFLOW, re.M)
    assert len(titles) == 2
    assert len(set(titles)) == 2


def test_a_rate_limit_is_the_exit_code_the_actions_read_as_no_verdict():
    """Both actions default to 3, so the workflow names no other code."""
    assert smoke.RATE_LIMITED == 3
    assert "rate-limit-exit-code" not in WORKFLOW


def test_the_runner_pauses_between_calls_to_yahoo():
    """It shares its address with everyone else on GitHub's runners."""
    assert WORKFLOW.count("tests/smoke.py --pause 1") == 2
    assert WORKFLOW.count("tests/smoke.py") == 2


def test_it_can_write_issues_and_nothing_else():
    assert "contents: write" not in WORKFLOW
    assert WORKFLOW.count("issues: write") == 1
