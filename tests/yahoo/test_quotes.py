"""Unit tests for search, get_quote, get_quotes and get_history.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
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

# --- search ---------------------------------------------------------------


def test_search_requires_query():
    with pytest.raises(ToolError):
        yahoo.search("   ")


def test_search_maps_quote_fields(monkeypatch):
    class FakeSearch:
        def __init__(self, *a, **k):
            self.quotes = [
                {
                    "symbol": "AAPL",
                    "longname": "Apple Inc.",
                    "exchDisp": "NASDAQ",
                    "typeDisp": "Equity",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                }
            ]

    monkeypatch.setattr(tickers.yf, "Search", FakeSearch)
    out = yahoo.search("apple", limit=5)
    assert out == [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "type": "Equity",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
    ]


def test_search_wraps_upstream_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(tickers.yf, "Search", boom)
    with pytest.raises(ToolError):
        yahoo.search("apple")


def test_search_maps_rate_limit_to_rate_limit_error(monkeypatch):
    def throttled(*a, **k):
        raise YFRateLimitError()

    monkeypatch.setattr(tickers.yf, "Search", throttled)
    with pytest.raises(RateLimitError):
        yahoo.search("apple")


def test_history_maps_rate_limit_to_rate_limit_error(monkeypatch):
    class Throttled(FakeTicker):
        def history(self, **kwargs):
            raise YFRateLimitError()

    monkeypatch.setattr(tickers, "get_ticker", lambda symbol: Throttled())
    with pytest.raises(RateLimitError):
        yahoo.get_history("aapl")


# --- get_quote ------------------------------------------------------------


def test_get_quote_returns_fields(patch_ticker):
    patch_ticker(FakeTicker(fast_info={"lastPrice": 100.0, "currency": "USD"}))
    quote = yahoo.get_quote("aapl")
    assert quote["symbol"] == "AAPL"
    assert quote["lastPrice"] == 100.0
    assert quote["currency"] == "USD"


def test_get_quote_without_price_raises(patch_ticker):
    patch_ticker(FakeTicker(fast_info={"currency": "USD"}))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_quote("nope")


# --- get_quotes -----------------------------------------------------------


def _patch_tickers(monkeypatch, mapping):
    """Patch _get_ticker to resolve each symbol from a {SYMBOL: FakeTicker} map."""
    monkeypatch.setattr(tickers, "get_ticker", lambda s: mapping[s.strip().upper()])


def test_get_quotes_unresolvable_isin_is_a_per_symbol_miss(monkeypatch):
    """One bad ISIN must not fail the whole batch."""
    good = FakeTicker(fast_info={"lastPrice": 1.0})

    def resolve(symbol):
        if symbol == "ZZ0000000009":
            raise SymbolNotFoundError(symbol)
        return good

    monkeypatch.setattr(tickers, "get_ticker", resolve)
    out = yahoo.get_quotes(["AAPL", "ZZ0000000009"])
    assert [q["symbol"] for q in out["quotes"]] == ["AAPL"]
    assert out["not_found"] == ["ZZ0000000009"]


def test_get_quotes_returns_rows(monkeypatch):
    _patch_tickers(
        monkeypatch,
        {
            "AAPL": FakeTicker(fast_info={"lastPrice": 100.0, "currency": "USD"}),
            "MSFT": FakeTicker(fast_info={"lastPrice": 200.0, "currency": "USD"}),
        },
    )
    out = yahoo.get_quotes(["aapl", "msft"])
    assert out["count"] == 2
    assert out["not_found"] == []
    assert out["truncated"] is False
    assert {q["symbol"] for q in out["quotes"]} == {"AAPL", "MSFT"}


def test_get_quotes_reports_not_found_per_symbol(monkeypatch):
    _patch_tickers(
        monkeypatch,
        {
            "AAPL": FakeTicker(fast_info={"lastPrice": 100.0}),
            "BADSYM": FakeTicker(fast_info={"currency": "USD"}),  # no lastPrice
        },
    )
    out = yahoo.get_quotes(["AAPL", "BADSYM"])
    assert out["count"] == 1
    assert out["quotes"][0]["symbol"] == "AAPL"
    assert out["not_found"] == ["BADSYM"]


def test_get_quotes_dedupes_and_is_case_insensitive(monkeypatch):
    _patch_tickers(
        monkeypatch,
        {"AAPL": FakeTicker(fast_info={"lastPrice": 100.0})},
    )
    out = yahoo.get_quotes(["aapl", "AAPL", " aapl "])
    assert out["count"] == 1


def test_get_quotes_caps_symbols(monkeypatch):
    _patch_tickers(
        monkeypatch,
        {f"S{i}": FakeTicker(fast_info={"lastPrice": float(i)}) for i in range(10)},
    )
    out = yahoo.get_quotes([f"s{i}" for i in range(10)], limit=3)
    assert out["count"] == 3
    assert out["truncated"] is True


def test_get_quotes_empty_input_raises():
    with pytest.raises(ToolError):
        yahoo.get_quotes([])


def test_get_quotes_blank_only_raises():
    with pytest.raises(ToolError):
        yahoo.get_quotes(["   ", ""])


def test_get_quotes_rate_limit(monkeypatch):
    class Throttled(FakeTicker):
        @property
        def fast_info(self):
            raise YFRateLimitError()

    monkeypatch.setattr(tickers, "get_ticker", lambda s: Throttled())
    with pytest.raises(RateLimitError):
        yahoo.get_quotes(["AAPL"])


def test_get_quotes_upstream_miss_is_per_symbol(monkeypatch):
    class Boom(FakeTicker):
        @property
        def fast_info(self):
            raise RuntimeError("network")

    monkeypatch.setattr(tickers, "get_ticker", lambda s: Boom())
    out = yahoo.get_quotes(["AAPL"])
    # A generic error is a per-symbol miss, not a hard failure.
    assert out["count"] == 0
    assert out["not_found"] == ["AAPL"]


# --- get_history ----------------------------------------------------------


def test_get_history_uses_period_when_no_start(patch_ticker):
    df = pd.DataFrame(
        {"Close": [1.0, 2.0]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="Date"),
    )
    ticker = patch_ticker(FakeTicker(history=df))
    out = yahoo.get_history("aapl", period="5d", interval="1d")
    assert out["count"] == 2
    assert "period" in ticker.history_kwargs
    assert "start" not in ticker.history_kwargs


def test_get_history_uses_start_end_when_given(patch_ticker):
    df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    ticker = patch_ticker(FakeTicker(history=df))
    yahoo.get_history("aapl", start="2024-01-01", end="2024-01-31")
    assert ticker.history_kwargs["start"] == "2024-01-01"
    assert ticker.history_kwargs["end"] == "2024-01-31"
    assert "period" not in ticker.history_kwargs


def test_get_history_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(history=pd.DataFrame()))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_history("nope")


# --- get_history arguments ------------------------------------------------
#
# Yahoo answers a period or interval it does not know with no rows, which used
# to come back as "symbol not found" and sent the model looking for a ticker
# that was right all along.


@pytest.mark.parametrize(
    "kwargs,named",
    [
        ({"period": "banana"}, "period"),
        ({"period": "0d"}, "period"),
        ({"interval": "3d"}, "interval"),
        ({"interval": "2h"}, "interval"),
        ({"start": "01.01.2024"}, "start"),
        ({"start": "2024-1-1"}, "start"),
        ({"start": "2024-02-30"}, "start"),
        ({"start": "2024-01-01", "end": "tomorrow"}, "end"),
    ],
)
def test_get_history_rejects_an_argument_before_asking_yahoo(
    patch_ticker, kwargs, named
):
    ticker = patch_ticker(FakeTicker(history=pd.DataFrame()))
    with pytest.raises(ToolError) as info:
        yahoo.get_history("aapl", **kwargs)
    assert not isinstance(info.value, SymbolNotFoundError)
    assert str(info.value).startswith(f"Invalid {named} ")
    assert not hasattr(ticker, "history_kwargs")  # Yahoo was never asked


def test_a_rejected_interval_lists_every_valid_one(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError) as info:
        yahoo.get_history("aapl", interval="3d")
    assert ", ".join(yahoo.INTERVALS) in str(info.value)


def test_a_rejected_period_lists_the_named_ones_and_the_shape(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError) as info:
        yahoo.get_history("aapl", period="banana")
    assert ", ".join(yahoo.PERIODS) in str(info.value)
    assert "7mo" in str(info.value)


@pytest.mark.parametrize("period", ["7mo", "3y", "2wk", "100y", "YTD", " 1MO "])
def test_get_history_passes_any_counted_period(patch_ticker, period):
    """Yahoo serves any count of d, wk, mo or y, not only the listed ones."""
    df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    ticker = patch_ticker(FakeTicker(history=df))
    out = yahoo.get_history("aapl", period=period)
    assert ticker.history_kwargs["period"] == period.strip().lower()
    assert out["period"] == period.strip().lower()


def test_get_history_passes_4h_and_writes_the_interval_as_yahoo_does(patch_ticker):
    df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    ticker = patch_ticker(FakeTicker(history=df))
    yahoo.get_history("aapl", interval="4H")
    assert ticker.history_kwargs["interval"] == "4h"


def test_no_intraday_bars_is_not_called_an_unknown_symbol(patch_ticker):
    """1m over a year is valid on its own and still empty: Yahoo keeps 8 days."""
    patch_ticker(FakeTicker(history=pd.DataFrame()))
    with pytest.raises(ToolError) as info:
        yahoo.get_history("aapl", period="1y", interval="1m")
    assert not isinstance(info.value, SymbolNotFoundError)
    message = str(info.value)
    assert message.startswith("No 1m bars for 'AAPL' in that range.")
    assert "last 8 days" in message
    assert "'search' tool" in message  # the symbol may still be the reason


def test_every_intraday_interval_knows_how_far_back_it_reaches():
    from benethos_yahoo_finance_mcp.yahoo import quotes

    daily_and_up = set(yahoo.INTERVALS) - set(quotes._INTRADAY_DAYS)
    assert daily_and_up == {"1d", "5d", "1wk", "1mo", "3mo"}


def test_get_history_checks_only_what_it_uses(patch_ticker):
    """``period`` is ignored next to ``start`` and ``end`` without it, so
    neither is checked there."""
    df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    patch_ticker(FakeTicker(history=df))
    assert yahoo.get_history("aapl", period="banana", start="2024-01-01")["count"]
    assert yahoo.get_history("aapl", end="tomorrow")["count"]


# --- search limit clamping ------------------------------------------------


def test_search_clamps_limit(monkeypatch):
    captured = {}

    class FakeSearch:
        def __init__(self, query, max_results=8, **kwargs):
            captured["max_results"] = max_results
            self.quotes = []

    monkeypatch.setattr(tickers.yf, "Search", FakeSearch)

    yahoo.search("x", limit=999)
    assert captured["max_results"] == 25

    yahoo.search("x", limit=0)
    assert captured["max_results"] == 1


# --- get_history truncation -----------------------------------------------


def test_get_history_truncates_and_flags(patch_ticker):
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({"Close": list(range(10))}, index=idx)
    patch_ticker(FakeTicker(history=df))
    out = yahoo.get_history("aapl", limit=3)
    assert out["count"] == 3
    assert out["truncated"] is True
    # The most recent rows are kept (tail).
    assert out["rows"][-1]["Close"] == 9
