"""The CodeQL analysis: the wiring of the codeql job in ci.yml and of codeql.yml.

The analysis runs through the organisation's workflow, which proves itself
there. What can go wrong here is the call: a language left out, the two calls
drifting apart, a permission beyond the upload, a weekly run that is not
weekly, or a second category that would count every finding twice. The one
rule the configuration leaves out, the pin of every action, is held here in
its place, for the actions that are not the organisation's.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
WEEKLY = (ROOT / ".github" / "workflows" / "codeql.yml").read_text("utf-8")
CALL = "uses: benethos-hub/.github/.github/workflows/codeql.yml@main"
CONFIG_PATH = ".github/codeql/codeql-config.yml"
CONFIG = (ROOT / CONFIG_PATH).read_text("utf-8")
ORG = "benethos-hub/.github/"


def _job(workflow: str, name: str) -> str:
    return workflow.split(f"\n  {name}:\n", 1)[1].split("\n\n  ", 1)[0].rstrip()


def test_the_ci_job_calls_the_organisations_workflow_for_the_code_and_the_workflows():
    job = _job(CI, "codeql")
    assert CALL in job
    assert "languages: python,actions" in job


def test_the_weekly_workflow_makes_the_same_call():
    """One analysis in two places, so a change to one is a change to both."""
    assert _job(WEEKLY, "codeql") == _job(CI, "codeql")


def test_the_weekly_run_is_weekly_and_by_hand_only():
    on = WEEKLY.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.search(r'cron: "\d+ \d+ \* \* [0-6]"', on), "one weekday, once"
    assert "workflow_dispatch:" in on
    assert "push" not in on
    assert "pull_request" not in on


def test_the_upload_permission_is_granted_to_the_codeql_job_and_nowhere_else():
    assert "security-events: write" in _job(CI, "codeql")
    assert CI.count("security-events: write") == 1
    assert WEEKLY.count("security-events: write") == 1
    assert "contents: write" not in WEEKLY


def test_the_two_runs_share_the_default_category():
    """A category of their own would file the same findings twice."""
    assert "category:" not in _job(CI, "codeql")
    assert "category:" not in WEEKLY


def test_the_calls_read_the_configuration_file():
    """The weekly call is held equal above, so one assertion covers both."""
    assert f"config-file: {CONFIG_PATH}" in _job(CI, "codeql")


def test_the_configuration_leaves_out_the_decided_rules_and_nothing_else():
    excluded = re.findall(r"^\s+id: (\S+)$", CONFIG, re.M)
    assert excluded == ["actions/unpinned-tag"]
    assert "queries:" not in CONFIG, "the suite is the workflow's input"
    assert "paths-ignore" not in CONFIG, "every file is read"


def test_every_action_that_is_not_the_organisations_is_pinned_to_a_commit():
    """What the excluded rule would check, for the actions it was meant for."""
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in path.read_text("utf-8").splitlines():
            uses = re.search(r"uses: (\S+)", line)
            if uses is None or uses.group(1).startswith(ORG):
                continue
            assert re.search(r"@[0-9a-f]{40} # v\d", line), (
                f"{path.name}: {line.strip()}"
            )
