"""Unit tests for the yfinance client wrapper, with yfinance fully mocked."""

from __future__ import annotations

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from yahoo_finance_mcp import client
from yahoo_finance_mcp.errors import RateLimitError, SymbolNotFoundError, ToolError


class FakeTicker:
    """Stand-in for ``yf.Ticker`` exposing only what the client touches."""

    def __init__(self, **attrs):
        self._attrs = attrs

    def __getattr__(self, name):
        # Fallback for statement attrs (income_stmt, balance_sheet, ...) that
        # the client reads via getattr; defined properties take precedence.
        attrs = self.__dict__.get("_attrs", {})
        if name in attrs:
            return attrs[name]
        raise AttributeError(name)

    @property
    def fast_info(self):
        return self._attrs.get("fast_info", {})

    def history(self, **kwargs):
        self.history_kwargs = kwargs
        return self._attrs.get("history", pd.DataFrame())

    @property
    def info(self):
        return self._attrs.get("info", {})

    @property
    def dividends(self):
        return self._attrs.get("dividends")

    @property
    def splits(self):
        return self._attrs.get("splits")

    @property
    def news(self):
        return self._attrs.get("news", [])

    @property
    def recommendations(self):
        return self._attrs.get("recommendations")

    @property
    def analyst_price_targets(self):
        return self._attrs.get("analyst_price_targets")

    @property
    def options(self):
        return self._attrs.get("options", ())

    def option_chain(self, expiration):
        self.requested_expiration = expiration
        return self._attrs.get("option_chain")


@pytest.fixture
def patch_ticker(monkeypatch):
    """Patch ``client._get_ticker`` to return a supplied FakeTicker."""

    def _install(ticker: FakeTicker):
        monkeypatch.setattr(client, "_get_ticker", lambda symbol: ticker)
        return ticker

    return _install


# --- search ---------------------------------------------------------------


def test_search_requires_query():
    with pytest.raises(ToolError):
        client.search("   ")


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

    monkeypatch.setattr(client.yf, "Search", FakeSearch)
    out = client.search("apple", limit=5)
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

    monkeypatch.setattr(client.yf, "Search", boom)
    with pytest.raises(ToolError):
        client.search("apple")


def test_search_maps_rate_limit_to_rate_limit_error(monkeypatch):
    def throttled(*a, **k):
        raise YFRateLimitError()

    monkeypatch.setattr(client.yf, "Search", throttled)
    with pytest.raises(RateLimitError):
        client.search("apple")


def test_history_maps_rate_limit_to_rate_limit_error(monkeypatch):
    class Throttled(FakeTicker):
        def history(self, **kwargs):
            raise YFRateLimitError()

    monkeypatch.setattr(client, "_get_ticker", lambda symbol: Throttled())
    with pytest.raises(RateLimitError):
        client.get_history("aapl")


# --- get_quote ------------------------------------------------------------


def test_get_quote_returns_fields(patch_ticker):
    patch_ticker(FakeTicker(fast_info={"lastPrice": 100.0, "currency": "USD"}))
    quote = client.get_quote("aapl")
    assert quote["symbol"] == "AAPL"
    assert quote["lastPrice"] == 100.0
    assert quote["currency"] == "USD"


def test_get_quote_without_price_raises(patch_ticker):
    patch_ticker(FakeTicker(fast_info={"currency": "USD"}))
    with pytest.raises(SymbolNotFoundError):
        client.get_quote("nope")


# --- get_history ----------------------------------------------------------


def test_get_history_uses_period_when_no_start(patch_ticker):
    df = pd.DataFrame(
        {"Close": [1.0, 2.0]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="Date"),
    )
    ticker = patch_ticker(FakeTicker(history=df))
    out = client.get_history("aapl", period="5d", interval="1d")
    assert out["count"] == 2
    assert "period" in ticker.history_kwargs
    assert "start" not in ticker.history_kwargs


def test_get_history_uses_start_end_when_given(patch_ticker):
    df = pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2024-01-01"]))
    ticker = patch_ticker(FakeTicker(history=df))
    client.get_history("aapl", start="2024-01-01", end="2024-01-31")
    assert ticker.history_kwargs["start"] == "2024-01-01"
    assert ticker.history_kwargs["end"] == "2024-01-31"
    assert "period" not in ticker.history_kwargs


def test_get_history_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(history=pd.DataFrame()))
    with pytest.raises(SymbolNotFoundError):
        client.get_history("nope")


# --- get_financials -------------------------------------------------------


def test_get_financials_invalid_statement(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError):
        client.get_financials("aapl", statement="bogus")


def test_get_financials_invalid_freq(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError):
        client.get_financials("aapl", freq="weekly")


def test_get_financials_returns_rows(patch_ticker):
    df = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [100.0]},
        index=["Total Revenue"],
    )
    patch_ticker(FakeTicker(income_stmt=df))
    # Attribute name for income/annual is "income_stmt".
    out = client.get_financials("aapl", statement="income", freq="annual")
    assert out["statement"] == "income"
    assert out["rows"][0]["item"] == "Total Revenue"


# --- get_dividends --------------------------------------------------------


def test_get_dividends_handles_none(patch_ticker):
    patch_ticker(FakeTicker(dividends=None, splits=None))
    out = client.get_dividends("aapl")
    assert out["dividends"] == []
    assert out["splits"] == []


def test_get_dividends_returns_records(patch_ticker):
    div = pd.Series([0.5, 0.6], index=pd.DatetimeIndex(["2023-01-01", "2023-06-01"]))
    patch_ticker(FakeTicker(dividends=div, splits=None))
    out = client.get_dividends("aapl")
    assert len(out["dividends"]) == 2
    assert out["dividends"][0]["dividend"] == 0.5


# --- get_news -------------------------------------------------------------


def test_get_news_parses_nested_content(patch_ticker):
    news = [
        {
            "content": {
                "title": "Headline",
                "summary": "Body",
                "provider": {"displayName": "Yahoo"},
                "pubDate": "2024-01-01T00:00:00Z",
                "canonicalUrl": {"url": "https://example.com"},
            }
        }
    ]
    patch_ticker(FakeTicker(news=news))
    out = client.get_news("aapl", limit=5)
    assert out["count"] == 1
    article = out["articles"][0]
    assert article["title"] == "Headline"
    assert article["publisher"] == "Yahoo"
    assert article["url"] == "https://example.com"


# --- get_recommendations --------------------------------------------------


def test_get_recommendations_combines_trend_and_targets(patch_ticker):
    recs = pd.DataFrame({"period": ["0m"], "buy": [10]})
    patch_ticker(
        FakeTicker(
            recommendations=recs,
            analyst_price_targets={"mean": 200.0},
        )
    )
    out = client.get_recommendations("aapl")
    assert out["price_targets"] == {"mean": 200.0}
    assert out["recommendation_trend"][0]["buy"] == 10


def test_get_recommendations_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(recommendations=None, analyst_price_targets=None))
    with pytest.raises(SymbolNotFoundError):
        client.get_recommendations("nope")


# --- get_options ----------------------------------------------------------


def test_get_options_lists_expirations(patch_ticker):
    patch_ticker(FakeTicker(options=("2024-01-19", "2024-02-16")))
    out = client.get_options("aapl")
    assert out["expirations"] == ["2024-01-19", "2024-02-16"]


def test_get_options_unknown_expiration_raises(patch_ticker):
    patch_ticker(FakeTicker(options=("2024-01-19",)))
    with pytest.raises(ToolError):
        client.get_options("aapl", expiration="2030-01-01")


def test_get_options_no_options_raises(patch_ticker):
    patch_ticker(FakeTicker(options=()))
    with pytest.raises(SymbolNotFoundError):
        client.get_options("aapl")


def test_get_options_returns_chain(patch_ticker):
    import types

    calls = pd.DataFrame({"strike": [100.0]})
    puts = pd.DataFrame({"strike": [90.0]})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = client.get_options("aapl", expiration="2024-01-19")
    assert out["calls"][0]["strike"] == 100.0
    assert out["puts"][0]["strike"] == 90.0


def test_get_options_caps_rows(patch_ticker):
    import types

    calls = pd.DataFrame({"strike": list(range(100))})
    puts = pd.DataFrame({"strike": list(range(100))})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = client.get_options("aapl", expiration="2024-01-19", max_rows=5)
    assert len(out["calls"]) == 5
    assert len(out["puts"]) == 5


# --- get_company_info -----------------------------------------------------


def test_get_company_info_returns_curated_fields(patch_ticker):
    patch_ticker(
        FakeTicker(
            info={
                "quoteType": "EQUITY",
                "shortName": "Apple Inc.",
                "sector": "Technology",
                "marketCap": 3_000_000,
                "irrelevant": "dropped",
            }
        )
    )
    info = client.get_company_info("aapl")
    assert info["symbol"] == "AAPL"
    assert info["shortName"] == "Apple Inc."
    assert info["sector"] == "Technology"
    # Only curated fields are surfaced.
    assert "irrelevant" not in info


def test_get_company_info_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(info={}))
    with pytest.raises(SymbolNotFoundError):
        client.get_company_info("nope")


# --- search limit clamping ------------------------------------------------


def test_search_clamps_limit(monkeypatch):
    captured = {}

    class FakeSearch:
        def __init__(self, query, max_results=8, **kwargs):
            captured["max_results"] = max_results
            self.quotes = []

    monkeypatch.setattr(client.yf, "Search", FakeSearch)

    client.search("x", limit=999)
    assert captured["max_results"] == 25

    client.search("x", limit=0)
    assert captured["max_results"] == 1


# --- get_history truncation -----------------------------------------------


def test_get_history_truncates_and_flags(patch_ticker):
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({"Close": list(range(10))}, index=idx)
    patch_ticker(FakeTicker(history=df))
    out = client.get_history("aapl", max_rows=3)
    assert out["count"] == 3
    assert out["truncated"] is True
    # The most recent rows are kept (tail).
    assert out["rows"][-1]["Close"] == 9


# --- _get_ticker cache ----------------------------------------------------


def test_get_ticker_caches_and_is_case_insensitive(monkeypatch):
    client._ticker_cache.clear()
    constructed: list[str] = []

    def fake_ticker(symbol):
        constructed.append(symbol)
        return FakeTicker()

    monkeypatch.setattr(client.yf, "Ticker", fake_ticker)

    first = client._get_ticker("aapl")
    second = client._get_ticker("AAPL")
    assert first is second  # same cached instance
    assert constructed == ["AAPL"]  # built once, key upper-cased


def test_get_ticker_empty_symbol_raises():
    with pytest.raises(ToolError):
        client._get_ticker("   ")
