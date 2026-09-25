"""Tests for tool registration and the generated MCP schema (offline)."""

from __future__ import annotations

import asyncio
import subprocess
import sys

from benethos_yahoo_finance_mcp.server import mcp

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


def test_root_logging_is_ours_not_the_sdks():
    """Our plain stderr handler wins over the RichHandler the SDK installs.

    Both call logging.basicConfig at import and only the first counts, so this
    pins the ordering in server.py. Run in a fresh interpreter because pytest
    has its own handlers on the root logger.
    """
    code = (
        "import logging, sys, benethos_yahoo_finance_mcp.server; "
        "h = logging.getLogger().handlers; "
        "print(len(h), type(h[0]).__name__, h[0].stream is sys.stderr)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.split() == ["1", "StreamHandler", "True"]


def test_every_tool_is_annotated_read_only_and_open_world():
    """Clients read these hints, for example to skip a confirmation prompt."""
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        assert dumped.get("annotations") == {
            "readOnlyHint": True,
            "openWorldHint": True,
        }, tool.name
