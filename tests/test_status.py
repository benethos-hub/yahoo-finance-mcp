"""Tests for ``server_status``, called through the SDK as a client calls it.

The tool asks Yahoo nothing. Its upstream lines come from what the yahoo
package remembers of the last request, see tests/yahoo/test_tickers.py.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from importlib.metadata import version
from types import SimpleNamespace

import pytest

from benethos_yahoo_finance_mcp import __version__, yahoo
from benethos_yahoo_finance_mcp.cli import parse_settings
from benethos_yahoo_finance_mcp.errors import RateLimitError
from benethos_yahoo_finance_mcp.server import build_server
from benethos_yahoo_finance_mcp.tools import status
from benethos_yahoo_finance_mcp.yahoo import tickers

CORE = ["name", "version", "transport", "python", "mcp", "uptime_seconds"]


def _status(server, **arguments):
    """The answer's text, after checking it came as one plain text block."""
    result = asyncio.run(server.call_tool("server_status", arguments))
    assert not result.is_error
    assert result.structured_content is None
    (block,) = result.content
    assert block.type == "text"
    return block.text


def _fields(text):
    return [line.split(":", 1)[0] for line in text.splitlines()]


def _value(text, key):
    [value] = [
        line.split(": ", 1)[1]
        for line in text.splitlines()
        if line.strip().startswith(f"{key}: ")
    ]
    return value


@pytest.fixture
def no_request_yet(monkeypatch):
    monkeypatch.setattr(tickers, "_last_answer", None)


@pytest.fixture
def yahoo_unreachable(monkeypatch):
    """Any request to Yahoo fails the test."""

    def refuse(*args, **kwargs):
        raise AssertionError("server_status asked Yahoo")

    monkeypatch.setattr(tickers, "get_ticker", refuse)
    monkeypatch.setattr(tickers.yf, "Ticker", refuse)
    monkeypatch.setattr(tickers.yf, "Search", refuse)


def test_the_core_fields_by_name_and_order(server):
    text = _status(server)
    assert _fields(text) == CORE
    assert _value(text, "name") == "benethos-yahoo-finance-mcp"
    assert _value(text, "version") == __version__
    assert _value(text, "transport") == "stdio"
    assert _value(text, "python") == "{}.{}.{}".format(*sys.version_info[:3])
    assert _value(text, "mcp") == version("mcp")
    assert int(_value(text, "uptime_seconds")) >= 0


def test_the_transport_is_the_one_served():
    text = _status(build_server("streamable-http"))
    assert _value(text, "transport") == "streamable-http"


def test_the_uptime_counts_from_the_build(monkeypatch):
    clock = iter([1000.0, 1418.7])
    monkeypatch.setattr(status, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    server = build_server()
    assert _value(_status(server), "uptime_seconds") == "418"


def test_details_add_the_upstream_block_after_the_core(server, no_request_yet):
    text = _status(server, details=True)
    assert text.splitlines()[len(CORE) :] == [
        "details:",
        "  upstream:",
        "    reachable: unknown",
        "    checked_seconds_ago: never",
        "    token_set: no",
    ]


@pytest.mark.parametrize("details", [False, True])
def test_no_request_either_way(server, no_request_yet, yahoo_unreachable, details):
    _status(server, details=details)
    assert yahoo.last_answer() is None


def test_after_an_answer_yahoo_is_reachable(server, monkeypatch):
    monkeypatch.setattr(tickers, "_last_answer", (True, tickers.time.monotonic() - 17))
    text = _status(server, details=True)
    assert _value(text, "reachable") == "yes"
    assert _value(text, "checked_seconds_ago") == "17"


def test_after_a_rate_limit_yahoo_is_not_reachable(server, monkeypatch):
    """The status answers although the request before it failed."""
    from yfinance.exceptions import YFRateLimitError

    monkeypatch.setattr(tickers, "_last_answer", None)
    with pytest.raises(RateLimitError):
        with tickers.upstream("Failed"):
            raise YFRateLimitError()
    text = _status(server, details=True)
    assert _value(text, "reachable") == "no"
    assert _value(text, "checked_seconds_ago") == "0"


def test_no_secret_in_the_answer(monkeypatch):
    """The bearer token guards the HTTP port, the status never names it."""
    token = "s3cr3t-T0ken-value-for-the-test"
    monkeypatch.setenv("YF_MCP_BEARER_TOKEN", token)
    settings = parse_settings(["--transport", "streamable-http"])
    assert settings.bearer_token == token
    text = _status(build_server(settings.transport), details=True)
    for start in range(len(token) - 5):
        assert token[start : start + 6] not in text


def test_a_status_question_writes_no_log_line(server, caplog):
    with caplog.at_level(logging.DEBUG, logger="benethos_yahoo_finance_mcp"):
        _status(server, details=True)
    assert caplog.records == []
