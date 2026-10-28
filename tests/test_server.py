"""Tests for tool registration and the generated MCP schema (offline)."""

from __future__ import annotations

import asyncio
import subprocess
import sys

import pytest

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.server import _without_titles, build_server

mcp = build_server()

EXPECTED_TOOLS = {
    "search",
    "get_quote",
    "get_quotes",
    "get_history",
    "get_company_info",
    "get_financials",
    "get_dividends",
    "get_news",
    "get_recommendations",
    "get_options",
    "get_earnings",
    "get_estimates",
    "get_upgrades_downgrades",
    "get_holders",
    "get_insider_activity",
    "get_sec_filings",
    "get_calendar",
    "get_shares",
    "get_fund_data",
    "get_sector",
    "get_industry",
    "get_market",
    "screen",
}


def _list_tools():
    return asyncio.run(mcp.list_tools())


def test_all_expected_tools_are_registered():
    names = {t.name for t in _list_tools()}
    assert names == EXPECTED_TOOLS


def test_search_is_listed_first():
    """A name has to be resolved before anything else can use it."""
    assert _list_tools()[0].name == "search"


def test_every_tool_has_a_description():
    for tool in _list_tools():
        assert tool.description and tool.description.strip(), tool.name


def test_every_parameter_has_a_description():
    for tool in _list_tools():
        props = (tool.input_schema or {}).get("properties", {})
        assert props, f"{tool.name} has no parameters in its schema"
        for param, spec in props.items():
            assert spec.get("description"), f"{tool.name}.{param} missing description"


def _fresh(code: str) -> list[str]:
    """Run ``code`` in a fresh interpreter, whose root logger pytest has not touched."""
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_root_logging_is_ours_not_the_sdks():
    """One plain handler on stderr, not the RichHandler the SDK installs."""
    code = (
        "import logging, sys; "
        "from benethos_yahoo_finance_mcp import cli, transport; "
        "transport.run_stdio = lambda server: None; "
        "cli.main([]); "
        "h = logging.getLogger().handlers; "
        "print(len(h), isinstance(h[0], logging.StreamHandler), "
        "h[0].stream is sys.stderr)"
    )
    assert _fresh(code) == ["1", "True", "True"]


def test_building_a_server_leaves_the_root_logger_alone():
    """The SDK's constructor calls basicConfig with a RichHandler.

    Nothing may be left of it, whatever order a program builds and logs in.
    """
    code = (
        "import logging; "
        "from benethos_yahoo_finance_mcp.server import build_server; "
        "build_server(); "
        "root = logging.getLogger(); "
        "print(len(root.handlers), logging.getLevelName(root.level))"
    )
    assert _fresh(code) == ["0", "WARNING"]


def test_importing_the_package_configures_no_logging():
    code = (
        "import logging; "
        "import benethos_yahoo_finance_mcp.cli, benethos_yahoo_finance_mcp.server; "
        "print(len(logging.getLogger().handlers))"
    )
    assert _fresh(code) == ["0"]


def test_every_tool_is_annotated_read_only_and_open_world():
    """Clients read these hints, for example to skip a confirmation prompt."""
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        assert dumped.get("annotations") == {
            "readOnlyHint": True,
            "openWorldHint": True,
        }, tool.name


def test_every_tool_has_a_title_of_its_own():
    """A client shows the title to a person, two alike could not be told apart."""
    titles = [tool.title for tool in asyncio.run(mcp.list_tools())]
    assert all(titles), titles
    assert len(set(titles)) == len(titles), titles


def _titles_in(schema: object) -> list[str]:
    """Every ``title`` key a schema carries, property names left out."""
    if isinstance(schema, list):
        return [t for item in schema for t in _titles_in(item)]
    if not isinstance(schema, dict):
        return []
    found = []
    for key, value in schema.items():
        if key == "title":
            found.append(str(value))
        elif key in ("properties", "$defs"):
            found.extend(t for sub in value.values() for t in _titles_in(sub))
        else:
            found.extend(_titles_in(value))
    return found


def test_the_schemas_carry_no_titles():
    """pydantic names every model and field, and no client reads those names."""
    for tool in asyncio.run(mcp.list_tools()):
        assert _titles_in(tool.input_schema) == [], tool.name
        assert _titles_in(tool.output_schema) == [], tool.name


def test_a_parameter_called_title_would_survive():
    """Only the key is dropped, a property of that name is a property."""
    schema = {
        "title": "xArguments",
        "properties": {"title": {"title": "Title", "type": "string"}},
        "$defs": {"title": {"title": "T", "type": "object"}},
    }
    assert _without_titles(schema) == {
        "properties": {"title": {"type": "string"}},
        "$defs": {"title": {"type": "object"}},
    }


# A bound a tool states in prose the model reads, and in the ``le`` of a
# parameter where it has one, against the constant the yahoo function holds.
# A docstring cannot take the number from the constant, so this ties them.
BOUNDS = [
    ("search", "limit", "(1-{})", yahoo.SEARCH_MAX),
    ("get_news", "limit", "1-{})", yahoo.NEWS_MAX),
    ("get_earnings", "limit", None, yahoo.EARNINGS_MAX),
    ("get_sec_filings", "limit", None, yahoo.FILINGS_MAX),
    ("screen", "limit", None, yahoo.SCREEN_MAX),
]


@pytest.mark.parametrize(("tool", "param", "text", "value"), BOUNDS)
def test_a_bound_is_stated_as_the_yahoo_function_holds_it(tool, param, text, value):
    [listed] = [t for t in _list_tools() if t.name == tool]
    if text:
        assert text.format(value) in listed.description
    if param:
        assert listed.input_schema["properties"][param]["maximum"] == value


def test_the_server_names_its_website():
    """The initialize handshake points a client at the repository."""
    assert mcp.website_url == "https://github.com/benethos-hub/yahoo-finance-mcp"
