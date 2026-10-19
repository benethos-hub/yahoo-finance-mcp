"""The release workflow's guards, read from the workflow and run where they can be.

A mistake here shows only on a published release, when the image and the PyPI
upload already disagree, so the guards are held to what they promise.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import benethos_yahoo_finance_mcp

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "tag_matches_version.py"
WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text("utf-8")

_spec = importlib.util.spec_from_file_location(
    "ci_passed", ROOT / ".github" / "scripts" / "ci_passed.py"
)
assert _spec and _spec.loader
ci_passed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci_passed)


def _check(tag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={"GITHUB_REF_NAME": tag, "PYPROJECT": str(ROOT / "pyproject.toml")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_tag_that_is_the_package_version_passes():
    result = _check(f"v{benethos_yahoo_finance_mcp.__version__}")
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("tag", ["v99.0.0", "v0.0.1", "main", ""])
def test_any_other_tag_stops_the_release(tag):
    result = _check(tag)
    assert result.returncode == 1
    assert result.stdout.startswith("::error::Release tag")


@pytest.mark.parametrize(
    "job,first_build_step",
    [
        ("pypi-publish:", "uv build"),
        ("ghcr-publish:", "qemu"),
        ("mcp-registry-publish:", "mcp-publisher publish"),
        ("mcpb-bundle:", "build.py"),
    ],
)
def test_each_job_checks_the_tag_before_it_builds(job, first_build_step):
    body = WORKFLOW.split(job, 1)[1].split("\n  ghcr-publish:", 1)[0]
    assert body.index("tag_matches_version.py") < body.index(first_build_step)


def test_a_pre_release_leaves_latest_alone():
    [latest] = [line for line in WORKFLOW.splitlines() if "value=latest" in line]
    assert "!github.event.release.prerelease" in latest


def test_the_registry_entry_waits_for_both_packages():
    """The registry checks the README on PyPI and the label in the image when
    it takes the entry, so both have to be published first."""
    job = WORKFLOW.split("mcp-registry-publish:", 1)[1]
    assert "needs: [pypi-publish, ghcr-publish, mcpb-bundle]" in job


def test_the_bundle_checksum_is_filled_in_before_publishing():
    job = WORKFLOW.split("mcp-registry-publish:", 1)[1]
    assert job.index("fill_bundle_checksum.py") < job.index("mcp-publisher publish")


def test_a_refused_bundle_still_leaves_the_version_listed():
    """The registry takes an entry whole or not at all. After the retries the
    bundle is dropped and the rest published, and the job still fails."""
    step = WORKFLOW.split("- name: Publish server.json", 1)[1]
    retries = step.index("done")
    dropped = step.index("--drop")
    republished = step.index('./mcp-publisher publish "$entry"', dropped)
    assert retries < dropped < republished < step.index("exit 1", republished)


def test_the_bundle_is_attached_under_a_stable_name_too():
    """The README links releases/latest/download/<name>, which only resolves
    when every release carries a file of exactly that name."""
    job = WORKFLOW.split("mcpb-bundle:", 1)[1].split("\n  mcp-registry-publish:", 1)[0]
    upload = [line for line in job.splitlines() if "gh release upload" in line]
    assert upload and "benethos-yahoo-finance-mcp.mcpb" in upload[0]


def test_edge_is_built_from_main_only():
    job = WORKFLOW.split("ghcr-publish:", 1)[1]
    assert (
        "if: github.event_name == 'release' || github.ref == 'refs/heads/main'" in job
    )


# The gate in front of every upload: the release commit's CI run on main.


def _jobs() -> dict[str, str]:
    """Each job's name with its body, as far as the next job."""
    body = WORKFLOW.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


@pytest.mark.parametrize("job", ["pypi-publish", "ghcr-publish", "mcpb-bundle"])
def test_nothing_is_built_before_the_ci_gate(job):
    """The registry job needs these three, so it waits for the gate as well."""
    assert "needs: ci-passed" in _jobs()[job]


def test_the_ci_gate_may_read_the_runs():
    gate = _jobs()["ci-passed"]
    assert "actions: read" in gate
    assert "python3 .github/scripts/ci_passed.py" in gate


def _run(status: str, conclusion: str | None = None, created: str = "1") -> dict:
    return {
        "status": status,
        "conclusion": conclusion,
        "created_at": f"2026-10-19T10:0{created}:00Z",
        "html_url": f"https://example.invalid/run/{created}",
    }


def _gate(
    answers: list[list[dict]], **kwargs: Any
) -> tuple[int, list[str], list[float]]:
    """Run the gate against canned API answers, the last one repeating."""
    urls: list[str] = []
    slept: list[float] = []

    def fetch(url: str) -> dict:
        urls.append(url)
        return {"workflow_runs": answers[min(len(urls), len(answers)) - 1]}

    code = ci_passed.check(
        "benethos-hub/yahoo-finance-mcp",
        "abc1234def",
        fetch=fetch,
        sleep=slept.append,
        **kwargs,
    )
    return code, urls, slept


def test_a_green_run_on_main_lets_the_release_through():
    code, urls, slept = _gate([[_run("completed", "success")]])
    assert code == 0 and slept == []
    assert "head_sha=abc1234def" in urls[0]
    assert "event=push" in urls[0] and "branch=main" in urls[0]
    assert "/workflows/ci.yml/runs" in urls[0]


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out"])
def test_a_run_that_did_not_succeed_stops_the_release(conclusion, capsys):
    code, _, _ = _gate([[_run("completed", conclusion)]])
    assert code == 1
    assert capsys.readouterr().out.startswith("::error::CI on main ended")


def test_a_run_in_progress_is_waited_for():
    code, urls, slept = _gate(
        [[_run("queued")], [_run("in_progress")], [_run("completed", "success")]],
        interval=30,
    )
    assert code == 0 and len(urls) == 3 and slept == [30, 30]


def test_a_run_that_never_finishes_stops_the_release_after_the_wait(capsys):
    code, urls, _ = _gate([[_run("in_progress")]], wait_seconds=90, interval=30)
    assert code == 1 and len(urls) == 4
    assert "is still in_progress after 90 s" in capsys.readouterr().out


def test_a_commit_without_a_run_on_main_stops_soon(capsys):
    """A commit that never went into main gets no run, so the gate does not
    sit out the whole wait for one."""
    code, urls, _ = _gate([[]], wait_seconds=1800, interval=30, appear_seconds=60)
    assert code == 1 and len(urls) == 3
    assert "::error::No CI run on main" in capsys.readouterr().out


def test_the_newest_run_of_the_commit_decides():
    old_red = _run("completed", "failure", created="1")
    new_green = _run("completed", "success", created="2")
    older_green = new_green | {"created_at": "2026-10-19T09:00:00Z"}
    assert _gate([[old_red, new_green]])[0] == 0
    assert _gate([[older_green, old_red]])[0] == 1
