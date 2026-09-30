"""Tests for tool registration and the generated MCP schema (offline)."""

from __future__ import annotations

import asyncio
import subprocess
import sys

from benethos_yahoo_finance_mcp.server import build_server

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
}


def _list_tools():
    return asyncio.run(mcp.list_tools())


def test_all_expected_tools_are_registered():
    names = {t.name for t in _list_tools()}
    assert names == EXPECTED_TOOLS


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
