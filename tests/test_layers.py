"""The layers of the package, read from the source rather than from memory.

Each top-level module or package is a unit, and the table below says which
units it may import. SPECS.md §3 shows the same table to a reader, and a test
keeps the two in agreement. A unit missing from the table fails the suite, so
a new module is placed deliberately rather than by whatever it happened to
need.

Packages speak to each other only through their ``__init__.py``: a name taken
from another package must be in that package's ``__all__``, and no import
reaches into another package's submodules. The yahoo modules can then be
regrouped without touching a single tool.
"""

from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

import benethos_yahoo_finance_mcp

PACKAGE = Path(benethos_yahoo_finance_mcp.__file__).resolve().parent
ROOT = "__init__"

# unit -> the units it imports, exactly. Order is bottom to top. A new edge
# goes in here and in SPECS §3 in the same change, an edge no longer used
# comes out, so the table describes the code rather than a ceiling over it.
LAYERS: dict[str, set[str]] = {
    ROOT: set(),  # the version, nothing else
    "errors": set(),
    "settings": set(),
    "logbook": set(),
    "formatting": set(),
    "cache": {ROOT, "settings", "logbook"},
    "yahoo": {"errors", "logbook", "cache", "formatting"},
    # Never formatting: a tool returns what yahoo built.
    "tools": {"errors", "logbook", "yahoo"},
    "server": {ROOT, "tools", "logbook"},
    # The server comes in as the SDK's type, never as this package's module.
    "transport": {"settings", "logbook"},
    "cli": {ROOT, "settings", "logbook", "cache", "server", "transport"},
    "__main__": {"cli"},
}


def _unit(parts: tuple[str, ...]) -> str:
    return parts[0].removesuffix(".py") if parts else ROOT


def _sources() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def _module_parts(path: Path) -> tuple[str, ...]:
    """``('tools', 'options')`` for tools/options.py, ``('tools',)`` for its init."""
    parts = path.relative_to(PACKAGE).with_suffix("").parts
    return parts[:-1] if parts[-1] == "__init__" else parts


def _imports(path: Path) -> Iterator[tuple[tuple[str, ...], list[str], int]]:
    """Every in-package import as ``(module path, names, line)``.

    The module path is relative to the package root: ``from ..yahoo import
    tickers`` in tools/options.py gives ``(('yahoo',), ['tickers'], line)``.
    """
    here = _module_parts(path)
    package = here if path.name == "__init__.py" else here[:-1]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = package[: len(package) - (node.level - 1)]
            target = base + tuple(node.module.split(".") if node.module else ())
            yield target, [a.name for a in node.names], node.lineno
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "benethos_yahoo_finance_mcp"
        ):
            target = tuple(node.module.split(".")[1:])  # type: ignore[union-attr]
            yield target, [a.name for a in node.names], node.lineno
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("benethos_yahoo_finance_mcp."):
                    yield tuple(alias.name.split(".")[1:]), [], node.lineno


def _edges() -> Iterator[tuple[Path, str, str, int]]:
    """``(file, its unit, imported unit, line)`` for every cross-unit import."""
    for path in _sources():
        unit = _unit(path.relative_to(PACKAGE).parts)
        for target, names, line in _imports(path):
            if target:
                used = {_unit(target)}
            else:  # from the package root: each name is a unit, or the root
                used = {n if n in LAYERS else ROOT for n in names}
            for other in used - {unit}:
                yield path, unit, other, line


def _specs_table() -> dict[str, set[str]]:
    """The layer table in SPECS.md §3, as ``LAYERS`` spells it."""
    text = (PACKAGE.parent.parent / "SPECS.md").read_text(encoding="utf-8")
    block = text.split("<!-- layers:start -->")[1].split("<!-- layers:end -->")[0]
    table: dict[str, set[str]] = {}
    for row in block.splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != 2 or not cells[0].startswith("`"):
            continue
        unit = cells[0].strip("`").removesuffix(".py")
        names = {n.removesuffix(".py") for n in re.findall(r"`([^`]+)`", cells[1])}
        table[unit] = names
    return table


def test_the_specs_table_matches_this_one():
    """SPECS §3 shows the layers to a reader. It must say what is enforced."""
    assert _specs_table() == LAYERS


def test_every_unit_has_a_line_in_the_table():
    units = {_unit(p.relative_to(PACKAGE).parts) for p in _sources()}
    assert units - set(LAYERS) == set(), "add the new module to LAYERS"


def test_the_table_names_no_unit_that_is_gone():
    units = {_unit(p.relative_to(PACKAGE).parts) for p in _sources()}
    assert set(LAYERS) - units == set()


@pytest.mark.parametrize("path", _sources(), ids=lambda p: "/".join(p.parts[-2:]))
def test_imports_follow_the_layers(path):
    wrong = [
        f"{path.name}:{line} imports {other}"
        for file, unit, other, line in _edges()
        if file == path and other not in LAYERS[unit]
    ]
    assert not wrong, wrong


def test_every_edge_in_the_table_is_used():
    """The table describes the imports, so an edge nobody uses comes out."""
    used: dict[str, set[str]] = {unit: set() for unit in LAYERS}
    for _, unit, other, _ in _edges():
        used[unit].add(other)
    assert used == LAYERS


@pytest.mark.parametrize("path", _sources(), ids=lambda p: "/".join(p.parts[-2:]))
def test_packages_are_entered_through_their_init(path):
    unit = _unit(path.relative_to(PACKAGE).parts)
    for target, names, line in _imports(path):
        if not target or _unit(target) == unit:
            continue
        where = f"{path.name}:{line}"
        assert len(target) == 1, f"{where} reaches into {'.'.join(target)}"
        other = target[0]
        if not (PACKAGE / other).is_dir():
            continue  # a plain module has no __init__ to go through
        exported = set(importlib.import_module(f"{PACKAGE.name}.{other}").__all__)
        assert set(names) <= exported, f"{where} takes {set(names) - exported}"


def test_no_unit_reaches_into_yahoo_through_an_attribute():
    """``yahoo.tickers.X`` is invisible to the import check above but just as
    tied to the submodule's name."""
    reaching = [
        path.relative_to(PACKAGE).as_posix()
        for path in _sources()
        if _unit(path.relative_to(PACKAGE).parts) != "yahoo"
        and "yahoo.tickers." in path.read_text(encoding="utf-8")
    ]
    assert not reaching


def test_only_the_command_line_entry_imports_cli():
    importers = {unit for _, unit, other, _ in _edges() if other == "cli"}
    assert importers <= {"__main__"}


def test_only_settings_reads_the_environment():
    """And logbook/formats, for NO_COLOR, a terminal convention."""
    readers = {
        path.relative_to(PACKAGE).as_posix()
        for path in _sources()
        if re.search(r"\b(os\.environ|getenv)\b", path.read_text(encoding="utf-8"))
    }
    assert readers == {"settings.py", "logbook/formats.py"}


def test_only_the_yahoo_package_imports_yfinance():
    for path in _sources():
        if _unit(path.relative_to(PACKAGE).parts) == "yahoo":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module or ""]
            assert not any(n.split(".")[0] == "yfinance" for n in names), path.name
