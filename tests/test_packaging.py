"""Guard the PEP 561 marker that makes the annotations reach installers.

Every module here is annotated and mypy runs as a CI gate, but none of that
reaches anyone who installs the package. A type checker treats an installed
package without a ``py.typed`` marker as untyped and skips it entirely, however
complete the annotations are. Removing the file breaks downstream type checking
without breaking a single test, an import or the build, so the loss would be
silent.

This covers the file in the source tree. Whether it survives into the built
wheel is a separate question, checked in the release workflow, because a file
that exists is not the same as a file that ships.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

import pytest

import benethos_yahoo_finance_mcp

PACKAGE_DIR = Path(benethos_yahoo_finance_mcp.__file__).resolve().parent
MARKER = PACKAGE_DIR / "py.typed"


def test_py_typed_marker_sits_next_to_the_code() -> None:
    """PEP 561 looks for the marker inside the package directory itself."""
    assert MARKER.is_file(), (
        f"{MARKER} is missing. Without it a type checker skips this package "
        "entirely and every annotation in it goes unused."
    )


def test_py_typed_marker_is_empty() -> None:
    """PEP 561 defines no content for the file, so it stays empty."""
    assert MARKER.read_bytes() == b"", (
        "py.typed is a marker, not a configuration file. Content in it is at "
        "best ignored and at worst misleading."
    )


# The documentation quotes the current version in a handful of places, as an
# example to copy. Three of them were missed during a release and found only by
# sweeping the repository a second time, which is not a method. A reader
# copying a stale example pins the version before the one they are reading
# about, which is worse than no example.
#
# The failure mode here is forgetting, not difficulty, so this asserts rather
# than generates: nothing is rewritten, the suite simply goes red until the
# examples agree with the package.
REPO = PACKAGE_DIR.parent.parent
PYPROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


# Every check in this file compares against `__version__`, which is read from
# the *installed* metadata, not from pyproject.toml. A bump of pyproject.toml
# without `uv sync` leaves the previous version installed, and the checks
# below then call the README up to date and pyproject's new version nowhere,
# or the other way round. This names the actual cause.
def test_installed_version_is_the_one_in_pyproject():
    declared = PYPROJECT["project"]["version"]
    installed = benethos_yahoo_finance_mcp.__version__
    assert installed == declared, (
        f"pyproject.toml says {declared}, the installed package says {installed}. "
        "Run `uv sync --extra dev` before reading anything else this file reports."
    )


VERSION_EXAMPLES = (
    # An exact pin of the distribution, as the install section shows it.
    ("README.md", r"benethos-yahoo-finance-mcp==(\d+\.\d+\.\d+)"),
    # An exact image tag in backticks. `:0.4` names a minor line on purpose and
    # has only two components, so it is not matched.
    ("README.md", r"`:(\d+\.\d+\.\d+)`"),
    # The version the production compose template starts with.
    ("containers/production/.env.example", r"(?m)^YAHOO_FINANCE_MCP_VERSION=(\S+)$"),
    # The version people are asked to report in a bug.
    (".github/ISSUE_TEMPLATE/bug_report.yml", r'placeholder: "(\d+\.\d+\.\d+)"'),
    # The MCP Registry entry, its own version and the PyPI package's. The
    # image tag in it is caught by the sweep below.
    (".github/publish/mcp-registry/server.json", r'"version": "(\d+\.\d+\.\d+)"'),
)

# The minor-line tag, `:0.5`, which follows patch releases rather than naming
# one. It is right for it to stay put across a patch bump and wrong for it to
# stay put across a minor one, so it is compared against the first two
# components instead of the whole version. Missed by eye on the 0.5.0 bump,
# where the README and the compose file of the day both still said `:0.4`.
MINOR_LINE_EXAMPLES = (("README.md", r"`:(\d+\.\d+)`"),)


# The lists above name the places known today, and a new example anywhere else,
# SPECS.md, a comment, a file that does not exist yet, would not be on them.
# The 0.7.1 bump needed a sweep by hand to rule that out. This sweep reads every
# text file of the repository for the shapes a copyable pin takes, so the next
# example is checked from the day it is written. The changelog is history and
# quotes every old version on purpose.
PIN_SHAPES = (
    re.compile(r"benethos-yahoo-finance-mcp==(\d+\.\d+\.\d+)"),
    re.compile(r"yahoo-finance-mcp:(\d+\.\d+\.\d+)\b"),
    re.compile(r"`:(\d+\.\d+\.\d+)`"),
    re.compile(r"YAHOO_FINANCE_MCP_VERSION=(\d+\.\d+\.\d+)"),
)
_TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".toml", ".py", ".txt", ".example", ".json"}
_SKIP_DIRS = {"build", "dist", "htmlcov", "node_modules", "__pycache__"}
_HISTORY = {"CHANGELOG.md"}


def _repository_text_files() -> list[Path]:
    """Every text file in the checkout, without virtualenvs, caches or builds."""
    files = []
    for root, dirs, names in os.walk(REPO):
        # Pruned in place, so a virtualenv is never walked at all.
        dirs[:] = [
            d
            for d in dirs
            if d not in _SKIP_DIRS
            and not d.endswith(".egg-info")
            and (not d.startswith(".") or d == ".github")
        ]
        for name in names:
            path = Path(root) / name
            if name in _HISTORY:
                continue
            if path.suffix in _TEXT_SUFFIXES or name == "Dockerfile":
                files.append(path)
    return files


def test_no_stale_version_pin_anywhere_in_the_repository():
    current = benethos_yahoo_finance_mcp.__version__
    found: dict[str, set[str]] = {}
    for path in _repository_text_files():
        text = path.read_text(encoding="utf-8")
        for shape in PIN_SHAPES:
            for version in shape.findall(text):
                found.setdefault(version, set()).add(path.relative_to(REPO).as_posix())

    # The README's own pins must be among the hits, or the walk missed files. Any
    # version will do: right after a bump they are all stale, and the list
    # below is what says where.
    assert any("README.md" in paths for paths in found.values()), (
        "the sweep did not see README.md's pins, so it checked nothing"
    )
    stale = {
        version: sorted(paths) for version, paths in found.items() if version != current
    }
    assert not stale, (
        f"pins of an older release outside the changelog: {stale}. The package is "
        f"at {current}, and anyone copying them pins the release before it."
    )


# The image was named after the repository up to 0.7.1 and after the
# distribution since. The 0.7 line is pushed under both names, so whoever
# follows `:0.7` under the old one keeps getting its patches, and 0.8.0 is the
# announced end of it. Dropping a line from a workflow on the day it is due is
# exactly the kind of step that is forgotten, so the version bump asks for it.
OLD_IMAGE_LINE = re.compile(
    r"^\s*ghcr\.io/\$\{\{ github\.repository_owner \}\}/yahoo-finance-mcp\s*$", re.M
)


def test_the_old_image_name_ends_with_the_0_7_line():
    workflow = (REPO / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    still_pushed = bool(OLD_IMAGE_LINE.search(workflow))
    major, minor = (
        int(p) for p in benethos_yahoo_finance_mcp.__version__.split(".")[:2]
    )
    if (major, minor) <= (0, 7):
        assert still_pushed, (
            "publish.yml no longer pushes the old image name, but the 0.7 line "
            "promised it updates until 0.8.0."
        )
    else:
        assert not still_pushed, (
            "publish.yml still pushes ghcr.io/benethos-hub/yahoo-finance-mcp. The "
            "changelog announced 0.8.0 as the first release without it: remove "
            "that line from the image list."
        )


@pytest.mark.parametrize(("relative_path", "pattern"), VERSION_EXAMPLES)
def test_documented_version_examples_are_current(relative_path, pattern):
    text = (REPO / relative_path).read_text(encoding="utf-8")
    found = re.findall(pattern, text)

    # A pattern that stops matching would let this pass while checking nothing.
    assert found, f"{relative_path} no longer contains {pattern!r}"

    stale = sorted({v for v in found if v != benethos_yahoo_finance_mcp.__version__})
    assert not stale, (
        f"{relative_path} still shows {stale}, the package is at "
        f"{benethos_yahoo_finance_mcp.__version__}. Anyone copying that example "
        "pins an older release than the one they are reading about."
    )


@pytest.mark.parametrize(("relative_path", "pattern"), MINOR_LINE_EXAMPLES)
def test_documented_minor_line_examples_are_current(relative_path, pattern):
    text = (REPO / relative_path).read_text(encoding="utf-8")
    found = re.findall(pattern, text)

    assert found, f"{relative_path} no longer contains {pattern!r}"

    major, minor, *_ = benethos_yahoo_finance_mcp.__version__.split(".")
    current = f"{major}.{minor}"
    stale = sorted({v for v in found if v != current})
    assert not stale, (
        f"{relative_path} still offers {stale} as the minor line to follow, but "
        f"the package is on {current}. That tag stops at the previous minor and "
        "never sees this release."
    )


# Step 3 of the release checklist: `[Unreleased]` closed as the new version
# with its date, and the two compare links at the foot moved along. A bump with
# the changelog still open passed every check above, and the release notes are
# taken from exactly that section.
CHANGELOG_SECTION = re.compile(r"^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?$", re.M)
CHANGELOG_LINK = re.compile(r"^\[([^\]]+)\]: (\S+)$", re.M)


def test_changelog_closes_the_current_release():
    current = benethos_yahoo_finance_mcp.__version__
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = CHANGELOG_SECTION.findall(text)
    names = [name for name, _ in sections]

    assert names[:2] == ["Unreleased", current], (
        f"CHANGELOG.md opens with {names[:2]}, expected ['Unreleased', "
        f"'{current}']: close `[Unreleased]` as `## [{current}] - <date>` and "
        "start a new empty one above it."
    )
    assert dict(sections)[current], f"`## [{current}]` in CHANGELOG.md has no date"

    compare = PYPROJECT["project"]["urls"]["Repository"] + "/compare/"
    previous = names[2]
    links = dict(CHANGELOG_LINK.findall(text))
    expected = {
        "Unreleased": f"{compare}v{current}...HEAD",
        current: f"{compare}v{previous}...v{current}",
    }
    wrong = {
        name: links.get(name)
        for name, url in expected.items()
        if links.get(name) != url
    }
    assert not wrong, (
        f"compare links at the foot of CHANGELOG.md are {wrong}, expected "
        f"{ {name: expected[name] for name in wrong} }"
    )


# The supported Pythons are written down in four places that nothing ties
# together: the classifiers in pyproject.toml, its requires-python, the CI
# matrix, and the matrix entry that measures coverage (plus the oldest Python
# lowest-versions installs). Adding 3.15 meant editing each by hand, and one
# left behind would have kept every check green. ci.yml is read with regular
# expressions, which is enough for these few lines and needs no YAML parser.
CI = (REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _matrix_versions() -> list[str]:
    match = re.search(r"^\s*python-version: \[([^\]]*)\]", CI, re.M)
    assert match, "ci.yml no longer lists a python-version matrix"
    versions = re.findall(r'"(\d+\.\d+)"', match.group(1))
    assert versions, f"no versions found in {match.group(0).strip()!r}"
    return sorted(versions, key=_version_key)


def test_classifiers_name_exactly_the_tested_pythons():
    prefix = "Programming Language :: Python :: "
    classified = sorted(
        (
            c.removeprefix(prefix)
            for c in PYPROJECT["project"]["classifiers"]
            if re.fullmatch(re.escape(prefix) + r"\d+\.\d+", c)
        ),
        key=_version_key,
    )
    matrix = _matrix_versions()
    assert classified == matrix, (
        f"pyproject.toml classifies Python {classified}, CI tests {matrix}. "
        "Add or drop the version in both places."
    )


# Each condition with the `run:` line under it, so the operator is tied to the
# step it guards: `==` belongs to the one with --cov, `!=` to the one without.
_CONDITIONAL_STEP = re.compile(
    r"if: matrix\.python-version ([!=]=) '(\d+\.\d+)'\n\s*run: (.+)"
)


def test_coverage_runs_on_the_newest_tested_python():
    steps = _CONDITIONAL_STEP.findall(CI)
    assert len(steps) == 2, (
        f"expected the test job's two conditional steps in ci.yml, found {steps}"
    )
    newest = _matrix_versions()[-1]
    expected = {("==", newest, True), ("!=", newest, False)}
    found = {(op, version, "--cov" in run) for op, version, run in steps}
    assert found == expected, (
        f"the test steps run as {sorted(found)} (operator, version, with --cov), "
        f"expected {sorted(expected)}: coverage on the newest tested Python, "
        f"{newest}, and the other versions without it."
    )


# The range the prose names, "Python 3.11-3.15", in the files a contributor
# reads first, with a hyphen or the README's en dash. The changelog is history
# and keeps the ranges of its day.
_PROSE_RANGE = re.compile(r"Python(?::\*\*)? (\d+\.\d+)[-–](\d+\.\d+)")


@pytest.mark.parametrize("relative_path", ["CLAUDE.md", "README.md", "SPECS.md"])
def test_the_documented_python_range_is_the_matrix(relative_path):
    text = (REPO / relative_path).read_text(encoding="utf-8")
    ranges = set(_PROSE_RANGE.findall(text))
    assert ranges, f"{relative_path} no longer names a Python range"
    matrix = _matrix_versions()
    assert ranges == {(matrix[0], matrix[-1])}, (
        f"{relative_path} names Python {sorted(ranges)}, CI tests "
        f"{matrix[0]}-{matrix[-1]}"
    )


def test_the_oldest_tested_python_is_the_floor_everywhere():
    oldest = _matrix_versions()[0]
    requires = PYPROJECT["project"]["requires-python"]
    assert requires == f">={oldest}", (
        f"requires-python is {requires!r}, the oldest tested Python is {oldest}"
    )
    lowest = re.search(r"uv venv -p (\d+\.\d+) /tmp/lowest", CI)
    assert lowest, "ci.yml no longer creates the lowest-versions venv with -p"
    assert lowest.group(1) == oldest, (
        f"lowest-versions installs on {lowest.group(1)}, the oldest tested "
        f"Python is {oldest}"
    )
