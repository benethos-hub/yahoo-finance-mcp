"""The documents: where they stand, how a long one is split, and their links.

The rule is in CLAUDE.md under Conventions. A document directly in docs/
is named in capitals. A long one is an overview, and its parts stand in the
folder of the same name in lowercase, each starting with the name of its
document and a line back to the overview, which lists every part. The
concept keeps its section numbers, so "CONCEPT §4" names one place.

A link renders whether it leads anywhere or not, so a renamed heading or a
moved file goes unnoticed. Checked here, without the network:

- A link to a heading lands on one, in the same file or another one of the
  repository.
- A link into the repository, relative or as an address on GitHub, names a
  file or folder that is there.
- The README PyPI shows has no relative link, since PyPI renders it without
  the repository around it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Only the ``](target)`` tail of a link: a badge is a link around an image,
# and its outer target is the one that counts.
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_SRC = re.compile(r"""<img\b[^>]*?\bsrc=["']([^"']+)["']""")
_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
_HEADING = re.compile(r"^(#{1,6}) (.+)$", re.M)
_REPOSITORY = re.compile(
    r"^https://(?:github\.com/benethos-hub/yahoo-finance-mcp/(?:blob|tree)/main/"
    r"|raw\.githubusercontent\.com/benethos-hub/yahoo-finance-mcp/main/)"
    r"([^#?]*)(?:#(.*))?$"
)
_SECTION = re.compile(r"^## (\d+a?)\. ", re.M)
_ROW = re.compile(r"^\| \[[^\]]+\]\(concept/([^)]+)\) \| ([^|]+) \|", re.M)


def _documents() -> list[Path]:
    """Every Markdown file a person reads here. The changelog is history and
    names files and headings as they were on their day."""
    return [
        ROOT / "README.md",
        ROOT / "CLAUDE.md",
        ROOT / "SECURITY.md",
        ROOT / "containers" / "README.md",
        *sorted(DOCS.rglob("*.md")),
    ]


def _text(markdown: str) -> str:
    return _FENCE.sub("", markdown)


def _targets(markdown: str) -> list[str]:
    text = _text(markdown)
    return _LINK.findall(text) + _SRC.findall(text)


def anchor(heading: str) -> str:
    """GitHub's anchor of a heading: the text without HTML and code marks,
    in lower case, punctuation dropped, spaces as hyphens."""
    text = re.sub(r"<[^>]+>", "", heading).replace("`", "").strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    """The anchors of a file's headings. A repeated one gets -1, -2 and so
    on, as on GitHub."""
    found: set[str] = set()
    for _, heading in _HEADING.findall(_text(path.read_text("utf-8"))):
        base = unique = anchor(heading)
        suffix = 0
        while unique in found:
            suffix += 1
            unique = f"{base}-{suffix}"
        found.add(unique)
    return found


def _broken(document: Path, target: str) -> str | None:
    """Why ``target`` in ``document`` leads nowhere, or None."""
    if target.startswith("#"):
        return None if target[1:] in _anchors(document) else "no such heading"
    found = _REPOSITORY.match(target)
    if found:
        path, fragment = ROOT / found[1], found[2]
    elif target.startswith(("http://", "https://", "mailto:")):
        return None
    elif document == ROOT / "README.md":
        return "relative, which PyPI cannot follow"
    else:
        file, _, fragment = target.partition("#")
        path = (document.parent / file).resolve()
    if not path.exists():
        return "no such file"
    if fragment and path.suffix == ".md" and fragment not in _anchors(path):
        return "no such heading there"
    return None


@pytest.mark.parametrize(
    "document", _documents(), ids=lambda p: p.relative_to(ROOT).as_posix()
)
def test_every_link_leads_somewhere(document: Path) -> None:
    broken = [
        f"{target}: {why}"
        for target in _targets(document.read_text("utf-8"))
        if (why := _broken(document, target))
    ]
    assert not broken, "\n  ".join(["links that lead nowhere:", *broken])


def test_a_document_in_docs_is_named_in_capitals() -> None:
    files = sorted(p.name for p in DOCS.glob("*.md"))
    assert {"CONCEPT.md", "RELEASING.md"} <= set(files)
    assert [f for f in files if not f.removesuffix(".md").isupper()] == []


def test_a_folder_in_docs_holds_the_parts_of_its_document() -> None:
    for folder in (p for p in DOCS.iterdir() if p.is_dir()):
        assert folder.name == folder.name.lower()
        assert (DOCS / f"{folder.name.upper()}.md").exists(), folder.name
        for part in folder.iterdir():
            assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*\.md", part.name), part


def _parts() -> list[Path]:
    return sorted((DOCS / "concept").glob("*.md"))


@pytest.mark.parametrize("part", _parts(), ids=lambda p: p.name)
def test_a_part_names_its_document_and_leads_back(part: Path) -> None:
    lines = part.read_text("utf-8").splitlines()
    assert lines[0].startswith("# Concept: ")
    assert lines[2].startswith("Part of the [concept](../CONCEPT.md)")


def test_the_overview_lists_every_part_with_its_sections() -> None:
    rows = dict(_ROW.findall((DOCS / "CONCEPT.md").read_text("utf-8")))
    assert sorted(rows) == [p.name for p in _parts()]
    for name, numbers in rows.items():
        held = _SECTION.findall((DOCS / "concept" / name).read_text("utf-8"))
        assert [n.strip() for n in numbers.split(",")] == held, name


def test_every_section_number_stands_once() -> None:
    numbers = [
        n
        for path in [DOCS / "CONCEPT.md", *_parts()]
        for n in _SECTION.findall(path.read_text("utf-8"))
    ]
    assert len(numbers) == len(set(numbers))
    assert {"1", "3", "4", "7a", "8a", "12"} <= set(numbers)


def test_the_documents_are_found() -> None:
    names = {p.relative_to(ROOT).as_posix() for p in _documents()}
    assert {
        "docs/CONCEPT.md",
        "docs/RELEASING.md",
        "docs/concept/architecture.md",
    } <= names


def test_the_anchor_follows_githubs_rules() -> None:
    assert anchor("3. Architecture") == "3-architecture"
    assert anchor("7a. Prompts") == "7a-prompts"
    assert anchor("8a. Result cache (`cache.py`)") == "8a-result-cache-cachepy"
    assert anchor("4. Transport & runtime") == "4-transport--runtime"


def test_the_check_sees_what_is_broken(tmp_path: Path) -> None:
    document = tmp_path / "NOTES.md"
    document.write_text(
        "# T\n\n## Here\n\n[a](#here) [b](#gone) [c](missing.md)\n"
        "[![x](https://img.example/x.svg)](LICENSE)\n```\n[d](nothing)\n```\n",
        "utf-8",
    )
    targets = _targets(document.read_text("utf-8"))
    assert targets == [
        "#here",
        "#gone",
        "missing.md",
        "https://img.example/x.svg",
        "LICENSE",
    ]
    assert [_broken(document, t) for t in targets] == [
        None,
        "no such heading",
        "no such file",
        None,
        "no such file",
    ]
    base = "https://github.com/benethos-hub/yahoo-finance-mcp/blob/main/"
    assert _broken(document, base + "SPECS.md#3-architecture") == "no such file"
    assert _broken(document, base + "docs/CONCEPT.md#nothing") == (
        "no such heading there"
    )
    assert _broken(document, base + "docs/concept/prompts.md#7a-prompts") is None
    assert _broken(ROOT / "README.md", "docs/CONCEPT.md") == (
        "relative, which PyPI cannot follow"
    )
