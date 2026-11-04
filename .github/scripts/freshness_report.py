"""What the daily freshness check reports, as Markdown for an issue.

``uv lock --upgrade`` moves every package as far as pyproject.toml allows, which
is what the auto-update extension and uvx install. ``uv tree --outdated`` then
names what lies past that. This compares the two lockfiles and reads that list:

    alarm  the newest versions allowed fail, so one of them is the likely cause
    news   newer versions exist, whether they reach anyone, and how they did

It prints nothing when there is nothing to report, which closes the issue. Only
versions and the outcome of a step go in, since the issue is public.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT = "benethos-yahoo-finance-mcp"
_OUTDATED = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])? v(\S+) .*\(latest: v([^)]+)\)"
)


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
    or ruff is nobody's news here.
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


def past_the_bound(outdated: str, after: Lock) -> list[tuple[str, str, str]]:
    """Every package of a user's installation with a release it cannot reach."""
    found: dict[str, tuple[str, str]] = {}
    for line in outdated.splitlines():
        match = _OUTDATED.search(line)
        if match and normalized(match[1]) in after.runtime:
            found[normalized(match[1])] = (match[2], match[3])
    return [(name, *found[name]) for name in sorted(found)]


def alarm(before: Lock, after: Lock, tests: str, smoke: str) -> str:
    """The report when a step failed on versions that differ from the lockfile.

    With nothing moved the versions are the lockfile's, and a failure there says
    something about Yahoo or the code, not about a new version.
    """
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


def news(before: Lock, after: Lock, outdated: str, tests: str, smoke: str) -> str:
    """The report of newer versions, the direct ones and every major by name.

    A transitive minor or patch only counts. There are about as many of those as
    days, and the issue would never close.
    """
    rows: list[str] = []
    others = 0
    checked = f"{tests} / {smoke}"

    def row(name: str, old: str | None, new: str, reaches: str, status: str) -> None:
        nonlocal others
        change = kind(old, new)
        if name in after.direct or change == "major":
            rows.append(
                f"| `{name}` | {old or '-'} | {new} | {change} | {reaches} | {status} |"
            )
        else:
            others += 1

    for name, old, new in moved(before, after):
        row(name, old, new, "yes", checked)
    for name, old, new in past_the_bound(outdated, after):
        row(name, old, new, "no, past its bound", "not checked")
    if not rows:
        return ""
    lines = [
        "Newer versions than the ones in `uv.lock`:",
        "",
        "| Package | Now | Newest | Kind | Reaches users | Tests / smoke |",
        "|---|---|---|---|---|---|",
        *rows,
    ]
    if others:
        lines += ["", f"{others} more transitive, each a minor or a patch."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", choices=["alarm", "news"])
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--outdated", type=Path, required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--smoke", required=True)
    args = parser.parse_args(argv)
    before = load_lock(args.before.read_text("utf-8"))
    after = load_lock(args.after.read_text("utf-8"))
    if args.report == "alarm":
        text = alarm(before, after, args.tests, args.smoke)
    else:
        outdated = args.outdated.read_text("utf-8")
        text = news(before, after, outdated, args.tests, args.smoke)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
