"""The release workflow's guards, read from the workflow and run where they can be.

A mistake here shows only on a published release, when the image and the PyPI
upload already disagree, so the guards are held to what they promise.
"""

from __future__ import annotations

import re
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


def test_the_ci_gate_is_the_organisations_and_may_read_the_runs():
    """A reusable workflow gets no more rights than its calling job grants."""
    gate = _jobs()["ci-passed"]
    assert (
        "uses: benethos-hub/.github/.github/workflows/python-release-ci-passed.yml@"
        in gate
    )
    assert "actions: read" in gate
    assert "audit: true" in gate
