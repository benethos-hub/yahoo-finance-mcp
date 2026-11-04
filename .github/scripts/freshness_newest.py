"""What the job ``newest`` of freshness.yml leaves for the organisation's report.

``uv lock --upgrade`` moves every package as far as pyproject.toml allows, which
is what the auto-update extension and uvx install. The job runs the tests and the
smoke test on those versions, after a smoke run on the locked ones, and this
turns the outcomes into the artifact ``actions/freshness/report/FORMAT.md`` of
benethos-hub/.github describes:

    status.json   ``ok`` when the run says something about the versions,
                  ``inconclusive`` when it does not: Yahoo refused the locked
                  versions too, rate-limited the run, or nothing moved and a
                  step still failed. Every status names the alarm issue.
    section.md    only when the newest versions fail: which step, and what moved
                  against uv.lock, so one of those is the likely cause.

An ``ok`` without a section closes the alarm issue. An ``inconclusive`` leaves it
as it was and is a line in the pins report. Only versions and the outcome of a
step go in, since the issues are public.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT = "benethos-yahoo-finance-mcp"


@dataclass(frozen=True)
class Lock:
    versions: dict[str, str]
    direct: frozenset[str]
    runtime: frozenset[str]


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_lock(text: str) -> Lock:
    """A lockfile's versions, and which packages a user of the server gets.

    The project's ``dependencies`` leave its ``dev`` extra out, so a new pytest
    or ruff is nobody's alarm here.
    """
    packages = {normalized(p["name"]): p for p in tomllib.loads(text)["package"]}
    direct = [normalized(d["name"]) for d in packages[PROJECT].get("dependencies", [])]
    runtime: set[str] = set()
    todo = list(direct)
    while todo:
        name = todo.pop()
        if name in runtime or name not in packages:
            continue
        runtime.add(name)
        todo += [normalized(d["name"]) for d in packages[name].get("dependencies", [])]
    return Lock(
        versions={n: p["version"] for n, p in packages.items() if "version" in p},
        direct=frozenset(direct),
        runtime=frozenset(runtime),
    )


def kind(old: str | None, new: str) -> str:
    """How far a version moved, ``new`` for a package that was not there."""
    if old is None:
        return "new"
    before = [int(part) for part in re.findall(r"\d+", old)] + [0, 0]
    after = [int(part) for part in re.findall(r"\d+", new)] + [0, 0]
    if before[0] != after[0]:
        return "major"
    return "minor" if before[1] != after[1] else "patch"


def moved(before: Lock, after: Lock) -> list[tuple[str, str | None, str]]:
    """Every package of a user's installation the upgrade moved, by name."""
    return [
        (name, before.versions.get(name), after.versions[name])
        for name in sorted(after.runtime)
        if name in after.versions and before.versions.get(name) != after.versions[name]
    ]


def verdict(before: Lock, after: Lock, locked: str, tests: str, smoke: str) -> str:
    """``ok`` when the run says something about the newest versions.

    ``inconclusive`` when it does not: the locked versions failed or were
    rate-limited too, so Yahoo or the runner is the matter, the newest run was
    rate-limited, or nothing moved and a step still failed, which is then the
    code or Yahoo and not a version.
    """
    if locked != "success" or smoke == "rate-limited":
        return "inconclusive"
    failed = tests == "failure" or smoke == "failure"
    if failed and not moved(before, after):
        return "inconclusive"
    return "ok"


def section(before: Lock, after: Lock, tests: str, smoke: str) -> str:
    """The alarm's prose when a step failed on versions that differ from the
    lockfile, empty otherwise."""
    changes = moved(before, after)
    if not changes or (tests != "failure" and smoke != "failure"):
        return ""
    lines = [
        "The newest versions pyproject.toml allows fail, while the versions in "
        "`uv.lock` pass. The auto-update extension and `uvx` install these, so "
        "their users may be affected.",
        "",
        f"- Tests: {tests}",
        f"- Smoke run against Yahoo: {smoke}",
        "",
        "| Package | In `uv.lock` | Newest allowed | Kind |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| `{name}` | {old or '-'} | {new} | {kind(old, new)} |"
        for name, old, new in changes
    ]
    return "\n".join(lines) + "\n"


def write(
    out: Path, before: Lock, after: Lock, locked: str, tests: str, smoke: str
) -> str:
    """The artifact in ``out``: status.json always, section.md when there is
    prose. Returns the verdict."""
    out.mkdir(parents=True, exist_ok=True)
    result = verdict(before, after, locked, tests, smoke)
    status = {"result": result, "checked": len(after.runtime), "issue": "alarm"}
    (out / "status.json").write_text(json.dumps(status) + "\n", "utf-8")
    text = section(before, after, tests, smoke) if result == "ok" else ""
    if text:
        (out / "section.md").write_text(text, "utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--before", type=Path, required=True, help="uv.lock as committed"
    )
    parser.add_argument(
        "--after", type=Path, required=True, help="uv.lock after the upgrade"
    )
    parser.add_argument(
        "--locked", required=True, help="smoke run on the locked versions"
    )
    parser.add_argument("--tests", required=True, help="outcome of the tests")
    parser.add_argument(
        "--smoke", required=True, help="smoke run on the newest versions"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="folder of the artifact"
    )
    args = parser.parse_args(argv)
    before = load_lock(args.before.read_text("utf-8"))
    after = load_lock(args.after.read_text("utf-8"))
    result = write(args.out, before, after, args.locked, args.tests, args.smoke)
    print(f"newest: {result}, {len(moved(before, after))} runtime packages moved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
