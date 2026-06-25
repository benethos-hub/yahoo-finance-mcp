"""Thin wrapper around :mod:`yfinance` with light in-memory caching.

This module isolates all direct yfinance usage so the MCP tools in ``server.py``
stay small and easy to test. yfinance talks to the unofficial Yahoo Finance
endpoints and can be rate limited, so ``Ticker`` objects are cached briefly to
avoid redundant network calls.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

import yfinance as yf
from yfinance.exceptions import YFDataException, YFRateLimitError

from . import cache
from .errors import RateLimitError, SymbolNotFoundError, ToolError
from .formatting import dataframe_to_records, to_jsonable

logger = logging.getLogger(__name__)


def _wrap_upstream(exc: Exception, message: str) -> ToolError:
    """Normalize an upstream yfinance exception into a ``ToolError``.

    Rate limiting gets a dedicated, actionable message; any other failure keeps
    the operation-specific context so the client knows what was being attempted.
    """
    if isinstance(exc, YFRateLimitError):
        return RateLimitError()
    return ToolError(f"{message}: {exc}")


# Time-to-live for cached Ticker objects, in seconds. Short enough that quotes
# stay fresh, long enough to coalesce bursts of related tool calls.
_TICKER_TTL = 60.0

_ticker_cache: dict[str, tuple[float, yf.Ticker]] = {}
_cache_lock = Lock()

# Fields surfaced from Ticker.fast_info for get_quote.
_QUOTE_FAST_FIELDS = (
    "currency",
    "exchange",
    "quoteType",
    "lastPrice",
    "previousClose",
    "open",
    "dayHigh",
    "dayLow",
    "lastVolume",
    "marketCap",
    "fiftyDayAverage",
    "twoHundredDayAverage",
    "yearHigh",
    "yearLow",
    "yearChange",
)


def _get_ticker(symbol: str) -> yf.Ticker:
    """Return a cached ``yf.Ticker`` for ``symbol`` (case-insensitive key)."""
    key = symbol.strip().upper()
    if not key:
        raise ToolError("A non-empty symbol is required.")

    now = time.monotonic()
    with _cache_lock:
        cached = _ticker_cache.get(key)
        if cached is not None and now - cached[0] < _TICKER_TTL:
            return cached[1]
        ticker = yf.Ticker(key)
        _ticker_cache[key] = (now, ticker)
        return ticker


@cache.cached("search")
def search(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Search Yahoo Finance by free text, ticker, or ISIN.

    Returns the matching instruments with their Yahoo ``symbol`` plus name,
    exchange, and type. The same endpoint resolves ISINs and tickers, so this
    doubles as symbol lookup.
    """
    query = (query or "").strip()
    if not query:
        raise ToolError("A non-empty search query is required.")

    limit = max(1, min(int(limit), 25))
    try:
        result = yf.Search(query, max_results=limit, news_count=0, lists_count=0)
        quotes = result.quotes or []
    except Exception as exc:  # noqa: BLE001 - normalize upstream errors
        raise _wrap_upstream(exc, f"Search failed for {query!r}") from exc

    matches: list[dict[str, Any]] = []
    for q in quotes[:limit]:
        matches.append(
            {
                "symbol": q.get("symbol"),
                "name": q.get("longname") or q.get("shortname"),
                "exchange": q.get("exchDisp") or q.get("exchange"),
                "type": q.get("typeDisp") or q.get("quoteType"),
                "sector": q.get("sector"),
                "industry": q.get("industry"),
            }
        )
    return matches


@cache.cached("quote")
def get_quote(symbol: str) -> dict[str, Any]:
    """Return the current quote and key intraday figures for ``symbol``."""
    ticker = _get_ticker(symbol)
    try:
        fast = ticker.fast_info
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load quote for {symbol!r}") from exc

    quote: dict[str, Any] = {"symbol": symbol.strip().upper()}
    have_data = False
    for field in _QUOTE_FAST_FIELDS:
        try:
            value = fast.get(field)
        except YFRateLimitError as exc:
            raise RateLimitError() from exc
        except Exception:  # noqa: BLE001 - some fields raise when unavailable
            value = None
        if value is not None:
            have_data = True
        quote[field] = to_jsonable(value)

    if not have_data or quote.get("lastPrice") is None:
        raise SymbolNotFoundError(symbol)
    return quote


@cache.cached("history")
def get_history(
    symbol: str,
    *,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    max_rows: int = 250,
) -> dict[str, Any]:
    """Return historical OHLCV data for ``symbol``.

    ``period`` is ignored when ``start`` is given. See Yahoo's accepted values
    for ``period`` (e.g. ``1d``, ``5d``, ``1mo``, ``1y``, ``max``) and
    ``interval`` (e.g. ``1m``, ``1h``, ``1d``, ``1wk``, ``1mo``).
    """
    ticker = _get_ticker(symbol)
    kwargs: dict[str, Any] = {"interval": interval, "auto_adjust": True}
    if start:
        kwargs["start"] = start
        if end:
            kwargs["end"] = end
    else:
        kwargs["period"] = period

    try:
        df = ticker.history(**kwargs)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load history for {symbol!r}") from exc

    if df is None or df.empty:
        raise SymbolNotFoundError(symbol)

    rows = dataframe_to_records(df, max_rows=max_rows, index_name="date")
    return {
        "symbol": symbol.strip().upper(),
        "interval": interval,
        "period": None if start else period,
        "start": start,
        "end": end,
        "count": len(rows),
        "truncated": len(df) > len(rows),
        "rows": rows,
    }


# Fields surfaced from Ticker.info for get_company_info. A curated subset keeps
# the response small; the full info dict is large and noisy.
_COMPANY_INFO_FIELDS = (
    "symbol",
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
    ticker = _get_ticker(symbol)
    try:
        info = ticker.info or {}
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load company info for {symbol!r}"
        ) from exc

    if not info or info.get("quoteType") is None and info.get("shortName") is None:
        raise SymbolNotFoundError(symbol)

    profile: dict[str, Any] = {"symbol": symbol.strip().upper()}
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
    max_rows: int = 60,
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
            f"Invalid statement {statement!r}; expected one of "
            f"{', '.join(_STATEMENT_ATTRS)}."
        )
    if freq not in _VALID_FREQS:
        raise ToolError(
            f"Invalid freq {freq!r}; expected one of {', '.join(_VALID_FREQS)}."
        )

    freq_map = _STATEMENT_ATTRS[statement]
    if freq not in freq_map:
        raise ToolError(
            f"Frequency {freq!r} is not available for the {statement!r} "
            f"statement; available: {', '.join(freq_map)}."
        )

    attr = freq_map[freq]
    ticker = _get_ticker(symbol)
    try:
        df = getattr(ticker, attr)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load {statement} statement for {symbol!r}"
        ) from exc

    if df is None or df.empty:
        raise SymbolNotFoundError(symbol)

    rows = dataframe_to_records(df, max_rows=max_rows, index_name="item")
    return {
        "symbol": symbol.strip().upper(),
        "statement": statement,
        "freq": freq,
        "rows": rows,
    }


@cache.cached("dividends")
def get_dividends(symbol: str, *, max_rows: int = 250) -> dict[str, Any]:
    """Return historical dividends and stock splits for ``symbol``."""
    ticker = _get_ticker(symbol)
    try:
        dividends = ticker.dividends
        splits = ticker.splits
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load dividends for {symbol!r}") from exc

    def _series_records(series: Any, value_key: str) -> list[dict[str, Any]]:
        if series is None or series.empty:
            return []
        tail = series.tail(max_rows)
        return [
            {"date": to_jsonable(idx), value_key: to_jsonable(val)}
            for idx, val in tail.items()
        ]

    return {
        "symbol": symbol.strip().upper(),
        "dividends": _series_records(dividends, "dividend"),
        "splits": _series_records(splits, "split_ratio"),
    }


@cache.cached("news")
def get_news(symbol: str, *, limit: int = 10) -> dict[str, Any]:
    """Return recent news headlines for ``symbol``."""
    limit = max(1, min(int(limit), 30))
    ticker = _get_ticker(symbol)
    try:
        raw = ticker.news or []
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load news for {symbol!r}") from exc

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
        "symbol": symbol.strip().upper(),
        "count": len(articles),
        "articles": articles,
    }


@cache.cached("recommendations")
def get_recommendations(symbol: str) -> dict[str, Any]:
    """Return analyst recommendation trends and price targets for ``symbol``."""
    ticker = _get_ticker(symbol)
    try:
        recs = ticker.recommendations
        targets = ticker.analyst_price_targets
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load recommendations for {symbol!r}"
        ) from exc

    trend = dataframe_to_records(recs, max_rows=12) if recs is not None else []
    if not trend and not targets:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": symbol.strip().upper(),
        "price_targets": to_jsonable(targets) if targets else None,
        "recommendation_trend": trend,
    }


@cache.cached("options")
def get_options(
    symbol: str,
    *,
    expiration: str | None = None,
    max_rows: int = 60,
) -> dict[str, Any]:
    """Return the option chain for ``symbol``.

    Without ``expiration`` the available expiration dates are returned. With an
    ``expiration`` (``YYYY-MM-DD``, one of the listed dates) the calls and puts
    for that date are returned (capped at ``max_rows`` each).
    """
    ticker = _get_ticker(symbol)
    try:
        expirations = list(ticker.options or ())
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load options for {symbol!r}") from exc

    if not expirations:
        raise SymbolNotFoundError(symbol)

    if not expiration:
        return {"symbol": symbol.strip().upper(), "expirations": expirations}

    if expiration not in expirations:
        raise ToolError(
            f"Expiration {expiration!r} is not available for {symbol!r}. "
            f"Available: {', '.join(expirations[:10])}"
            + (" ..." if len(expirations) > 10 else "")
        )

    try:
        chain = ticker.option_chain(expiration)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load option chain for {symbol!r} {expiration}"
        ) from exc

    return {
        "symbol": symbol.strip().upper(),
        "expiration": expiration,
        "calls": dataframe_to_records(chain.calls, max_rows=max_rows),
        "puts": dataframe_to_records(chain.puts, max_rows=max_rows),
    }


@cache.cached("earnings")
def get_earnings(symbol: str, *, limit: int = 12) -> dict[str, Any]:
    """Return upcoming and historical earnings for ``symbol``.

    Combines the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) with the recent earnings history. Equity-only;
    empty for ETFs/funds/crypto.
    """
    limit = max(1, min(int(limit), 50))
    ticker = _get_ticker(symbol)
    try:
        dates = ticker.get_earnings_dates(limit=limit)
        history = ticker.earnings_history
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load earnings for {symbol!r}") from exc

    dates_rows = (
        dataframe_to_records(dates, max_rows=limit, index_name="earnings_date")
        if dates is not None
        else []
    )
    history_rows = (
        dataframe_to_records(history, max_rows=limit, index_name="quarter")
        if history is not None
        else []
    )
    if not dates_rows and not history_rows:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": symbol.strip().upper(),
        "earnings_dates": dates_rows,
        "earnings_history": history_rows,
    }


# Maps the output key to the Ticker attribute for the analyst-estimate tables.
_ESTIMATE_ATTRS = {
    "earnings_estimate": "earnings_estimate",
    "revenue_estimate": "revenue_estimate",
    "eps_trend": "eps_trend",
    "eps_revisions": "eps_revisions",
    "growth_estimates": "growth_estimates",
}


@cache.cached("estimates")
def get_estimates(symbol: str) -> dict[str, Any]:
    """Return forward analyst estimates for ``symbol``.

    Includes earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (each a small table keyed by period). Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = _get_ticker(symbol)
    out: dict[str, Any] = {"symbol": symbol.strip().upper()}
    have_data = False
    for key, attr in _ESTIMATE_ATTRS.items():
        try:
            df = getattr(ticker, attr)
        except Exception as exc:  # noqa: BLE001
            raise _wrap_upstream(
                exc, f"Failed to load estimates for {symbol!r}"
            ) from exc
        rows = (
            dataframe_to_records(df, max_rows=12, index_name="period")
            if df is not None
            else []
        )
        if rows:
            have_data = True
        out[key] = rows

    if not have_data:
        raise SymbolNotFoundError(symbol)
    return out


@cache.cached("upgrades_downgrades")
def get_upgrades_downgrades(symbol: str, *, max_rows: int = 50) -> dict[str, Any]:
    """Return recent analyst rating changes for ``symbol``.

    Each entry is a firm's upgrade/downgrade with the from/to grade and action,
    most recent first. Equity-only; empty for ETFs/funds/crypto.
    """
    ticker = _get_ticker(symbol)
    try:
        df = ticker.upgrades_downgrades
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load upgrades/downgrades for {symbol!r}"
        ) from exc

    if df is not None and not df.empty:
        # Source order varies; sort newest-first and cap.
        df = df.sort_index(ascending=False).head(max_rows)
    rows = (
        dataframe_to_records(df, max_rows=max_rows, index_name="date")
        if df is not None
        else []
    )
    if not rows:
        raise SymbolNotFoundError(symbol)

    return {"symbol": symbol.strip().upper(), "changes": rows}


@cache.cached("holders")
def get_holders(symbol: str, *, max_rows: int = 25) -> dict[str, Any]:
    """Return the ownership breakdown for ``symbol``.

    Combines the high-level holder summary (insider/institutional percentages)
    with the top institutional and mutual-fund holders. Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = _get_ticker(symbol)
    try:
        major = ticker.major_holders
        institutional = ticker.institutional_holders
        mutualfund = ticker.mutualfund_holders
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load holders for {symbol!r}") from exc

    major_rows = (
        dataframe_to_records(major, max_rows=10, index_name="metric")
        if major is not None
        else []
    )
    # Both lists are sorted largest-holder-first; keep the top rows (head), not
    # the tail that dataframe_to_records would otherwise retain when capping.
    institutional_rows = (
        dataframe_to_records(institutional.head(max_rows))
        if institutional is not None
        else []
    )
    mutualfund_rows = (
        dataframe_to_records(mutualfund.head(max_rows))
        if mutualfund is not None
        else []
    )
    if not major_rows and not institutional_rows and not mutualfund_rows:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": symbol.strip().upper(),
        "major_holders": major_rows,
        "institutional_holders": institutional_rows,
        "mutualfund_holders": mutualfund_rows,
    }


@cache.cached("insider_activity")
def get_insider_activity(symbol: str, *, max_rows: int = 50) -> dict[str, Any]:
    """Return insider trading activity for ``symbol``.

    Combines individual insider transactions, a 6-month purchases/sales summary,
    and the current insider roster (with shares owned). Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = _get_ticker(symbol)
    try:
        transactions = ticker.insider_transactions
        purchases = ticker.insider_purchases
        roster = ticker.insider_roster_holders
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(
            exc, f"Failed to load insider activity for {symbol!r}"
        ) from exc

    # Transactions are newest-first; keep the most recent (head), not the tail
    # that dataframe_to_records would retain when capping.
    transactions_rows = (
        dataframe_to_records(transactions.head(max_rows))
        if transactions is not None
        else []
    )
    purchases_rows = (
        dataframe_to_records(purchases, max_rows=10) if purchases is not None else []
    )
    roster_rows = (
        dataframe_to_records(roster.head(max_rows)) if roster is not None else []
    )
    if not transactions_rows and not purchases_rows and not roster_rows:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": symbol.strip().upper(),
        "transactions": transactions_rows,
        "purchases_summary": purchases_rows,
        "roster": roster_rows,
    }


@cache.cached("sec_filings")
def get_sec_filings(symbol: str, *, limit: int = 25) -> dict[str, Any]:
    """Return recent SEC filings for ``symbol``.

    Each entry has the filing date, type (e.g. ``10-K``, ``10-Q``, ``8-K``),
    title, the Yahoo EDGAR URL, and exhibit links. Equity-only; empty for
    ETFs/funds/crypto.
    """
    limit = max(1, min(int(limit), 100))
    ticker = _get_ticker(symbol)
    try:
        filings = ticker.sec_filings
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load SEC filings for {symbol!r}") from exc

    items: list[dict[str, Any]] = []
    for filing in list(filings or [])[:limit]:
        if not isinstance(filing, dict):
            continue
        items.append(
            {
                "date": to_jsonable(filing.get("date")),
                "type": filing.get("type"),
                "title": filing.get("title"),
                "url": filing.get("edgarUrl"),
                "exhibits": to_jsonable(filing.get("exhibits")),
            }
        )
    if not items:
        raise SymbolNotFoundError(symbol)

    return {"symbol": symbol.strip().upper(), "count": len(items), "filings": items}


@cache.cached("calendar")
def get_calendar(symbol: str) -> dict[str, Any]:
    """Return upcoming corporate-calendar events for ``symbol``.

    Includes the next earnings date(s) with analyst estimate ranges and the next
    dividend / ex-dividend dates. Equity-only; empty for ETFs/funds/crypto.
    """
    ticker = _get_ticker(symbol)
    try:
        cal = ticker.calendar
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load calendar for {symbol!r}") from exc

    if not cal:
        raise SymbolNotFoundError(symbol)

    return {"symbol": symbol.strip().upper(), "calendar": to_jsonable(cal)}


@cache.cached("shares")
def get_shares(
    symbol: str,
    *,
    start: str | None = None,
    end: str | None = None,
    max_rows: int = 50,
) -> dict[str, Any]:
    """Return the shares-outstanding time series for ``symbol``.

    Each point is a date and the reported shares outstanding. ``start`` / ``end``
    (``YYYY-MM-DD``) optionally bound the range; otherwise the full available
    history is used. Only the most recent ``max_rows`` points are returned.
    """
    ticker = _get_ticker(symbol)
    try:
        series = ticker.get_shares_full(start=start, end=end)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load shares for {symbol!r}") from exc

    if series is None or len(series) == 0:
        raise SymbolNotFoundError(symbol)

    tail = series.tail(max_rows)
    rows = [
        {"date": to_jsonable(idx), "shares": to_jsonable(val)}
        for idx, val in tail.items()
    ]
    return {"symbol": symbol.strip().upper(), "count": len(rows), "shares": rows}


@cache.cached("fund_data")
def get_fund_data(symbol: str, *, max_rows: int = 25) -> dict[str, Any]:
    """Return fund/ETF profile data for ``symbol``.

    Includes the fund overview, asset-class and sector weightings, and the top
    holdings. Fund/ETF-only; raises for stocks and crypto, which have no fund
    data.
    """
    ticker = _get_ticker(symbol)
    try:
        fd = ticker.funds_data
        description = fd.description
        overview = fd.fund_overview
        asset_classes = fd.asset_classes
        sector_weightings = fd.sector_weightings
        top_holdings = fd.top_holdings
    except YFRateLimitError as exc:
        raise RateLimitError() from exc
    except YFDataException as exc:
        # Raised for non-funds (stocks/crypto have no fund data).
        raise SymbolNotFoundError(symbol) from exc
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load fund data for {symbol!r}") from exc

    holdings_rows = (
        dataframe_to_records(top_holdings.head(max_rows), index_name="symbol")
        if top_holdings is not None
        else []
    )
    return {
        "symbol": symbol.strip().upper(),
        "description": description,
        "fund_overview": to_jsonable(overview),
        "asset_classes": to_jsonable(asset_classes),
        "sector_weightings": to_jsonable(sector_weightings),
        "top_holdings": holdings_rows,
    }


# Sector/industry keys are sourced from yfinance's own constant so they stay in
# sync with upstream. That constant is semi-internal (note the upstream typo in
# its name), so the import is defensive: if it is ever renamed or removed we fall
# back to a known-good snapshot of the 11 sector keys, and correctness never
# depends on this list alone — an invalid key is still caught at runtime when
# yfinance returns no data.
_FALLBACK_SECTOR_KEYS = (
    "basic-materials",
    "communication-services",
    "consumer-cyclical",
    "consumer-defensive",
    "energy",
    "financial-services",
    "healthcare",
    "industrials",
    "real-estate",
    "technology",
    "utilities",
)

try:
    from yfinance.const import (
        SECTOR_INDUSTY_MAPPING_LC as _SECTOR_INDUSTRY_MAP_RAW,
    )

    SECTOR_INDUSTRY_MAP: dict[str, tuple[str, ...]] = {
        str(sec): tuple(inds) for sec, inds in _SECTOR_INDUSTRY_MAP_RAW.items()
    }
except Exception:  # noqa: BLE001 - constant is semi-internal; degrade gracefully
    logger.warning(
        "yfinance.const sector mapping unavailable; "
        "falling back to a static sector list."
    )
    SECTOR_INDUSTRY_MAP = {key: () for key in _FALLBACK_SECTOR_KEYS}

# Public, derived from the mapping above (single source of truth for code + docs).
SECTOR_KEYS: tuple[str, ...] = tuple(SECTOR_INDUSTRY_MAP)
# Flat set of all valid industry keys; empty only if the fallback is in effect,
# in which case industry validation defers entirely to the runtime check.
INDUSTRY_KEYS: frozenset[str] = frozenset(
    ind for inds in SECTOR_INDUSTRY_MAP.values() for ind in inds
)


@cache.cached("sector")
def get_sector(key: str, *, max_rows: int = 25) -> dict[str, Any]:
    """Return an overview of a market sector by its Yahoo ``key``.

    ``key`` is one of Yahoo's fixed sector keys (e.g. ``technology``,
    ``healthcare``, ``financial-services``). Returns the sector overview, top
    companies/ETFs/mutual funds, and the constituent industries (whose ``key``
    feeds :func:`get_industry`).
    """
    key = (key or "").strip().lower()
    if not key:
        raise ToolError("A non-empty sector key is required.")
    if key not in SECTOR_KEYS:
        raise ToolError(
            f"Unknown sector key {key!r}. Valid keys: {', '.join(SECTOR_KEYS)}."
        )

    try:
        sector = yf.Sector(key)
        name = sector.name
        index_symbol = sector.symbol
        overview = sector.overview
        top_companies = sector.top_companies
        top_etfs = sector.top_etfs
        top_mutual_funds = sector.top_mutual_funds
        industries = sector.industries
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load sector {key!r}") from exc

    if not name:
        # Key is valid but yfinance returned no data (transient/upstream issue).
        raise SymbolNotFoundError(key)

    return {
        "key": key,
        "name": name,
        "index_symbol": index_symbol,
        "overview": to_jsonable(overview),
        "top_companies": (
            dataframe_to_records(top_companies.head(max_rows), index_name="symbol")
            if top_companies is not None
            else []
        ),
        "top_etfs": to_jsonable(top_etfs),
        "top_mutual_funds": to_jsonable(top_mutual_funds),
        "industries": (
            dataframe_to_records(industries, index_name="key")
            if industries is not None
            else []
        ),
    }


@cache.cached("industry")
def get_industry(key: str, *, max_rows: int = 25) -> dict[str, Any]:
    """Return an overview of an industry by its Yahoo ``key``.

    ``key`` is a Yahoo industry key (e.g. ``semiconductors``,
    ``software-infrastructure``); discover valid keys from the ``industries``
    list returned by :func:`get_sector`. Returns the industry overview, its
    parent sector, top companies, and the top-performing and top-growth
    companies.
    """
    key = (key or "").strip().lower()
    if not key:
        raise ToolError("A non-empty industry key is required.")
    # Offline pre-check when the upstream key set is known; otherwise defer to
    # the runtime check below.
    if INDUSTRY_KEYS and key not in INDUSTRY_KEYS:
        raise ToolError(
            f"Unknown industry key {key!r}. Discover valid keys from the "
            "'industries' list returned by get_sector."
        )

    try:
        industry = yf.Industry(key)
        name = industry.name
        index_symbol = industry.symbol
        sector_key = industry.sector_key
        sector_name = industry.sector_name
        overview = industry.overview
        top_companies = industry.top_companies
        top_performing = industry.top_performing_companies
        top_growth = industry.top_growth_companies
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load industry {key!r}") from exc

    if not name:
        # Key is valid but yfinance returned no data (transient/upstream issue).
        raise SymbolNotFoundError(key)

    return {
        "key": key,
        "name": name,
        "index_symbol": index_symbol,
        "sector_key": sector_key,
        "sector_name": sector_name,
        "overview": to_jsonable(overview),
        "top_companies": (
            dataframe_to_records(top_companies.head(max_rows), index_name="symbol")
            if top_companies is not None
            else []
        ),
        "top_performing_companies": (
            dataframe_to_records(top_performing, index_name="symbol")
            if top_performing is not None
            else []
        ),
        "top_growth_companies": (
            dataframe_to_records(top_growth, index_name="symbol")
            if top_growth is not None
            else []
        ),
    }
