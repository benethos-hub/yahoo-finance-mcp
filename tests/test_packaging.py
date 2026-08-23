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

import re
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
VERSION_EXAMPLES = (
    # An exact pin of the distribution, as the install section shows it.
    ("README.md", r"benethos-yahoo-finance-mcp==(\d+\.\d+\.\d+)"),
    # An exact image tag in backticks. `:0.4` names a minor line on purpose and
    # has only two components, so it is not matched.
    ("README.md", r"`:(\d+\.\d+\.\d+)`"),
    ("compose.yaml", r"`:(\d+\.\d+\.\d+)`"),
    # The version people are asked to report in a bug.
    (".github/ISSUE_TEMPLATE/bug_report.yml", r'placeholder: "(\d+\.\d+\.\d+)"'),
)

# The minor-line tag, `:0.5`, which follows patch releases rather than naming
# one. It is right for it to stay put across a patch bump and wrong for it to
# stay put across a minor one, so it is compared against the first two
# components instead of the whole version. Missed by eye on the 0.5.0 bump,
# where both of these still said `:0.4`.
MINOR_LINE_EXAMPLES = (
    ("README.md", r"`:(\d+\.\d+)`"),
    ("compose.yaml", r"`:(\d+\.\d+)`"),
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
