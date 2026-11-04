"""The daily freshness check: the artifact of the job newest, and the wiring.

The check itself only proves itself on GitHub, on a schedule. What can go wrong
quietly is here: an alarm that closes on a Yahoo outage, a status the
organisation's report would misread, a call that does not name the job.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import smoke

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "freshness.yml").read_text("utf-8")


def _load_script():
    path = ROOT / ".github" / "scripts" / "freshness_newest.py"
    spec = importlib.util.spec_from_file_location("freshness_newest", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


newest = _load_script()


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


BEFORE = newest.load_lock(_lock())
MOVED = newest.load_lock(_lock(mcp="2.3.1"))


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
    assert newest.kind(old, new) == expected


# --- the section, the alarm's prose ---------------------------------------


def test_the_section_names_the_step_and_what_moved():
    text = newest.section(BEFORE, MOVED, "failure", "success")
    assert "- Tests: failure" in text
    assert "| `mcp` | 2.3.0 | 2.3.1 | patch |" in text


def test_a_transitive_package_is_named_too_it_may_be_the_cause():
    after = newest.load_lock(_lock(h11="1.0.1"))
    assert "`h11`" in newest.section(BEFORE, after, "success", "failure")


def test_no_section_when_both_steps_pass():
    assert newest.section(BEFORE, MOVED, "success", "success") == ""


def test_no_section_when_nothing_moved():
    """The versions are then the lockfile's, so no new version can be the cause."""
    assert newest.section(BEFORE, BEFORE, "failure", "failure") == ""


def test_a_dev_package_alone_is_no_alarm():
    after = newest.load_lock(_lock(pytest="9.0.1"))
    assert newest.section(BEFORE, after, "failure", "success") == ""


# --- the verdict, what the report may do with the alarm issue --------------


@pytest.mark.parametrize(
    ("locked", "tests", "smoke_result", "expected"),
    [
        ("success", "success", "success", "ok"),
        ("success", "failure", "success", "ok"),
        ("success", "success", "failure", "ok"),
        # Yahoo refused the locked versions too: not the versions' doing.
        ("failure", "failure", "failure", "inconclusive"),
        ("rate-limited", "success", "success", "inconclusive"),
        # A limited run says nothing about these versions.
        ("success", "success", "rate-limited", "inconclusive"),
    ],
)
def test_the_verdict_after_a_move(locked, tests, smoke_result, expected):
    assert newest.verdict(BEFORE, MOVED, locked, tests, smoke_result) == expected


def test_a_failure_without_a_move_proves_nothing_about_versions():
    """The code or Yahoo, then, and the alarm issue must stay as it was."""
    assert (
        newest.verdict(BEFORE, BEFORE, "success", "failure", "success")
        == "inconclusive"
    )
    assert newest.verdict(BEFORE, BEFORE, "success", "success", "success") == "ok"


# --- the artifact ----------------------------------------------------------


def _artifact(tmp_path, after, locked, tests, smoke_result):
    out = tmp_path / "newest"
    result = newest.write(out, BEFORE, after, locked, tests, smoke_result)
    status = json.loads((out / "status.json").read_text("utf-8"))
    section = out / "section.md"
    return result, status, section.read_text("utf-8") if section.is_file() else None


def test_the_artifact_addresses_the_alarm_and_counts_the_runtime_packages(tmp_path):
    result, status, section = _artifact(
        tmp_path, MOVED, "success", "success", "success"
    )
    assert result == "ok"
    assert status == {"result": "ok", "checked": 2, "issue": "alarm"}
    assert section is None, "nothing to say closes the alarm issue"


def test_a_failure_on_moved_versions_leaves_a_section(tmp_path):
    result, status, section = _artifact(
        tmp_path, MOVED, "success", "failure", "success"
    )
    assert result == "ok"
    assert status["result"] == "ok"
    assert section is not None
    assert "| `mcp` | 2.3.0 | 2.3.1 | patch |" in section


def test_an_inconclusive_run_leaves_no_section(tmp_path):
    """A section would reach the alarm file, which must stay empty then."""
    result, status, section = _artifact(
        tmp_path, MOVED, "success", "failure", "rate-limited"
    )
    assert result == "inconclusive"
    assert status["result"] == "inconclusive"
    assert section is None


def test_the_command_line_writes_the_artifact(tmp_path, capsys):
    before, after = tmp_path / "a", tmp_path / "b"
    before.write_text(_lock(), "utf-8")
    after.write_text(_lock(mcp="2.3.1"), "utf-8")
    out = tmp_path / "out" / "newest"
    code = newest.main(
        [
            f"--before={before}",
            f"--after={after}",
            "--locked=success",
            "--tests=failure",
            "--smoke=success",
            f"--out={out}",
        ]
    )
    assert code == 0
    assert (out / "status.json").is_file()
    assert "`mcp`" in (out / "section.md").read_text("utf-8")
    assert "newest: ok, 1 runtime packages moved" in capsys.readouterr().out


# --- the workflow ----------------------------------------------------------


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


def test_the_report_is_the_organisations_and_knows_the_job():
    job = _job("freshness")
    assert "uses: benethos-hub/.github/.github/workflows/freshness.yml@main" in job
    assert "needs: newest" in job
    assert "extra-jobs: newest" in job
    assert "if: ${{ !cancelled() }}" in job, "a dead job is a line in the report"


def test_the_artifact_is_named_as_the_report_expects():
    """freshness-<job>, named in extra-jobs, from the folder the script fills."""
    assert "name: freshness-newest" in _step("Leave the result for the report")
    assert '--out "$RUNNER_TEMP/freshness/newest"' in _step(
        "Write the result for the report"
    )
    assert "path: ${{ runner.temp }}/freshness/newest" in WORKFLOW


def test_the_two_issues_have_titles_of_their_own():
    titles = re.findall(r"^\s+(?:issue-|alarm-)title: (.+)$", WORKFLOW, re.M)
    assert len(titles) == 2
    assert len(set(titles)) == 2


def test_both_smoke_steps_tell_a_rate_limit_from_a_failure():
    for step_id in ("locked", "smoke"):
        step = WORKFLOW.split(f"id: {step_id}", 1)[1].split("\n      - ", 1)[0]
        assert f"{smoke.RATE_LIMITED}) result=rate-limited" in step
        assert "*) result=failure" in step
        assert 'echo "result=$result" >> "$GITHUB_OUTPUT"' in step
    write = _step("Write the result for the report")
    assert "LOCKED: ${{ steps.locked.outputs.result }}" in write
    assert "TESTS: ${{ steps.tests.outcome }}" in write
    assert "SMOKE: ${{ steps.smoke.outputs.result }}" in write


def test_a_red_step_still_reaches_the_artifact():
    assert "continue-on-error: true" in _step("Tests")
    assert "|| code=$?" in _step("Smoke run on the locked versions")
    assert "|| code=$?" in _step("Smoke run on the newest versions")


def test_the_runner_pauses_between_calls_to_yahoo():
    """It shares its address with everyone else on GitHub's runners."""
    assert WORKFLOW.count("python tests/smoke.py --pause 1") == 2
    assert WORKFLOW.count("tests/smoke.py") == 2


def test_it_can_write_issues_and_nothing_else():
    assert "contents: write" not in WORKFLOW
    assert WORKFLOW.count("issues: write") == 1
