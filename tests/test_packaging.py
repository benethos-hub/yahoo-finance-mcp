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

from pathlib import Path

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
