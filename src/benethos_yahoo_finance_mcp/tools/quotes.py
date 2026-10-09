"""Finding an instrument and its price: search, quotes, history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

_PERIOD_DESC = (
    "Look-back window: "
    + ", ".join(yahoo.PERIODS)
    + ", or any count of d, wk, mo or y such as 7mo. Ignored when 'start' is given."
)
_INTERVAL_DESC = (
    "Bar size. One of: "
    + ", ".join(yahoo.INTERVALS)
    + ". Intraday intervals only cover recent dates."
)


def search(
    query: Annotated[
        str, Field(description="Company name, ticker symbol, or ISIN to look up.")
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of matches to return.", ge=1, le=25),
    ] = 8,
) -> list[dict[str, Any]]:
    """Search Yahoo Finance by company name, ticker symbol, or ISIN.

    Use this to turn a company name into a Yahoo ``symbol`` that the other
    tools accept. They take an ISIN directly. Returns up to ``limit`` matches
    (1-25), each with its symbol, name, exchange, instrument type, sector and
    industry.
    """
    return yahoo.search(query, limit=limit)


def get_quote(symbol: Symbol) -> dict[str, Any]:
    """Get the current price and key intraday figures for a Yahoo symbol."""
    return yahoo.get_quote(symbol)


def get_quotes(
    symbols: Annotated[
        list[Annotated[str, Field(max_length=yahoo.tickers.SYMBOL_MAX)]],
        Field(
            description="Yahoo tickers or ISINs, e.g. ['AAPL', 'MSFT', "
            "'SAP.DE']. Not company names. Up to 50, extras are dropped."
        ),
    ],
) -> dict[str, Any]:
    """Get compact current quotes for several Yahoo symbols in one call.

    Use this to compare or fetch prices for multiple tickers at once. Each symbol
    is looked up individually and returns currency, last price, previous close,
    open, day high/low, and market cap. Symbols that return no data are listed
    under ``not_found`` rather than failing the whole call, and ``truncated``
    is set when more than 50 were passed.
    """
    return yahoo.get_quotes(symbols)


def get_history(
    symbol: Symbol,
    period: Annotated[str, Field(description=_PERIOD_DESC)] = "1mo",
    interval: Annotated[str, Field(description=_INTERVAL_DESC)] = "1d",
    start: Annotated[
        str | None,
        Field(description="Start date 'YYYY-MM-DD'. Overrides 'period' when set."),
    ] = None,
    end: Annotated[
        str | None,
        Field(
            description="End date 'YYYY-MM-DD', exclusive: for one day pass the "
            "day after. Used only together with 'start'."
        ),
    ] = None,
) -> dict[str, Any]:
    """Get historical OHLCV (open/high/low/close/volume) data for a symbol.

    Query a look-back ``period`` or an explicit ``start``/``end`` range. Results
    are capped at the most recent 250 rows, with ``truncated`` set when cut.
    """
    return yahoo.get_history(
        symbol, period=period, interval=interval, start=start, end=end
    )


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool, title in (
        (search, "Search instruments"),
        (get_quote, "Quote"),
        (get_quotes, "Quotes for several symbols"),
        (get_history, "Price history"),
    ):
        register_tool(server, tool, title)
