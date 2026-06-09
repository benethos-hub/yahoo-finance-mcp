"""Thin wrapper around :mod:`yfinance` with light in-memory caching.

This module isolates all direct yfinance usage so the MCP tools in
:mod:`yahoo_finance_mcp.server` stay small and easy to test. yfinance talks to
the unofficial Yahoo Finance endpoints and can be rate limited, so ``Ticker``
objects are cached briefly to avoid redundant network calls.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

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

_ticker_cache: dict[str, tuple[float, "yf.Ticker"]] = {}
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


def _get_ticker(symbol: str) -> "yf.Ticker":
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

# Maps the public ``statement`` argument to the Ticker attribute names.
_STATEMENT_ATTRS = {
    "income": {"annual": "income_stmt", "quarterly": "quarterly_income_stmt"},
    "balance": {"annual": "balance_sheet", "quarterly": "quarterly_balance_sheet"},
    "cashflow": {"annual": "cashflow", "quarterly": "quarterly_cashflow"},
}


def get_company_info(symbol: str) -> dict[str, Any]:
    """Return a curated company profile and key statistics for ``symbol``."""
    ticker = _get_ticker(symbol)
    try:
        info = ticker.info or {}
    except Exception as exc:  # noqa: BLE001
        raise _wrap_upstream(exc, f"Failed to load company info for {symbol!r}") from exc

    if not info or info.get("quoteType") is None and info.get("shortName") is None:
        raise SymbolNotFoundError(symbol)

    profile: dict[str, Any] = {"symbol": symbol.strip().upper()}
    for field in _COMPANY_INFO_FIELDS:
        if field in info:
            profile[field] = to_jsonable(info.get(field))
    return profile


def get_financials(
    symbol: str,
    *,
    statement: str = "income",
    freq: str = "annual",
    max_rows: int = 60,
) -> dict[str, Any]:
    """Return a financial statement for ``symbol``.

    ``statement`` is one of ``income``, ``balance``, ``cashflow``. ``freq`` is
    ``annual`` or ``quarterly``. Each returned row is a line item; columns are
    reporting periods (most recent first).
    """
    statement = (statement or "").strip().lower()
    freq = (freq or "").strip().lower()
    if statement not in _STATEMENT_ATTRS:
        raise ToolError(
            f"Invalid statement {statement!r}; expected one of "
            f"{', '.join(_STATEMENT_ATTRS)}."
        )
    if freq not in ("annual", "quarterly"):
        raise ToolError(f"Invalid freq {freq!r}; expected 'annual' or 'quarterly'.")

    attr = _STATEMENT_ATTRS[statement][freq]
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
    return {"symbol": symbol.strip().upper(), "count": len(articles), "articles": articles}


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
