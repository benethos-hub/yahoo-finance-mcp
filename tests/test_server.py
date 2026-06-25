"""Tests for tool registration and the generated MCP schema (offline)."""

from __future__ import annotations

import asyncio

from yahoo_finance_mcp.server import mcp

EXPECTED_TOOLS = {
    "search",
    "get_quote",
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
        props = (tool.inputSchema or {}).get("properties", {})
        assert props, f"{tool.name} has no parameters in its schema"
        for param, spec in props.items():
            assert spec.get("description"), f"{tool.name}.{param} missing description"
