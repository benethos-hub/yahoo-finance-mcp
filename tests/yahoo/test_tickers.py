"""Unit tests for the ticker cache and how upstream errors are mapped.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pytest
from fakes import FakeTicker
from yfinance.exceptions import YFRateLimitError

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    RateLimitError,
    SymbolNotFoundError,
    ToolError,
)
from benethos_yahoo_finance_mcp.yahoo import tickers

# --- get_ticker cache -----------------------------------------------------


def test_get_ticker_caches_and_is_case_insensitive(monkeypatch):
    tickers._ticker_cache.clear()
    constructed: list[str] = []

    def fake_ticker(symbol):
        constructed.append(symbol)
        return FakeTicker()

    monkeypatch.setattr(tickers.yf, "Ticker", fake_ticker)

    first = tickers.get_ticker("aapl")
    second = tickers.get_ticker("AAPL")
    assert first is second  # same cached instance
    assert constructed == ["AAPL"]  # built once, key upper-cased


def test_get_ticker_cache_is_bounded(monkeypatch):
    """Distinct symbols past the cap evict the least recently used one."""
    tickers._ticker_cache.clear()
    monkeypatch.setattr(tickers, "_TICKER_CACHE_MAX", 3)
    monkeypatch.setattr(tickers.yf, "Ticker", lambda symbol: FakeTicker())

    for sym in ("A", "B", "C"):
        tickers.get_ticker(sym)
    tickers.get_ticker("A")  # A is now the most recently used
    tickers.get_ticker("D")
    assert list(tickers._ticker_cache) == ["C", "A", "D"]


def test_get_ticker_cache_drops_expired_entries(monkeypatch):
    """A stale entry goes on the next insert, not only when it is asked for."""
    tickers._ticker_cache.clear()
    clock = [1000.0]
    monkeypatch.setattr(tickers.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(tickers.yf, "Ticker", lambda symbol: FakeTicker())

    tickers.get_ticker("OLD")
    clock[0] += tickers._TICKER_TTL + 1
    tickers.get_ticker("NEW")
    assert list(tickers._ticker_cache) == ["NEW"]


def test_get_ticker_unresolvable_isin_is_symbol_not_found(monkeypatch):
    """yfinance resolves ISIN-shaped input in the constructor and raises
    ValueError when Yahoo knows no such ISIN. That must not escape raw."""
    tickers._ticker_cache.clear()

    def unresolvable(symbol):
        raise ValueError(f"Invalid ISIN number: {symbol}")

    monkeypatch.setattr(tickers.yf, "Ticker", unresolvable)
    with pytest.raises(SymbolNotFoundError) as info:
        tickers.get_ticker("zz0000000009")
    assert info.value.symbol == "ZZ0000000009"
    assert "ZZ0000000009" not in tickers._ticker_cache


def test_get_ticker_rate_limit_while_resolving(monkeypatch):
    tickers._ticker_cache.clear()

    def throttled(symbol):
        raise YFRateLimitError()

    monkeypatch.setattr(tickers.yf, "Ticker", throttled)
    with pytest.raises(RateLimitError):
        tickers.get_ticker("US0378331005")


def test_get_ticker_empty_symbol_raises():
    with pytest.raises(ToolError):
        tickers.get_ticker("   ")


# --- upstream error normalization -----------------------------------------


def _ticker_raising_on(attr, exc):
    """A FakeTicker subclass whose ``attr`` access raises ``exc``."""

    def _raise(self):
        raise exc

    return type("Raising", (FakeTicker,), {attr: property(_raise)})()


# (attribute that fails, call that should trigger it)
_UPSTREAM_CASES = [
    ("fast_info", lambda: yahoo.get_quote("AAPL")),
    ("info", lambda: yahoo.get_company_info("AAPL")),
    ("income_stmt", lambda: yahoo.get_financials("AAPL")),
    ("dividends", lambda: yahoo.get_dividends("AAPL")),
    ("get_news", lambda: yahoo.get_news("AAPL")),
    ("recommendations", lambda: yahoo.get_recommendations("AAPL")),
    ("options", lambda: yahoo.get_options("AAPL")),
    ("get_earnings_dates", lambda: yahoo.get_earnings("AAPL")),
    ("earnings_estimate", lambda: yahoo.get_estimates("AAPL")),
    ("upgrades_downgrades", lambda: yahoo.get_upgrades_downgrades("AAPL")),
    ("major_holders", lambda: yahoo.get_holders("AAPL")),
    ("insider_transactions", lambda: yahoo.get_insider_activity("AAPL")),
    ("sec_filings", lambda: yahoo.get_sec_filings("AAPL")),
    ("calendar", lambda: yahoo.get_calendar("AAPL")),
]


@pytest.mark.parametrize("attr,call", _UPSTREAM_CASES)
def test_upstream_error_becomes_toolerror(monkeypatch, attr, call):
    monkeypatch.setattr(
        tickers, "get_ticker", lambda s: _ticker_raising_on(attr, RuntimeError("boom"))
    )
    with pytest.raises(ToolError) as exc_info:
        call()
    # A generic upstream error maps to a plain ToolError, not RateLimitError.
    assert not isinstance(exc_info.value, RateLimitError)


@pytest.mark.parametrize("attr,call", _UPSTREAM_CASES)
def test_upstream_rate_limit_becomes_rate_limit_error(monkeypatch, attr, call):
    monkeypatch.setattr(
        tickers, "get_ticker", lambda s: _ticker_raising_on(attr, YFRateLimitError())
    )
    with pytest.raises(RateLimitError):
        call()


def test_get_options_chain_upstream_error(monkeypatch):
    ticker = FakeTicker(options=("2024-01-19",))

    def boom(expiration):
        raise RuntimeError("chain failed")

    ticker.option_chain = boom
    monkeypatch.setattr(tickers, "get_ticker", lambda s: ticker)
    with pytest.raises(ToolError):
        yahoo.get_options("AAPL", expiration="2024-01-19")


def test_get_options_chain_rate_limit(monkeypatch):
    ticker = FakeTicker(options=("2024-01-19",))

    def boom(expiration):
        raise YFRateLimitError()

    ticker.option_chain = boom
    monkeypatch.setattr(tickers, "get_ticker", lambda s: ticker)
    with pytest.raises(RateLimitError):
        yahoo.get_options("AAPL", expiration="2024-01-19")
