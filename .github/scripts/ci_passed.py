"""Fail a release whose commit has no green CI run on main.

A version on PyPI cannot be replaced, and nothing in the release itself runs
the tests. The release is cut from a merge commit on main, and the push of that
commit to main ran the full CI: every required check, the whole matrix and both
audits. This waits for that run and passes only when it succeeded. A commit
that never reached main has no such run and stops the release as well. Run
first in publish.yml, every other job needs it.

GITHUB_REPOSITORY and GITHUB_SHA come from the runner, GITHUB_TOKEN needs
actions: read. CI_WAIT_SECONDS bounds the wait for a run still in progress.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable
from typing import Any

Fetch = Callable[[str], dict[str, Any]]


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result: dict[str, Any] = json.load(response)
        return result


def check(
    repository: str,
    sha: str,
    fetch: Fetch = fetch_json,
    wait_seconds: float = 1800,
    interval: float = 30,
    sleep: Callable[[float], None] = time.sleep,
    appear_seconds: float = 300,
) -> int:
    """0 once the newest CI run of a push to main for ``sha`` succeeded.

    A run still in progress is waited for up to ``wait_seconds``. A run that
    does not exist at all is given ``appear_seconds`` to show up, since a push
    lists its run within seconds and a commit that never reached main never
    gets one.
    """
    url = (
        f"https://api.github.com/repos/{repository}/actions/workflows/ci.yml/runs"
        f"?head_sha={sha}&event=push&branch=main&per_page=10"
    )
    waited = 0.0
    while True:
        runs = fetch(url).get("workflow_runs", [])
        # The newest run for the commit. A re-run keeps its run and only
        # raises run_attempt, so a run created later is a new push.
        run = max(runs, key=lambda r: r["created_at"], default=None)
        if run is not None and run["status"] == "completed":
            if run["conclusion"] == "success":
                print(f"CI passed on main for {sha[:7]}: {run['html_url']}")
                return 0
            print(
                f"::error::CI on main ended {run['conclusion']} for {sha[:7]}: "
                f"{run['html_url']}. Fix it on main and release from a green commit."
            )
            return 1
        if run is None and waited >= min(appear_seconds, wait_seconds):
            print(
                f"::error::No CI run on main for {sha[:7]}. A release is cut "
                "from a commit that went through a pull request into main."
            )
            return 1
        if run is not None and waited >= wait_seconds:
            print(
                f"::error::CI on main for {sha[:7]} is still {run['status']} "
                f"after {wait_seconds:.0f} s: {run['html_url']}"
            )
            return 1
        state = "no run yet" if run is None else run["status"]
        print(f"CI on main for {sha[:7]}: {state}, checking again in {interval:.0f} s")
        sleep(interval)
        waited += interval


def main() -> int:
    return check(
        os.environ["GITHUB_REPOSITORY"],
        os.environ["GITHUB_SHA"],
        wait_seconds=float(os.environ.get("CI_WAIT_SECONDS", "1800")),
    )


if __name__ == "__main__":
    sys.exit(main())
