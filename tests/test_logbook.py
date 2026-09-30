"""What the log says, at which level, and what it never says.

Each call goes through the real server with the client mocked, so the line is
the one an operator would read.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from benethos_yahoo_finance_mcp import cache, cli, transport, yahoo
from benethos_yahoo_finance_mcp.errors import RateLimitError, SymbolNotFoundError
from benethos_yahoo_finance_mcp.logbook import access, output
from benethos_yahoo_finance_mcp.server import build_server
from benethos_yahoo_finance_mcp.settings import Settings
from benethos_yahoo_finance_mcp.yahoo import tickers

mcp = build_server()
TOOLS = "benethos_yahoo_finance_mcp.tools"
YAHOO = "benethos_yahoo_finance_mcp.yahoo"


def _call(tool: str, args: dict[str, object]):
    return asyncio.run(mcp.call_tool(tool, args))


def _ours(caplog) -> list[logging.LogRecord]:
    return [
        r for r in caplog.records if r.name.startswith("benethos_yahoo_finance_mcp")
    ]


def test_a_call_that_returned_is_one_info_line(monkeypatch, caplog):
    rows = [{"close": 1.0}] * 250
    monkeypatch.setattr(
        yahoo, "get_history", lambda *a, **k: {"rows": rows, "truncated": True}
    )
    with caplog.at_level(logging.INFO):
        _call("get_history", {"symbol": "sap.de"})
    [record] = _ours(caplog)
    assert (record.name, record.levelno) == (TOOLS, logging.INFO)
    message = record.getMessage()
    assert message.startswith("get_history SAP.DE 250 rows, truncated, ")
    assert message.endswith(" ms")


def test_a_quotes_call_counts_found_and_missing(monkeypatch, caplog):
    answer = {"count": 2, "quotes": [{}, {}], "not_found": ["X"], "truncated": False}
    monkeypatch.setattr(yahoo, "get_quotes", lambda *a, **k: answer)
    with caplog.at_level(logging.INFO):
        _call("get_quotes", {"symbols": ["A", "B", "X"]})
    [record] = _ours(caplog)
    assert record.getMessage().startswith("get_quotes 3 symbols, 2 found, 1 missing, ")


def test_a_search_line_never_carries_the_query(monkeypatch, caplog):
    """A query is free text a person typed. Only the number of matches is logged."""
    monkeypatch.setattr(yahoo, "search", lambda *a, **k: [{"symbol": "AAPL"}])
    with caplog.at_level(logging.DEBUG):
        _call("search", {"query": "my private shopping list"})
    [record] = _ours(caplog)
    assert record.getMessage().startswith("search 1 matches, ")
    assert all("shopping" not in r.getMessage() for r in caplog.records)


def test_a_failed_call_is_a_warning_naming_the_class_not_the_text(monkeypatch, caplog):
    def boom(*a, **k):
        raise SymbolNotFoundError("NOPE")

    monkeypatch.setattr(yahoo, "get_options", boom)
    with caplog.at_level(logging.INFO), pytest.raises(Exception):  # noqa: B017
        _call("get_options", {"symbol": "nope"})
    [record] = _ours(caplog)
    assert (record.name, record.levelno) == (TOOLS, logging.WARNING)
    assert record.getMessage().startswith(
        "get_options NOPE failed: SymbolNotFoundError, "
    )
    assert "search" not in record.getMessage()  # the model's hint stays out


def test_a_rate_limit_is_named_for_the_operator(monkeypatch, caplog):
    def limited(*a, **k):
        raise RateLimitError()

    monkeypatch.setattr(yahoo, "get_news", limited)
    with caplog.at_level(logging.INFO), pytest.raises(Exception):  # noqa: B017
        _call("get_news", {"symbol": "aapl"})
    [record] = _ours(caplog)
    assert (record.name, record.levelno) == (YAHOO, logging.WARNING)
    assert record.getMessage() == "Yahoo rate limited get_news for AAPL"


def test_refused_arguments_name_the_field_not_the_value(caplog):
    with caplog.at_level(logging.INFO), pytest.raises(Exception):  # noqa: B017
        _call("get_news", {"symbol": "AAPL", "limit": 31337})
    [record] = _ours(caplog)
    assert (record.name, record.levelno) == (TOOLS, logging.WARNING)
    assert record.getMessage() == "get_news refused arguments: limit"
    assert all("31337" not in r.getMessage() for r in _ours(caplog))


def test_an_answer_from_the_result_cache_says_so(monkeypatch, caplog, tmp_path):
    cache.configure(Settings(cache_enabled=True, cache_dir=tmp_path))

    class Fast:
        fast_info = {"lastPrice": 1.0}

    monkeypatch.setattr(tickers, "get_ticker", lambda symbol: Fast())
    with caplog.at_level(logging.INFO, logger=TOOLS):
        _call("get_quote", {"symbol": "AAPL"})
        _call("get_quote", {"symbol": "AAPL"})
    first, second = [r.getMessage() for r in caplog.records if r.name == TOOLS]
    assert not first.endswith("cached")
    assert second.endswith(", cached")


def test_an_unusable_environment_value_is_reported(monkeypatch, caplog):
    monkeypatch.setenv("YF_MCP_PORT", "eighty")
    monkeypatch.setattr(transport, "run_stdio", lambda server: None)
    with caplog.at_level(logging.WARNING):
        cli.main([])
    messages = [r.getMessage() for r in _ours(caplog)]
    assert "Ignoring invalid YF_MCP_PORT: 'eighty'" in messages


class TestAccessLog:
    def _record(self, path: str, status: int) -> logging.LogRecord:
        return logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "%s %s HTTP/%s" %d',
            ("10.0.0.7:5555", "POST", path, "1.1", status),
            None,
        )

    def test_the_query_string_is_dropped(self):
        record = self._record("/mcp?session=abc", 401)
        assert access.AccessFilter().filter(record)
        assert record.getMessage() == '10.0.0.7:5555 - "POST /mcp HTTP/1.1" 401'

    def test_a_refused_request_stays_info(self):
        record = self._record("/mcp", 421)
        access.AccessFilter().filter(record)
        assert record.levelno == logging.INFO

    def test_a_served_request_is_debug(self):
        record = self._record("/mcp", 200)
        access.AccessFilter().filter(record)
        assert (record.levelno, record.levelname) == (logging.DEBUG, "DEBUG")

    def test_uvicorn_gets_no_handlers_of_its_own(self):
        assert access.uvicorn_options()["log_config"] is None


def test_chatty_libraries_are_held_at_warning():
    """The SDK quotes every failed call's text at INFO, and yfinance is loud."""
    output.configure("DEBUG")
    for name in output.QUIET:
        assert logging.getLogger(name).level == logging.WARNING, name


def test_debug_lowers_this_server_and_the_request_log_only():
    """A library nobody named, asyncio say, stays at the root's WARNING."""
    output.configure("DEBUG")
    level = {
        name: logging.getLogger(name).getEffectiveLevel()
        for name in ("", "asyncio", TOOLS, "uvicorn.access", "uvicorn.error")
    }
    assert level == {
        "": logging.WARNING,
        "asyncio": logging.WARNING,
        TOOLS: logging.DEBUG,
        "uvicorn.access": logging.DEBUG,
        "uvicorn.error": logging.INFO,
    }


def test_streamed_responses_never_reach_the_log():
    """sse_starlette logs every chunk at DEBUG, and a chunk is a whole tool result."""
    assert {"mcp", "sse_starlette"} <= set(output.QUIET)
