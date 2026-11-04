"""The daily report of what is pinned: the wiring of pins.yml.

The report itself lives in the organisation's reusable workflow and proves
itself there. What can go wrong here is the call: a trigger that is not a
schedule, a permission beyond issues, or an issue title that collides with
the two of freshness.yml, which would make the two workflows close each
other's issue.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PINS = (WORKFLOWS / "pins.yml").read_text("utf-8")
FRESHNESS = (WORKFLOWS / "freshness.yml").read_text("utf-8")


def _titles(workflow: str) -> list[str]:
    return re.findall(r"^\s+(?:issue-)?title: (.+)$", workflow, re.M)


def test_it_runs_on_a_schedule_and_by_hand_only():
    on = PINS.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in on
    assert "workflow_dispatch:" in on
    assert "push" not in on
    assert "pull_request" not in on


def test_it_calls_the_organisations_report():
    assert "uses: benethos-hub/.github/.github/workflows/freshness.yml@main" in PINS


def test_it_can_write_issues_and_nothing_else():
    assert "contents: write" not in PINS
    assert PINS.count("issues: write") == 1


def test_its_issue_is_not_one_of_the_freshness_issues():
    """One title, one issue: a shared title would be closed by the other workflow."""
    titles = _titles(PINS)
    assert len(titles) == 1
    assert titles[0] not in _titles(FRESHNESS)


def test_the_two_daily_workflows_do_not_start_together():
    cron = re.compile(r'cron: "([^"]+)"')
    assert cron.search(PINS).group(1) != cron.search(FRESHNESS).group(1)
