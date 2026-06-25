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

    def get_earnings_dates(self, **kwargs):
        self.earnings_dates_kwargs = kwargs
        return self._attrs.get("earnings_dates")


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


# --- get_earnings ---------------------------------------------------------


def test_get_earnings_combines_dates_and_history(patch_ticker):
    dates = pd.DataFrame(
        {"EPS Estimate": [1.5], "Reported EPS": [1.6]},
        index=pd.DatetimeIndex(["2024-01-25"], name="Earnings Date"),
    )
    history = pd.DataFrame(
        {"epsActual": [1.6]},
        index=pd.Index(["1Q2024"], name="quarter"),
    )
    ticker = patch_ticker(FakeTicker(earnings_dates=dates, earnings_history=history))
    out = client.get_earnings("aapl", limit=8)
    assert out["symbol"] == "AAPL"
    assert out["earnings_dates"][0]["EPS Estimate"] == 1.5
    assert out["earnings_history"][0]["epsActual"] == 1.6
    assert ticker.earnings_dates_kwargs == {"limit": 8}


def test_get_earnings_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(earnings_dates=None, earnings_history=None))
    with pytest.raises(SymbolNotFoundError):
        client.get_earnings("nope")


# --- get_estimates --------------------------------------------------------


def test_get_estimates_returns_tables(patch_ticker):
    est = pd.DataFrame({"avg": [2.0]}, index=pd.Index(["0q"], name="period"))
    patch_ticker(
        FakeTicker(
            earnings_estimate=est,
            revenue_estimate=None,
            eps_trend=None,
            eps_revisions=None,
            growth_estimates=None,
        )
    )
    out = client.get_estimates("aapl")
    assert out["earnings_estimate"][0]["avg"] == 2.0
    assert out["revenue_estimate"] == []


def test_get_estimates_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            earnings_estimate=None,
            revenue_estimate=None,
            eps_trend=None,
            eps_revisions=None,
            growth_estimates=None,
        )
    )
    with pytest.raises(SymbolNotFoundError):
        client.get_estimates("nope")


# --- get_upgrades_downgrades ----------------------------------------------


def test_get_upgrades_downgrades_sorts_newest_first_and_caps(patch_ticker):
    idx = pd.DatetimeIndex(["2024-01-01", "2024-03-01", "2024-02-01"], name="GradeDate")
    df = pd.DataFrame(
        {"Firm": ["A", "B", "C"], "ToGrade": ["Buy", "Hold", "Sell"]}, index=idx
    )
    patch_ticker(FakeTicker(upgrades_downgrades=df))
    out = client.get_upgrades_downgrades("aapl", max_rows=2)
    assert len(out["changes"]) == 2
    # Newest first: 2024-03-01 (B) then 2024-02-01 (C).
    assert out["changes"][0]["Firm"] == "B"
    assert out["changes"][1]["Firm"] == "C"


def test_get_upgrades_downgrades_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(upgrades_downgrades=pd.DataFrame()))
    with pytest.raises(SymbolNotFoundError):
        client.get_upgrades_downgrades("nope")


# --- get_holders ----------------------------------------------------------


def test_get_holders_combines_lists(patch_ticker):
    major = pd.DataFrame(
        {"Value": [0.016, 0.65]},
        index=pd.Index(["insidersPercentHeld", "institutionsPercentHeld"]),
    )
    institutional = pd.DataFrame({"Holder": ["Blackrock"], "Shares": [100]})
    mutualfund = pd.DataFrame({"Holder": ["Vanguard 500"], "Shares": [50]})
    patch_ticker(
        FakeTicker(
            major_holders=major,
            institutional_holders=institutional,
            mutualfund_holders=mutualfund,
        )
    )
    out = client.get_holders("aapl")
    assert out["symbol"] == "AAPL"
    assert out["major_holders"][0]["metric"] == "insidersPercentHeld"
    assert out["institutional_holders"][0]["Holder"] == "Blackrock"
    assert out["mutualfund_holders"][0]["Holder"] == "Vanguard 500"


def test_get_holders_caps_rows(patch_ticker):
    institutional = pd.DataFrame({"Holder": [f"H{i}" for i in range(100)]})
    patch_ticker(
        FakeTicker(
            major_holders=None,
            institutional_holders=institutional,
            mutualfund_holders=None,
        )
    )
    out = client.get_holders("aapl", max_rows=5)
    assert len(out["institutional_holders"]) == 5


def test_get_holders_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            major_holders=None, institutional_holders=None, mutualfund_holders=None
        )
    )
    with pytest.raises(SymbolNotFoundError):
        client.get_holders("nope")


# --- get_insider_activity -------------------------------------------------


def test_get_insider_activity_combines_tables(patch_ticker):
    transactions = pd.DataFrame({"Insider": ["BORDERS BEN"], "Shares": [116]})
    purchases = pd.DataFrame(
        {"Insider Purchases Last 6m": ["Purchases"], "Shares": [10]}
    )
    roster = pd.DataFrame(
        {"Name": ["COOK TIMOTHY D"], "Shares Owned Directly": [3280420]}
    )
    patch_ticker(
        FakeTicker(
            insider_transactions=transactions,
            insider_purchases=purchases,
            insider_roster_holders=roster,
        )
    )
    out = client.get_insider_activity("aapl")
    assert out["transactions"][0]["Insider"] == "BORDERS BEN"
    assert out["purchases_summary"][0]["Shares"] == 10
    assert out["roster"][0]["Name"] == "COOK TIMOTHY D"


def test_get_insider_activity_caps_rows(patch_ticker):
    transactions = pd.DataFrame({"Insider": [f"I{i}" for i in range(100)]})
    patch_ticker(
        FakeTicker(
            insider_transactions=transactions,
            insider_purchases=None,
            insider_roster_holders=None,
        )
    )
    out = client.get_insider_activity("aapl", max_rows=5)
    assert len(out["transactions"]) == 5


def test_get_insider_activity_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            insider_transactions=None,
            insider_purchases=None,
            insider_roster_holders=None,
        )
    )
    with pytest.raises(SymbolNotFoundError):
        client.get_insider_activity("nope")


# --- get_sec_filings ------------------------------------------------------


def test_get_sec_filings_curates_fields(patch_ticker):
    import datetime

    filings = [
        {
            "date": datetime.date(2026, 5, 1),
            "epochDate": 1777593600,
            "type": "10-Q",
            "title": "Periodic Financial Reports",
            "edgarUrl": "https://example.com/10q",
            "exhibits": {"10-Q": "https://example.com/ex"},
            "maxAge": 1,
        }
    ]
    patch_ticker(FakeTicker(sec_filings=filings))
    out = client.get_sec_filings("aapl")
    assert out["count"] == 1
    item = out["filings"][0]
    assert item["type"] == "10-Q"
    assert item["date"] == "2026-05-01"
    assert item["url"] == "https://example.com/10q"
    assert item["exhibits"] == {"10-Q": "https://example.com/ex"}
    # Noisy fields are dropped.
    assert "epochDate" not in item
    assert "maxAge" not in item


def test_get_sec_filings_caps_rows(patch_ticker):
    filings = [{"type": "8-K", "title": str(i)} for i in range(50)]
    patch_ticker(FakeTicker(sec_filings=filings))
    out = client.get_sec_filings("aapl", limit=5)
    assert out["count"] == 5


def test_get_sec_filings_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(sec_filings=[]))
    with pytest.raises(SymbolNotFoundError):
        client.get_sec_filings("nope")


# --- get_calendar ---------------------------------------------------------


def test_get_calendar_returns_events(patch_ticker):
    import datetime

    cal = {
        "Earnings Date": [datetime.date(2026, 7, 30)],
        "Earnings Average": 1.89,
        "Ex-Dividend Date": datetime.date(2026, 5, 11),
    }
    patch_ticker(FakeTicker(calendar=cal))
    out = client.get_calendar("aapl")
    assert out["symbol"] == "AAPL"
    assert out["calendar"]["Earnings Date"] == ["2026-07-30"]
    assert out["calendar"]["Earnings Average"] == 1.89


def test_get_calendar_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(calendar={}))
    with pytest.raises(SymbolNotFoundError):
        client.get_calendar("nope")


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


# --- upstream error normalization -----------------------------------------


def _ticker_raising_on(attr, exc):
    """A FakeTicker subclass whose ``attr`` access raises ``exc``."""

    def _raise(self):
        raise exc

    return type("Raising", (FakeTicker,), {attr: property(_raise)})()


# (attribute that fails, call that should trigger it)
_UPSTREAM_CASES = [
    ("fast_info", lambda: client.get_quote("AAPL")),
    ("info", lambda: client.get_company_info("AAPL")),
    ("income_stmt", lambda: client.get_financials("AAPL")),
    ("dividends", lambda: client.get_dividends("AAPL")),
    ("news", lambda: client.get_news("AAPL")),
    ("recommendations", lambda: client.get_recommendations("AAPL")),
    ("options", lambda: client.get_options("AAPL")),
    ("get_earnings_dates", lambda: client.get_earnings("AAPL")),
    ("earnings_estimate", lambda: client.get_estimates("AAPL")),
    ("upgrades_downgrades", lambda: client.get_upgrades_downgrades("AAPL")),
    ("major_holders", lambda: client.get_holders("AAPL")),
    ("insider_transactions", lambda: client.get_insider_activity("AAPL")),
    ("sec_filings", lambda: client.get_sec_filings("AAPL")),
    ("calendar", lambda: client.get_calendar("AAPL")),
]


@pytest.mark.parametrize("attr,call", _UPSTREAM_CASES)
def test_upstream_error_becomes_toolerror(monkeypatch, attr, call):
    monkeypatch.setattr(
        client, "_get_ticker", lambda s: _ticker_raising_on(attr, RuntimeError("boom"))
    )
    with pytest.raises(ToolError) as exc_info:
        call()
    # A generic upstream error maps to a plain ToolError, not RateLimitError.
    assert not isinstance(exc_info.value, RateLimitError)


@pytest.mark.parametrize("attr,call", _UPSTREAM_CASES)
def test_upstream_rate_limit_becomes_rate_limit_error(monkeypatch, attr, call):
    monkeypatch.setattr(
        client, "_get_ticker", lambda s: _ticker_raising_on(attr, YFRateLimitError())
    )
    with pytest.raises(RateLimitError):
        call()


def test_get_options_chain_upstream_error(monkeypatch):
    ticker = FakeTicker(options=("2024-01-19",))

    def boom(expiration):
        raise RuntimeError("chain failed")

    ticker.option_chain = boom
    monkeypatch.setattr(client, "_get_ticker", lambda s: ticker)
    with pytest.raises(ToolError):
        client.get_options("AAPL", expiration="2024-01-19")


def test_get_options_chain_rate_limit(monkeypatch):
    ticker = FakeTicker(options=("2024-01-19",))

    def boom(expiration):
        raise YFRateLimitError()

    ticker.option_chain = boom
    monkeypatch.setattr(client, "_get_ticker", lambda s: ticker)
    with pytest.raises(RateLimitError):
        client.get_options("AAPL", expiration="2024-01-19")
