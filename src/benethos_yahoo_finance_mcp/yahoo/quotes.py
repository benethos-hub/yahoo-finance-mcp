"""Finding an instrument and its price: search, quotes, history."""

from __future__ import annotations

from typing import Any

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from .. import cache
from ..errors import RateLimitError, SymbolNotFoundError, ToolError
from ..formatting import dataframe_to_records
from . import tickers

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
    with tickers.upstream(f"Search failed for {query!r}"):
        result = yf.Search(query, max_results=limit, news_count=0, lists_count=0)
        quotes = result.quotes or []

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
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load quote for {symbol!r}"):
        fast = ticker.fast_info

    quote = {
        "symbol": tickers.normalize(symbol),
        **tickers.fast_fields(fast, _QUOTE_FAST_FIELDS),
    }
    if quote["lastPrice"] is None:
        raise SymbolNotFoundError(symbol)
    return quote


# Compact field subset for multi-symbol quotes (smaller per-symbol payload than
# get_quote, so many symbols stay within the client's token budget).
_QUOTES_FAST_FIELDS = (
    "currency",
    "lastPrice",
    "previousClose",
    "open",
    "dayHigh",
    "dayLow",
    "marketCap",
)

# Hard cap on the number of symbols a single get_quotes call may return.
_MAX_QUOTES = 50


# A call where every symbol missed is still a non-empty dict, so the default
# test would store it, and a momentary upstream hiccup would then answer every
# repeat of the call with "none found" for the whole TTL.
@cache.cached("quotes", worth_keeping=lambda result: result["count"] > 0)
def get_quotes(symbols: list[str], *, limit: int = _MAX_QUOTES) -> dict[str, Any]:
    """Return compact current quotes for several symbols at once.

    Each symbol is looked up individually; symbols that return no data are
    reported under ``not_found`` instead of failing the whole call.
    """
    if not symbols:
        raise ToolError("At least one symbol is required.")

    limit = max(1, min(int(limit), _MAX_QUOTES))
    # Normalize, drop blanks, de-duplicate (preserving order), and cap.
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in symbols:
        sym = tickers.normalize(raw)
        if sym and sym not in seen:
            seen.add(sym)
            cleaned.append(sym)
    if not cleaned:
        raise ToolError("At least one non-empty symbol is required.")
    truncated = len(cleaned) > limit
    cleaned = cleaned[:limit]

    quotes: list[dict[str, Any]] = []
    not_found: list[str] = []
    for sym in cleaned:
        try:
            ticker = tickers.get_ticker(sym)
        except SymbolNotFoundError:
            # An ISIN-shaped symbol Yahoo cannot resolve fails already here.
            not_found.append(sym)
            continue
        try:
            fast = ticker.fast_info
        except YFRateLimitError as exc:
            raise RateLimitError() from exc
        except Exception:  # noqa: BLE001 - treat as a per-symbol miss
            not_found.append(sym)
            continue

        row = {"symbol": sym, **tickers.fast_fields(fast, _QUOTES_FAST_FIELDS)}
        if row["lastPrice"] is None:
            not_found.append(sym)
        else:
            quotes.append(row)

    return {
        "count": len(quotes),
        "quotes": quotes,
        "not_found": not_found,
        "truncated": truncated,
    }


@cache.cached("history")
def get_history(
    symbol: str,
    *,
    period: str = "1mo",
    interval: str = "1d",
    start: str | None = None,
    end: str | None = None,
    limit: int = 250,
) -> dict[str, Any]:
    """Return historical OHLCV data for ``symbol``.

    ``period`` is ignored when ``start`` is given. See Yahoo's accepted values
    for ``period`` (e.g. ``1d``, ``5d``, ``1mo``, ``1y``, ``max``) and
    ``interval`` (e.g. ``1m``, ``1h``, ``1d``, ``1wk``, ``1mo``).
    """
    ticker = tickers.get_ticker(symbol)
    kwargs: dict[str, Any] = {"interval": interval, "auto_adjust": True}
    if start:
        kwargs["start"] = start
        if end:
            kwargs["end"] = end
    else:
        kwargs["period"] = period

    with tickers.upstream(f"Failed to load history for {symbol!r}"):
        df = ticker.history(**kwargs)

    if df is None or df.empty:
        raise SymbolNotFoundError(symbol)

    rows = dataframe_to_records(df, max_rows=limit, index_name="date")
    return {
        "symbol": tickers.normalize(symbol),
        "interval": interval,
        "period": None if start else period,
        "start": start,
        "end": end,
        "count": len(rows),
        "truncated": len(df) > len(rows),
        "rows": rows,
    }
