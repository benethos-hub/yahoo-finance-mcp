"""The log's catalog: every line is a function in the logbook, and nothing else logs.

A rule about what a line may carry is only kept if there is one place to keep
it. These tests make the logbook that place: no module outside it imports
``logging``, every line takes its parameters from a fixed vocabulary that
``_describe`` knows how to render safely, and every line is written somewhere,
so the catalog does not fill up with lines nobody calls.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import benethos_yahoo_finance_mcp
from benethos_yahoo_finance_mcp.logbook import cache, calls, lifecycle, upstream

PACKAGE = Path(benethos_yahoo_finance_mcp.__file__).resolve().parent
LOGBOOK = PACKAGE / "logbook"
LINE_MODULES = (lifecycle, calls, cache, upstream)

# Every parameter a line may take. A new one needs a reason, and a rule in
# _describe if the value could carry something a line must not.
VOCABULARY = {
    "tool",  # a tool name, fixed by this package
    "arguments",  # a call's arguments, reduced to its subject by _describe
    "result",  # a call's result, reduced to counts by _describe
    "error",  # an exception, reduced to its class, or class and text for faults
    "seconds",  # a duration
    "fields",  # names of arguments a schema refused, never their values
    "variable",  # the name of an environment variable
    "value",  # an unusable setting's value, never the token's
    "version",  # this package's version
    "transport",
    "host",
    "port",
    "path",
    "directory",  # the cache directory
    "dropped",  # how many cache entries a sweep removed
    "limit",  # the configured most entries the cache keeps
}


def _sources_outside_the_logbook() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if LOGBOOK not in p.parents]


def _lines() -> list[tuple[str, object]]:
    """Every function in a line module that writes to the log."""
    found = []
    for module in LINE_MODULES:
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if fn.__module__ != module.__name__ or name.startswith("_"):
                continue
            if "_log." in inspect.getsource(fn):
                found.append((f"{module.__name__.rsplit('.', 1)[1]}.{name}", fn))
    return found


def test_the_catalog_is_not_empty():
    assert len(_lines()) >= 15


@pytest.mark.parametrize("path", _sources_outside_the_logbook(), ids=lambda p: p.name)
def test_nothing_outside_the_logbook_imports_logging(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert not any(n == "logging" or n.startswith("logging.") for n in names), (
            f"{path.name} imports logging. Add a line to the logbook instead."
        )


@pytest.mark.parametrize("name,fn", _lines(), ids=[n for n, _ in _lines()])
def test_every_parameter_is_in_the_vocabulary(name, fn):
    params = set(inspect.signature(fn).parameters)
    assert params <= VOCABULARY, f"{name} takes {params - VOCABULARY}"


@pytest.mark.parametrize("name,fn", _lines(), ids=[n for n, _ in _lines()])
def test_every_line_is_written_somewhere(name, fn):
    call = f"{name.split('.')[1]}("
    used = any(
        f".{call}" in path.read_text(encoding="utf-8")
        for path in _sources_outside_the_logbook()
    )
    assert used, f"{name} is in the catalog but nothing writes it"
