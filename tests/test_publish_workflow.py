"""The release workflow's wiring, read from the workflow.

The uploads themselves are the organisation's actions in benethos-hub/.github,
tested there. What stays here is which job calls which action, with what, on
which event and after what. A mistake here shows only on a published release,
when a version on PyPI can no longer be replaced.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text("utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
ACTIONS = "benethos-hub/.github/actions/publish/"


def _jobs() -> dict[str, str]:
    """Each job's name with its body, as far as the next job."""
    body = WORKFLOW.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def test_the_jobs_are_the_gate_the_uploads_and_the_registry():
    assert list(_jobs()) == [
        "ci-passed",
        "pypi-publish",
        "pypi-trial",
        "ghcr-publish",
        "mcpb-bundle",
        "mcp-registry",
    ]


@pytest.mark.parametrize(
    ("job", "action"),
    [
        ("pypi-publish", "pypi"),
        ("pypi-trial", "pypi"),
        ("ghcr-publish", "ghcr"),
        ("mcpb-bundle", "mcpb"),
        ("mcp-registry", "mcp-registry"),
    ],
)
def test_each_job_uploads_through_the_organisations_action(job, action):
    assert f"uses: {ACTIONS}{action}@main" in _jobs()[job]


# The gate in front of every upload: the release commit's CI run on main.


@pytest.mark.parametrize(
    "job", ["pypi-publish", "pypi-trial", "ghcr-publish", "mcpb-bundle"]
)
def test_nothing_is_built_before_the_ci_gate(job):
    """The registry job needs the uploads, so it waits for the gate as well."""
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


# PyPI: the upload on a release, the trial on a manual run.


def test_pypi_uploads_on_a_release_only_from_the_trusted_environment():
    """PyPI's Trusted Publisher trusts exactly the workflow file publish.yml
    and this environment. Renaming either means changing the publisher."""
    job = _jobs()["pypi-publish"]
    assert "if: github.event_name == 'release'\n" in job
    assert "name: pypi-benethos-yahoo-finance-mcp" in job
    assert "id-token: write" in job
    assert "dry-run" not in job


def test_the_pypi_trial_runs_by_hand_without_credentials():
    job = _jobs()["pypi-trial"]
    assert "if: github.event_name == 'workflow_dispatch'\n" in job
    assert "dry-run: true" in job
    assert "environment:" not in job
    assert "id-token" not in job


@pytest.mark.parametrize("job", ["pypi-publish", "pypi-trial"])
def test_the_wheel_must_carry_the_typing_marker(job):
    """Without py.typed every annotation of the package is ignored by type
    checkers, and nothing else would notice."""
    assert "wheel-contains: benethos_yahoo_finance_mcp/py.typed" in _jobs()[job]


# The image, the bundle and the registry entry.


def test_edge_is_built_from_main_only():
    job = _jobs()["ghcr-publish"]
    assert (
        "if: github.event_name == 'release' || github.ref == 'refs/heads/main'" in job
    )


def test_the_release_image_reuses_the_layers_of_the_ci_build():
    """The arm64 build in ci.yml names no cache scope, so buildx writes to
    buildkit, and the release reads from there."""
    job = _jobs()["ghcr-publish"]
    assert "image: benethos-yahoo-finance-mcp\n" in job
    assert "dockerfile: containers/images/yahoo-finance-mcp/Dockerfile" in job
    assert "cache-scope: buildkit" in job
    cache = re.findall(r"^\s+cache-(?:from|to): (.*)$", CI, re.M)
    assert cache == ["type=gha", "type=gha,mode=max"]


def test_the_bundle_is_staged_where_the_action_takes_it():
    job = _jobs()["mcpb-bundle"]
    assert "if: github.event_name == 'release'\n" in job
    assert (
        'uv run --no-project .github/publish/mcpb/build.py "$RUNNER_TEMP/bundle"'
        in (job)
    )
    assert "staged: ${{ runner.temp }}/bundle" in job


def test_the_registry_entry_waits_for_every_package():
    """The registry checks the README on PyPI, the label in the image and the
    bundle's checksum when it takes the entry, so all three come first, and a
    pre-release is not listed."""
    job = _jobs()["mcp-registry"]
    assert "needs: [pypi-publish, ghcr-publish, mcpb-bundle]" in job
    assert (
        "if: github.event_name == 'release' && !github.event.release.prerelease" in job
    )
    assert "id-token: write" in job
