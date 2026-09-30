"""The release workflow's guards, read from the workflow and run where they can be.

A mistake here shows only on a published release, when the image and the PyPI
upload already disagree, so the guards are held to what they promise.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import benethos_yahoo_finance_mcp

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "tag_matches_version.py"
WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text("utf-8")


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
    "job,first_build_step", [("pypi-publish:", "uv build"), ("ghcr-publish:", "qemu")]
)
def test_each_job_checks_the_tag_before_it_builds(job, first_build_step):
    body = WORKFLOW.split(job, 1)[1].split("\n  ghcr-publish:", 1)[0]
    assert body.index("tag_matches_version.py") < body.index(first_build_step)


def test_a_pre_release_leaves_latest_alone():
    [latest] = [line for line in WORKFLOW.splitlines() if "value=latest" in line]
    assert "!github.event.release.prerelease" in latest


def test_edge_is_built_from_main_only():
    job = WORKFLOW.split("ghcr-publish:", 1)[1]
    assert (
        "if: github.event_name == 'release' || github.ref == 'refs/heads/main'" in job
    )
