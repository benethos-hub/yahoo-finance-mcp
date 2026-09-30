"""What an empty or failed answer tells the model, across the yahoo modules.

An empty answer is not always an unknown symbol. Saying it is sends the model
to the search tool for a ticker that was right, so each case here names its
real cause. yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fakes import FakeTicker

from benethos_yahoo_finance_mcp import cache, yahoo
from benethos_yahoo_finance_mcp.errors import (
    RateLimitError,
    SymbolNotFoundError,
    ToolError,
)
from benethos_yahoo_finance_mcp.settings import Settings
from benethos_yahoo_finance_mcp.yahoo import tickers

# The six equity-only tools, each with the fake that answers nothing. Their
# descriptions used to promise an empty answer for ETFs, funds and crypto.
EQUITY_ONLY = [
    ("get_earnings", FakeTicker(earnings_dates=None, earnings_history=None)),
    (
        "get_estimates",
        FakeTicker(
            earnings_estimate=None,
            revenue_estimate=None,
            eps_trend=None,
            eps_revisions=None,
            growth_estimates=None,
        ),
    ),
    ("get_upgrades_downgrades", FakeTicker(upgrades_downgrades=pd.DataFrame())),
    (
        "get_holders",
        FakeTicker(
            major_holders=None, institutional_holders=None, mutualfund_holders=None
        ),
    ),
    (
        "get_insider_activity",
        FakeTicker(
            insider_transactions=None,
            insider_purchases=None,
            insider_roster_holders=None,
        ),
    ),
    ("get_calendar", FakeTicker(calendar={})),
]


@pytest.mark.parametrize("tool,fake", EQUITY_ONLY, ids=[t for t, _ in EQUITY_ONLY])
def test_an_etf_is_not_sent_to_the_search_tool(patch_ticker, tool, fake):
    """SPY is a correct symbol with no analyst or insider data at all."""
    patch_ticker(fake)
    with pytest.raises(SymbolNotFoundError) as info:
        getattr(yahoo, tool)("SPY")
    assert info.value.reason == tickers.EQUITY_ONLY_REASON
    assert "look it up by name" not in str(info.value)


class _Fast:
    """A fast_info whose every field fails the way ``errors`` says."""

    def __init__(self, errors: dict[str, Exception]) -> None:
        self.errors = errors

    def get(self, field: str):
        if field in self.errors:
            raise self.errors[field]
        return None


def test_an_unreachable_yahoo_is_not_an_unknown_symbol(monkeypatch):
    """Measured with a dead proxy: a ConnectionError among the fields."""
    from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError

    fast = _Fast({"lastPrice": KeyError("x"), "open": CurlConnectionError("down")})
    monkeypatch.setattr(
        tickers, "get_ticker", lambda s: type("T", (), {"fast_info": fast})()
    )
    with pytest.raises(ToolError) as info:
        yahoo.get_quote("MSFT")
    assert not isinstance(info.value, SymbolNotFoundError)
    assert "Yahoo could not be reached (ConnectionError)" in str(info.value)


def test_an_unknown_symbol_still_is_one(monkeypatch):
    """Measured: an unknown symbol raises KeyError for some fields, nothing else."""
    fast = _Fast({"lastPrice": KeyError("x"), "open": KeyError("y")})
    monkeypatch.setattr(
        tickers, "get_ticker", lambda s: type("T", (), {"fast_info": fast})()
    )
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_quote("NOPE")


def test_one_failed_lookup_does_not_cost_the_batch(monkeypatch):
    def lookup(symbol):
        if symbol == "BAD":
            raise ToolError("Failed to resolve 'BAD': unexpected TypeError.")
        return FakeTicker(fast_info={"lastPrice": 1.0})

    monkeypatch.setattr(tickers, "get_ticker", lookup)
    out = yahoo.get_quotes(["AAPL", "BAD"])
    assert out["count"] == 1
    assert out["not_found"] == ["BAD"]


def test_a_rate_limit_while_resolving_stops_the_batch(monkeypatch):
    def lookup(symbol):
        raise RateLimitError()

    monkeypatch.setattr(tickers, "get_ticker", lookup)
    with pytest.raises(RateLimitError):
        yahoo.get_quotes(["AAPL", "MSFT"])


def test_no_articles_is_not_pinned_in_the_cache(patch_ticker, tmp_path):
    """{"count": 0, ...} is truthy, and plain bool kept it for the whole TTL."""
    cache.configure(Settings(cache_enabled=True, cache_dir=tmp_path))
    try:
        patch_ticker(FakeTicker(news=[]))
        assert yahoo.get_news("aapl")["count"] == 0
        story = {"content": {"title": "Now there is news"}}
        patch_ticker(FakeTicker(news=[story]))
        assert yahoo.get_news("aapl")["count"] == 1
    finally:
        cache.configure(Settings())


@pytest.mark.parametrize(
    "result,keep",
    [
        ([], False),
        ({}, False),
        ({"count": 0, "articles": []}, False),
        ({"count": 2, "articles": [1, 2]}, True),
        ({"symbol": "AAPL"}, True),
        ([{"symbol": "AAPL"}], True),
    ],
)
def test_has_content(result, keep):
    assert cache.has_content(result) is keep
