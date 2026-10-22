"""Unit tests for the company profile, statements, dividends, news, calendar and shares.

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

# --- get_financials -------------------------------------------------------


def test_get_financials_invalid_statement(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError):
        yahoo.get_financials("aapl", statement="bogus")


def test_get_financials_invalid_freq(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError):
        yahoo.get_financials("aapl", freq="weekly")


def test_get_financials_returns_rows(patch_ticker):
    df = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [100.0]},
        index=["Total Revenue"],
    )
    patch_ticker(FakeTicker(income_stmt=df))
    # Attribute name for income/annual is "income_stmt".
    out = yahoo.get_financials("aapl", statement="income", freq="annual")
    assert out["statement"] == "income"
    assert out["rows"][0]["item"] == "Total Revenue"


def test_get_financials_keeps_every_line_item_from_the_top(patch_ticker):
    """A long statement loses nothing, and the headline items come first.

    Apple's annual balance sheet has 69 rows. The old cap of 60 kept the tail
    and silently dropped Net Debt, Total Debt and seven more from the top.
    """
    items = ["Net Debt", "Total Debt"] + [f"Item {i}" for i in range(67)]
    df = pd.DataFrame({pd.Timestamp("2025-09-27"): range(len(items))}, index=items)
    patch_ticker(FakeTicker(balance_sheet=df))
    out = yahoo.get_financials("aapl", statement="balance")
    assert len(out["rows"]) == 69
    assert [r["item"] for r in out["rows"][:2]] == ["Net Debt", "Total Debt"]


def test_get_financials_ttm_uses_ttm_attr(patch_ticker):
    df = pd.DataFrame(
        {pd.Timestamp("2026-03-31"): [129174.0]},
        index=["Free Cash Flow"],
    )
    patch_ticker(FakeTicker(ttm_cashflow=df))
    out = yahoo.get_financials("aapl", statement="cashflow", freq="ttm")
    assert out["freq"] == "ttm"
    assert out["rows"][0]["item"] == "Free Cash Flow"


def test_get_financials_ttm_not_available_for_balance(patch_ticker):
    patch_ticker(FakeTicker())
    with pytest.raises(ToolError):
        yahoo.get_financials("aapl", statement="balance", freq="ttm")


# --- get_dividends --------------------------------------------------------


def test_get_dividends_unknown_symbol_raises(patch_ticker):
    """yfinance answers an unknown symbol with None for both series."""
    patch_ticker(FakeTicker(dividends=None, splits=None))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_dividends("nope")


def test_get_dividends_non_payer_is_not_an_error(patch_ticker):
    """A real instrument without dividends or splits gets empty lists."""
    empty = pd.Series([], dtype=float)
    patch_ticker(FakeTicker(dividends=empty, splits=empty))
    out = yahoo.get_dividends("brk-b")
    assert out["dividends"] == []
    assert out["splits"] == []


def test_get_dividends_returns_records(patch_ticker):
    div = pd.Series([0.5, 0.6], index=pd.DatetimeIndex(["2023-01-01", "2023-06-01"]))
    patch_ticker(FakeTicker(dividends=div, splits=None))
    out = yahoo.get_dividends("aapl")
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
    out = yahoo.get_news("aapl", limit=5)
    assert out["count"] == 1
    assert out["source"] == "ticker"
    article = out["articles"][0]
    assert article["title"] == "Headline"
    assert article["publisher"] == "Yahoo"
    assert article["url"] == "https://example.com"


def _searched(title, *related, stamp=1792681243):
    return {
        "uuid": title,
        "title": title,
        "publisher": "Investing.com",
        "link": f"https://finance.yahoo.com/{title}",
        "providerPublishTime": stamp,
        "type": "STORY",
        "relatedTickers": list(related),
    }


def test_get_news_does_not_search_when_the_ticker_has_articles(
    patch_ticker, patch_search
):
    patch_ticker(FakeTicker(news=[{"content": {"title": "Headline"}}]))
    yahoo.get_news("aapl")
    assert patch_search.calls == []


def test_get_news_falls_back_to_the_articles_the_search_tags_with_the_symbol(
    patch_ticker, patch_search
):
    """The search matches text, so only Yahoo's own tagging decides."""
    patch_ticker(FakeTicker(news=[]))
    patch_search.news = [
        _searched("about-apple", "AAPL", "2317.TW"),
        _searched("about-oracle", "ORCL"),
        _searched("untagged"),
    ]
    out = yahoo.get_news("aapl")
    assert out["source"] == "search"
    assert out["count"] == 1
    assert out["articles"] == [
        {
            "title": "about-apple",
            "summary": None,
            "publisher": "Investing.com",
            "published": "2026-10-22T15:00:43Z",
            "url": "https://finance.yahoo.com/about-apple",
        }
    ]
    [(query, kwargs)] = patch_search.calls
    assert query == "AAPL"
    assert kwargs == {"max_results": 0, "news_count": 20, "lists_count": 0}


def test_get_news_searches_the_symbol_an_isin_resolves_to(patch_ticker, patch_search):
    patch_ticker(FakeTicker(news=[], ticker="AAPL"))
    patch_search.news = [_searched("about-apple", "AAPL")]
    out = yahoo.get_news("us0378331005")
    assert out["symbol"] == "US0378331005"
    assert out["count"] == 1
    assert patch_search.calls[0][0] == "AAPL"


def test_get_news_fallback_keeps_to_the_limit(patch_ticker, patch_search):
    patch_ticker(FakeTicker(news=[]))
    patch_search.news = [_searched(f"a{i}", "AAPL") for i in range(15)]
    out = yahoo.get_news("aapl", limit=4)
    assert [a["title"] for a in out["articles"]] == ["a0", "a1", "a2", "a3"]


def test_get_news_without_articles_anywhere_counts_none(patch_ticker):
    patch_ticker(FakeTicker(news=[]))
    out = yahoo.get_news("sap.de")
    assert out == {"symbol": "SAP.DE", "count": 0, "source": "search", "articles": []}


def test_get_news_articles_have_one_shape_whatever_the_source(
    patch_ticker, patch_search
):
    patch_ticker(FakeTicker(news=[{"content": {"title": "Headline"}}]))
    from_ticker = yahoo.get_news("aapl")["articles"][0]
    patch_ticker(FakeTicker(news=[]))
    patch_search.news = [_searched("about-apple", "AAPL", stamp=None)]
    from_search = yahoo.get_news("aapl")["articles"][0]
    assert from_search["published"] is None
    assert list(from_search) == list(from_ticker)


def test_get_news_fallback_rate_limit_becomes_rate_limit_error(
    patch_ticker, monkeypatch
):
    def throttled(*a, **k):
        raise YFRateLimitError()

    patch_ticker(FakeTicker(news=[]))
    monkeypatch.setattr(tickers.yf, "Search", throttled)
    with pytest.raises(RateLimitError):
        yahoo.get_news("aapl")


def test_get_news_asks_yahoo_for_the_requested_count(patch_ticker):
    """The count goes upstream. Reading ``.news`` always asked for yfinance's
    default of ten, so the tool's old ceiling of 30 was never reachable."""
    ticker = patch_ticker(FakeTicker(news=[]))
    yahoo.get_news("aapl", limit=3)
    assert ticker.news_kwargs == {"count": 3}


def test_get_news_limit_is_capped_at_what_yahoo_serves(patch_ticker):
    ticker = patch_ticker(FakeTicker(news=[]))
    yahoo.get_news("aapl", limit=30)
    assert ticker.news_kwargs == {"count": 10}


# --- get_calendar ---------------------------------------------------------


def test_get_calendar_returns_events(patch_ticker):
    import datetime

    cal = {
        "Earnings Date": [datetime.date(2026, 7, 30)],
        "Earnings Average": 1.89,
        "Ex-Dividend Date": datetime.date(2026, 5, 11),
    }
    patch_ticker(FakeTicker(calendar=cal))
    out = yahoo.get_calendar("aapl")
    assert out["symbol"] == "AAPL"
    assert out["calendar"]["Earnings Date"] == ["2026-07-30"]
    assert out["calendar"]["Earnings Average"] == 1.89


def test_get_calendar_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(calendar={}))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_calendar("nope")


# --- get_shares -----------------------------------------------------------


def test_get_shares_returns_recent_points(patch_ticker):
    idx = pd.DatetimeIndex(["2024-01-01", "2024-06-01", "2024-12-01"])
    series = pd.Series([100, 110, 120], index=idx)
    ticker = patch_ticker(FakeTicker(shares_full=series))
    out = yahoo.get_shares("aapl", start="2024-01-01", limit=2)
    # Most recent points are kept (tail).
    assert out["count"] == 2
    assert out["shares"][-1]["shares"] == 120
    assert ticker.shares_full_kwargs == {"start": "2024-01-01", "end": None}


@pytest.mark.parametrize(
    "kwargs,starts",
    [
        ({"start": "01.01.2024"}, "Invalid start '01.01.2024'"),
        ({"end": "2024-13-01"}, "Invalid end '2024-13-01'"),
        ({"start": "2024-06-01", "end": "2024-01-01"}, "end '2024-01-01' must be"),
    ],
)
def test_get_shares_checks_its_dates_before_asking_yahoo(patch_ticker, kwargs, starts):
    """A wrong format brought strptime's text to the model, a range the wrong
    way round came back as "not found"."""
    ticker = patch_ticker(FakeTicker(shares_full=None))
    with pytest.raises(ToolError) as info:
        yahoo.get_shares("aapl", **kwargs)
    assert not isinstance(info.value, SymbolNotFoundError)
    assert str(info.value).startswith(starts)
    assert not hasattr(ticker, "shares_full_kwargs")


def test_get_shares_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(shares_full=pd.Series(dtype="float64")))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_shares("nope")


def test_get_shares_none_raises(patch_ticker):
    patch_ticker(FakeTicker(shares_full=None))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_shares("nope")


def test_get_shares_upstream_error(monkeypatch):
    class Boom(FakeTicker):
        def get_shares_full(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(tickers, "get_ticker", lambda s: Boom())
    with pytest.raises(ToolError):
        yahoo.get_shares("AAPL")


def test_get_shares_rate_limit(monkeypatch):
    class Throttled(FakeTicker):
        def get_shares_full(self, **kwargs):
            raise YFRateLimitError()

    monkeypatch.setattr(tickers, "get_ticker", lambda s: Throttled())
    with pytest.raises(RateLimitError):
        yahoo.get_shares("AAPL")


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
    info = yahoo.get_company_info("aapl")
    assert info["symbol"] == "AAPL"
    assert info["shortName"] == "Apple Inc."
    assert info["sector"] == "Technology"
    # Only curated fields are surfaced.
    assert "irrelevant" not in info


def test_get_company_info_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(info={}))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_company_info("nope")


def test_get_company_info_echoes_the_input_symbol(patch_ticker):
    """An ISIN in must not come back out as a ticker.

    yfinance resolves an ISIN to its ticker, which `info` then reports. That
    used to overwrite the echoed input, so this one tool answered `AAPL` to a
    question asked about `US0378331005` while every other tool echoed the ISIN.
    """
    patch_ticker(
        FakeTicker(
            info={"quoteType": "EQUITY", "shortName": "Apple Inc.", "symbol": "AAPL"}
        )
    )
    info = yahoo.get_company_info("US0378331005")
    assert info["symbol"] == "US0378331005"
    assert info["resolved_symbol"] == "AAPL"


def test_get_company_info_omits_resolved_symbol_when_identical(patch_ticker):
    """A plain ticker resolves to itself, so the extra field is just noise."""
    patch_ticker(
        FakeTicker(
            info={"quoteType": "EQUITY", "shortName": "Apple Inc.", "symbol": "AAPL"}
        )
    )
    info = yahoo.get_company_info("aapl")
    assert info["symbol"] == "AAPL"
    assert "resolved_symbol" not in info
