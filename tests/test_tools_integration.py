"""End-to-end tests for the MCP tool layer.

These complement ``test_client.py`` (which tests the client functions directly)
and ``test_server.py`` (which tests tool registration). Here every tool is
invoked through the FastMCP machinery with the client mocked, so the thin
``@mcp.tool()`` wrappers are actually exercised. This catches wiring bugs the
other suites miss — e.g. forwarding ``limit`` to the wrong client keyword — and
asserts each tool's result is JSON-serializable.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from yahoo_finance_mcp import client
from yahoo_finance_mcp.server import mcp

# Minimal valid arguments to invoke each tool (one per registered tool). Optional
# parameters are omitted; required ones use a representative value.
TOOL_ARGS: dict[str, dict[str, object]] = {
    "search": {"query": "apple"},
    "get_quote": {"symbol": "AAPL"},
    "get_history": {"symbol": "AAPL"},
    "get_company_info": {"symbol": "AAPL"},
    "get_financials": {"symbol": "AAPL"},
    "get_dividends": {"symbol": "AAPL"},
    "get_news": {"symbol": "AAPL"},
    "get_recommendations": {"symbol": "AAPL"},
    "get_options": {"symbol": "AAPL"},
    "get_earnings": {"symbol": "AAPL"},
    "get_estimates": {"symbol": "AAPL"},
    "get_upgrades_downgrades": {"symbol": "AAPL"},
    "get_holders": {"symbol": "AAPL"},
    "get_insider_activity": {"symbol": "AAPL"},
    "get_sec_filings": {"symbol": "AAPL"},
    "get_calendar": {"symbol": "AAPL"},
    "get_shares": {"symbol": "AAPL"},
    "get_fund_data": {"symbol": "AAPL"},
    "get_sector": {"key": "technology"},
    "get_industry": {"key": "semiconductors"},
}


def _call(tool: str, args: dict[str, object]):
    return asyncio.run(mcp.call_tool(tool, args))


def test_tool_args_table_matches_registered_tools():
    """The argument table must stay in sync with the registered tools."""
    registered = {t.name for t in asyncio.run(mcp.list_tools())}
    assert set(TOOL_ARGS) == registered


@pytest.mark.parametrize("tool,args", list(TOOL_ARGS.items()))
def test_tool_invokes_client_and_result_serializes(monkeypatch, tool, args):
    """Each tool calls its client function exactly once and returns JSON-safe data."""
    calls: list[tuple] = []

    # ``search`` is the only tool that returns a list; all others return a dict.
    # The return value must match the tool's declared output schema.
    payload: object = (
        [{"ok": True, "tool": tool}] if tool == "search" else {"ok": True, "tool": tool}
    )

    def spy(*a, **k):
        calls.append((a, k))
        return payload

    # Wrappers look up ``client.<name>`` at call time, so patching the attribute
    # of the right name suffices.
    monkeypatch.setattr(client, tool, spy)

    content, structured = _call(tool, args)

    assert len(calls) == 1, f"{tool} did not forward to its client function once"
    # call_tool returns (content_blocks, structured_result); both must serialize.
    json.dumps(structured)


# Tools whose ``limit`` parameter must be forwarded as the client's ``max_rows``.
LIMIT_AS_MAX_ROWS = {
    "get_upgrades_downgrades": {"symbol": "AAPL"},
    "get_holders": {"symbol": "AAPL"},
    "get_insider_activity": {"symbol": "AAPL"},
    "get_shares": {"symbol": "AAPL"},
    "get_fund_data": {"symbol": "AAPL"},
    "get_sector": {"key": "technology"},
    "get_industry": {"key": "semiconductors"},
}

# Tools whose ``limit`` parameter is forwarded as the client's ``limit``.
LIMIT_AS_LIMIT = {
    "search": {"query": "apple"},
    "get_news": {"symbol": "AAPL"},
    "get_earnings": {"symbol": "AAPL"},
    "get_sec_filings": {"symbol": "AAPL"},
}


@pytest.mark.parametrize("tool,base", list(LIMIT_AS_MAX_ROWS.items()))
def test_limit_is_forwarded_as_max_rows(monkeypatch, tool, base):
    captured: dict[str, object] = {}

    def spy(*a, **k):
        captured.update(k)
        return {"ok": True}

    monkeypatch.setattr(client, tool, spy)
    _call(tool, {**base, "limit": 7})
    assert captured.get("max_rows") == 7, f"{tool} should forward limit as max_rows"
    assert "limit" not in captured, f"{tool} must not pass a 'limit' kwarg"


@pytest.mark.parametrize("tool,base", list(LIMIT_AS_LIMIT.items()))
def test_limit_is_forwarded_as_limit(monkeypatch, tool, base):
    captured: dict[str, object] = {}

    def spy(*a, **k):
        captured.update(k)
        return [{"ok": True}] if tool == "search" else {"ok": True}

    monkeypatch.setattr(client, tool, spy)
    _call(tool, {**base, "limit": 7})
    assert captured.get("limit") == 7, f"{tool} should forward limit as limit"


def test_get_shares_forwards_start_end_and_limit(monkeypatch):
    captured: dict[str, object] = {}

    def spy(*a, **k):
        captured.update(k)
        return {"ok": True}

    monkeypatch.setattr(client, "get_shares", spy)
    _call(
        "get_shares",
        {"symbol": "AAPL", "start": "2024-01-01", "end": "2024-06-01", "limit": 7},
    )
    assert captured["start"] == "2024-01-01"
    assert captured["end"] == "2024-06-01"
    assert captured["max_rows"] == 7


def test_get_financials_forwards_statement_and_freq(monkeypatch):
    captured: dict[str, object] = {}

    def spy(*a, **k):
        captured.update(k)
        return {"ok": True}

    monkeypatch.setattr(client, "get_financials", spy)
    _call("get_financials", {"symbol": "AAPL", "statement": "cashflow", "freq": "ttm"})
    assert captured["statement"] == "cashflow"
    assert captured["freq"] == "ttm"
