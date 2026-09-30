"""What a company reports: its profile, statements, dividends, shares,
news and corporate calendar."""

from __future__ import annotations

from typing import Any

from .. import cache
from ..errors import SymbolNotFoundError, ToolError
from ..formatting import MAX_ROWS, dataframe_to_records, to_jsonable
from . import tickers

# Fields surfaced from Ticker.info for get_company_info. A curated subset keeps
# the response small; the full info dict is large and noisy.
#
# "symbol" is deliberately absent. It used to sit first here, which meant the
# copy loop overwrote the echoed input with Yahoo's resolved ticker before
# returning — invisible for a ticker, but an ISIN went in and AAPL came back,
# while every other tool echoes what it was given. The resolved ticker is
# reported as "resolved_symbol" instead, and only when it actually differs.
_COMPANY_INFO_FIELDS = (
    "shortName",
    "longName",
    "quoteType",
    "exchange",
    "currency",
    "sector",
    "industry",
    "country",
    "city",
    "website",
    "fullTimeEmployees",
    "marketCap",
    "trailingPE",
    "forwardPE",
    "priceToBook",
    "dividendYield",
    "beta",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "longBusinessSummary",
)

# Maps the public ``statement`` argument to the Ticker attribute names. Only the
# income and cash-flow statements have a trailing-twelve-month (``ttm``) variant
# upstream; a balance sheet is a point-in-time snapshot, so it has none.
_STATEMENT_ATTRS = {
    "income": {
        "annual": "income_stmt",
        "quarterly": "quarterly_income_stmt",
        "ttm": "ttm_income_stmt",
    },
    "balance": {"annual": "balance_sheet", "quarterly": "quarterly_balance_sheet"},
    "cashflow": {
        "annual": "cashflow",
        "quarterly": "quarterly_cashflow",
        "ttm": "ttm_cashflow",
    },
}

_VALID_FREQS = ("annual", "quarterly", "ttm")


@cache.cached("company_info")
def get_company_info(symbol: str) -> dict[str, Any]:
    """Return a curated company profile and key statistics for ``symbol``."""
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load company info for {symbol!r}"):
        info = ticker.info or {}

    if not info or (info.get("quoteType") is None and info.get("shortName") is None):
        raise SymbolNotFoundError(symbol)

    profile: dict[str, Any] = {"symbol": tickers.normalize(symbol)}
    # yfinance swaps an ISIN for its ticker, found through Yahoo's search,
    # when it builds the Ticker, and `info` reports that ticker. Surface it,
    # since the caller has no other way to learn it, but never in place of
    # the echo.
    resolved = info.get("symbol")
    if resolved and resolved != profile["symbol"]:
        profile["resolved_symbol"] = resolved
    for field in _COMPANY_INFO_FIELDS:
        if field in info:
            profile[field] = to_jsonable(info.get(field))
    return profile


@cache.cached("financials")
def get_financials(
    symbol: str,
    *,
    statement: str = "income",
    freq: str = "annual",
    limit: int = MAX_ROWS,
) -> dict[str, Any]:
    """Return a financial statement for ``symbol``.

    ``statement`` is one of ``income``, ``balance``, ``cashflow``. ``freq`` is
    ``annual``, ``quarterly``, or ``ttm`` (trailing twelve months; income and
    cash-flow only). Each returned row is a line item; columns are reporting
    periods (most recent first).
    """
    statement = (statement or "").strip().lower()
    freq = (freq or "").strip().lower()
    if statement not in _STATEMENT_ATTRS:
        raise ToolError(
            f"Invalid statement {statement!r}, expected one of "
            f"{', '.join(_STATEMENT_ATTRS)}."
        )
    if freq not in _VALID_FREQS:
        raise ToolError(
            f"Invalid freq {freq!r}, expected one of {', '.join(_VALID_FREQS)}."
        )

    freq_map = _STATEMENT_ATTRS[statement]
    if freq not in freq_map:
        raise ToolError(
            f"Frequency {freq!r} is not available for the {statement!r} "
            f"statement. Available: {', '.join(freq_map)}."
        )

    attr = freq_map[freq]
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load {statement} statement for {symbol!r}"):
        df = getattr(ticker, attr)

    if df is None or df.empty:
        raise SymbolNotFoundError(symbol)

    # A statement is a set of line items, not a series, so no end of it is
    # safe to drop. It used to be capped at 60 rows with the tail kept, and
    # Apple's annual balance sheet has 69: Net Debt, Total Debt, Working
    # Capital and Tangible Book Value were among the nine that vanished
    # without a word. No statement comes near MAX_ROWS, so nothing is cut now,
    # and should one ever get there the rows keep Yahoo's order from the top.
    rows = dataframe_to_records(df, max_rows=limit, index_name="item", head=True)
    return {
        "symbol": tickers.normalize(symbol),
        "statement": statement,
        "freq": freq,
        "rows": rows,
    }


@cache.cached("dividends")
def get_dividends(symbol: str, *, limit: int = 250) -> dict[str, Any]:
    """Return historical dividends and stock splits for ``symbol``."""
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load dividends for {symbol!r}"):
        dividends = ticker.dividends
        splits = ticker.splits

    # yfinance tells the two empty cases apart, and so must the answer. A
    # symbol it cannot find yields None for both series, while a real
    # instrument that never paid or split, BRK-B or BTC-USD, yields empty
    # series. Only the first is an error. Probed live 2026-09-25.
    if dividends is None and splits is None:
        raise SymbolNotFoundError(symbol)

    def _series_records(series: Any, value_key: str) -> list[dict[str, Any]]:
        if series is None or series.empty:
            return []
        tail = series.tail(limit)
        return [
            {"date": to_jsonable(idx), value_key: to_jsonable(val)}
            for idx, val in tail.items()
        ]

    return {
        "symbol": tickers.normalize(symbol),
        "dividends": _series_records(dividends, "dividend"),
        "splits": _series_records(splits, "split_ratio"),
    }


# Yahoo serves at most this many articles per symbol, whatever count is asked
# for. Probed 2026-09-25 with get_news(count=30) for AAPL: ten came back.
_MAX_NEWS = 10


@cache.cached("news")
def get_news(symbol: str, *, limit: int = _MAX_NEWS) -> dict[str, Any]:
    """Return recent news headlines for ``symbol``."""
    limit = max(1, min(int(limit), _MAX_NEWS))
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load news for {symbol!r}"):
        raw = ticker.get_news(count=limit) or []

    articles: list[dict[str, Any]] = []
    for item in raw[:limit]:
        # yfinance nests the article under "content"; fall back to the item.
        content = item.get("content", item) if isinstance(item, dict) else {}
        provider = content.get("provider") or {}
        canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        articles.append(
            {
                "title": content.get("title"),
                "summary": content.get("summary") or content.get("description"),
                "publisher": provider.get("displayName"),
                "published": content.get("pubDate") or content.get("displayTime"),
                "url": canonical.get("url"),
            }
        )
    return {
        "symbol": tickers.normalize(symbol),
        "count": len(articles),
        "articles": articles,
    }


@cache.cached("calendar")
def get_calendar(symbol: str) -> dict[str, Any]:
    """Return upcoming corporate-calendar events for ``symbol``.

    Includes the next earnings date(s) with analyst estimate ranges and the next
    dividend / ex-dividend dates. Equity-only; empty for ETFs/funds/crypto.
    """
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load calendar for {symbol!r}"):
        cal = ticker.calendar

    if not cal:
        raise SymbolNotFoundError(symbol)

    return {"symbol": tickers.normalize(symbol), "calendar": to_jsonable(cal)}


@cache.cached("shares")
def get_shares(
    symbol: str,
    *,
    start: str | None = None,
    end: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return the shares-outstanding time series for ``symbol``.

    Each point is a date and the reported shares outstanding. ``start`` / ``end``
    (``YYYY-MM-DD``) optionally bound the range. Without ``start``, yfinance
    looks back 548 days (18 months) from ``end``, not over the whole history.
    Only the most recent ``limit`` points are returned.
    """
    start, end = tickers.checked_range(start, end)
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load shares for {symbol!r}"):
        series = ticker.get_shares_full(start=start, end=end)

    if series is None or len(series) == 0:
        raise SymbolNotFoundError(symbol)

    tail = series.tail(limit)
    rows = [
        {"date": to_jsonable(idx), "shares": to_jsonable(val)}
        for idx, val in tail.items()
    ]
    return {"symbol": tickers.normalize(symbol), "count": len(rows), "shares": rows}
