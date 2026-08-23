"""Guard the README links that PyPI cannot resolve.

The README is shipped verbatim as the package description. PyPI renders that
text on its own, without the repository around it, so a relative target like
``[LICENSE](LICENSE)`` becomes ``pypi.org/project/<name>/LICENSE`` and leads
nowhere. It looks fine on GitHub, which is why this went unnoticed until 0.4.0
was published, and it cannot be repaired afterwards — PyPI only re-renders the
description when a new distribution is uploaded.

Fragment links are fine: PyPI rewrites them to ``#user-content-<anchor>``.
"""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

# Only the ``](target)`` tail is matched, never the label before it. A badge is
# a link wrapped around an image, ``[![alt](img)](target)``, and any pattern
# that tries to balance the brackets misses the outer target of exactly that
# construct — which is how one of the three broken links here stayed hidden.
_LINK = re.compile(r"\]\(([^)\s]+)\)")

# Fenced code blocks hold example commands and URLs that are not page links.
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def _link_targets(markdown: str) -> list[str]:
    return _LINK.findall(_FENCE.sub("", markdown))


def test_readme_has_no_relative_links() -> None:
    """Every link target must survive being rendered outside the repository."""
    offenders = [
        target
        for target in _link_targets(README.read_text(encoding="utf-8"))
        if not target.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert not offenders, (
        "Relative link targets break on PyPI, which renders the README without "
        f"the repository around it. Use an absolute URL for: {offenders}"
    )


def test_link_check_would_catch_a_relative_target() -> None:
    """The guard is worth having only if it actually fires."""
    sample = "See [LICENSE](LICENSE) and [docs](https://example.com).\n"
    assert _link_targets(sample) == ["LICENSE", "https://example.com"]


def test_link_check_sees_through_a_badge() -> None:
    """A badge nests an image inside a link, and the outer target is the one
    that has to be checked."""
    sample = "[![License](https://img.shields.io/badge/x)](LICENSE)\n"
    assert _link_targets(sample) == ["https://img.shields.io/badge/x", "LICENSE"]


def test_link_check_ignores_code_blocks() -> None:
    """A path inside a fenced block is an example, not a link."""
    sample = "Text [ok](https://example.com)\n\n```\ncp [a](b) elsewhere\n```\n"
    assert _link_targets(sample) == ["https://example.com"]


# Adding a tool and forgetting its README row is the realistic version of this
# mistake: the tool works, every test passes, and the only symptom is that
# nobody reading the documentation knows it exists. The reverse, a row for a
# tool that was renamed or removed, sends people after something that is not
# there.
def test_readme_documents_exactly_the_registered_tools() -> None:
    import asyncio

    from benethos_yahoo_finance_mcp.server import mcp

    registered = {tool.name for tool in asyncio.run(mcp.list_tools())}
    documented = set(
        re.findall(r"`(get_[a-z_]+|search)`", README.read_text(encoding="utf-8"))
    )

    undocumented = sorted(registered - documented)
    assert not undocumented, (
        f"registered but absent from the README: {undocumented}. A tool nobody "
        "can read about is a tool nobody uses."
    )

    phantom = sorted(documented - registered)
    assert not phantom, (
        f"described in the README but not registered: {phantom}. Readers will "
        "go looking for something that is not there."
    )
