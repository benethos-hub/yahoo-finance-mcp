"""The daily freshness check: its report and its wiring.

The check itself only proves itself on GitHub, on a schedule. What can go wrong
quietly is here: a report that stays empty, or an alarm that closes on a Yahoo
outage.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "freshness.yml").read_text("utf-8")


def _load_script():
    path = ROOT / ".github" / "scripts" / "freshness_report.py"
    spec = importlib.util.spec_from_file_location("freshness_report", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


report = _load_script()


def _lock(**versions: str) -> str:
    """A lockfile with mcp as the one direct dependency, h11 under it, pytest in dev."""
    packages = {"mcp": "2.3.0", "h11": "1.0.0", "pytest": "9.0.0", **versions}
    text = [
        '[[package]]\nname = "benethos-yahoo-finance-mcp"\nversion = "1.0.0"\n'
        'source = { editable = "." }\ndependencies = [{ name = "mcp" }]\n'
        '[package.optional-dependencies]\ndev = [{ name = "pytest" }]\n'
    ]
    for name, version in packages.items():
        deps = 'dependencies = [{ name = "h11" }]\n' if name == "mcp" else ""
        text.append(f'[[package]]\nname = "{name}"\nversion = "{version}"\n{deps}')
    return "\n".join(text)


BEFORE = report.load_lock(_lock())


def test_the_runtime_set_leaves_the_dev_extra_out():
    assert BEFORE.direct == {"mcp"}
    assert BEFORE.runtime == {"mcp", "h11"}


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("2.3.0", "3.0.0", "major"),
        ("2.3.0", "2.4.0", "minor"),
        ("2.3.0", "2.3.1", "patch"),
        ("2.9.0.post0", "2.9.0.post1", "patch"),
        ("6.1", "6.1.3", "patch"),
        (None, "1.0.0", "new"),
    ],
)
def test_how_far_a_version_moved(old, new, expected):
    assert report.kind(old, new) == expected


# --- alarm -----------------------------------------------------------------


def test_the_alarm_names_the_step_and_what_moved():
    after = report.load_lock(_lock(mcp="2.3.1"))
    text = report.alarm(BEFORE, after, "failure", "success")
    assert "- Tests: failure" in text
    assert "| `mcp` | 2.3.0 | 2.3.1 | patch |" in text


def test_a_transitive_package_is_named_too_it_may_be_the_cause():
    after = report.load_lock(_lock(h11="1.0.1"))
    assert "`h11`" in report.alarm(BEFORE, after, "success", "failure")


def test_no_alarm_when_both_steps_pass():
    after = report.load_lock(_lock(mcp="2.3.1"))
    assert report.alarm(BEFORE, after, "success", "success") == ""


def test_no_alarm_when_nothing_moved():
    """The versions are then the lockfile's, so no new version can be the cause."""
    assert report.alarm(BEFORE, BEFORE, "failure", "failure") == ""


# --- news ------------------------------------------------------------------

OUTDATED = """\
benethos-yahoo-finance-mcp v1.0.0
├── mcp v2.3.1 (latest: v2.4.0)
│   └── h11 v1.0.0
└── pytest v9.0.0 (extra: dev) (latest: v9.1.0)
"""


def test_news_shows_a_direct_patch_that_reaches_users_and_how_it_did():
    after = report.load_lock(_lock(mcp="2.3.1"))
    text = report.news(BEFORE, after, "", "success", "failure")
    assert "| `mcp` | 2.3.0 | 2.3.1 | patch | yes | success / failure |" in text


def test_news_shows_a_release_past_the_bound_as_unchecked():
    after = report.load_lock(_lock(mcp="2.3.1"))
    text = report.news(BEFORE, after, OUTDATED, "success", "success")
    assert (
        "| `mcp` | 2.3.1 | 2.4.0 | minor | no, past its bound | not checked |" in text
    )


def test_news_leaves_development_tools_out():
    after = report.load_lock(_lock(pytest="9.0.1"))
    text = report.news(BEFORE, after, OUTDATED, "success", "success")
    assert "pytest" not in text


def test_news_names_a_transitive_major():
    after = report.load_lock(_lock(h11="2.0.0"))
    text = report.news(BEFORE, after, "", "success", "success")
    assert "| `h11` | 1.0.0 | 2.0.0 | major | yes |" in text


def test_news_only_counts_a_transitive_minor_or_patch():
    after = report.load_lock(_lock(mcp="2.3.1", h11="1.0.1"))
    text = report.news(BEFORE, after, "", "success", "success")
    assert "`h11`" not in text
    assert "1 more transitive" in text


def test_a_transitive_patch_alone_does_not_open_the_issue():
    after = report.load_lock(_lock(h11="1.0.1"))
    assert report.news(BEFORE, after, "", "success", "success") == ""


def test_nothing_new_closes_the_issue():
    assert report.news(BEFORE, BEFORE, "", "success", "success") == ""


def test_the_command_line_writes_the_report(tmp_path, capsys):
    before, after, outdated = (tmp_path / n for n in ("a", "b", "c"))
    before.write_text(_lock(), "utf-8")
    after.write_text(_lock(mcp="2.3.1"), "utf-8")
    outdated.write_text("", "utf-8")
    code = report.main(
        [
            "alarm",
            f"--before={before}",
            f"--after={after}",
            f"--outdated={outdated}",
            "--tests=failure",
            "--smoke=success",
        ]
    )
    assert code == 0
    assert "`mcp`" in capsys.readouterr().out


# --- the workflow ----------------------------------------------------------


def _step(name: str) -> str:
    return WORKFLOW.split(f"- name: {name}\n", 1)[1].split("\n      - ", 1)[0]


def test_it_runs_on_a_schedule_and_by_hand_only():
    on = WORKFLOW.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    assert "schedule:" in on
    assert "workflow_dispatch:" in on
    assert "push" not in on
    assert "pull_request" not in on


def test_a_failure_of_both_leaves_the_alarm_alone():
    """Yahoo being down must not close an open alarm with an empty report."""
    assert "if: needs.locked.result == 'success'" in _step("Keep the alarm issue")


def test_the_newest_job_runs_after_a_red_locked_one():
    assert "if: ${{ !cancelled() }}" in WORKFLOW


def test_it_can_write_issues_and_nothing_else():
    assert "contents: write" not in WORKFLOW
    assert WORKFLOW.count("issues: write") == 1


def test_a_red_step_still_reaches_the_reports():
    for step in ("Tests", "Smoke run against Yahoo\n        id: smoke"):
        body = WORKFLOW.split(f"- name: {step}", 1)[1].split("\n      - ", 1)[0]
        assert "continue-on-error: true" in body
