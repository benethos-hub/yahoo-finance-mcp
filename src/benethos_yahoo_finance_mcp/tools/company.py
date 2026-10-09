"""What a company reports: its profile, statements, dividends, news,
corporate calendar and shares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def get_company_info(symbol: Symbol) -> dict[str, Any]:
    """Get a company profile and key statistics for a Yahoo symbol.

    Returns name, sector/industry, location, employee count, and valuation
    metrics (market cap, trailing and forward P/E, P/B, beta, 52-week range,
    dividend yield) plus a business summary. For an ISIN, ``resolved_symbol``
    names the ticker it stands for.
    """
    return yahoo.get_company_info(symbol)


def get_financials(
    symbol: Symbol,
    statement: Annotated[
        str,
        Field(
            description="Which statement: 'income' (income statement), "
            "'balance' (balance sheet), or 'cashflow' (cash flow)."
        ),
    ] = "income",
    freq: Annotated[
        str,
        Field(
            description="Reporting frequency: 'annual', 'quarterly', or 'ttm' "
            "(trailing twelve months, income and cashflow only)."
        ),
    ] = "annual",
) -> dict[str, Any]:
    """Get a financial statement for a Yahoo symbol.

    Each row is a line item and each column a reporting period, most recent
    first.
    """
    return yahoo.get_financials(symbol, statement=statement, freq=freq)


def get_dividends(symbol: Symbol) -> dict[str, Any]:
    """Get the dividend and stock-split history for a Yahoo symbol."""
    return yahoo.get_dividends(symbol)


def get_news(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of headlines to return.", ge=1, le=10),
    ] = 10,
) -> dict[str, Any]:
    """Get recent news headlines for a Yahoo symbol (up to ``limit``, 1-10).

    Each article includes title, summary, publisher, publish time, and URL.
    """
    return yahoo.get_news(symbol, limit=limit)


def get_calendar(symbol: Symbol) -> dict[str, Any]:
    """Get upcoming corporate-calendar events for a Yahoo symbol.

    Returns the next earnings date(s) with analyst estimate ranges and the next
    dividend / ex-dividend dates. Equity-only: an ETF, fund or crypto symbol
    answers with an error that says so.
    """
    return yahoo.get_calendar(symbol)


def get_shares(
    symbol: Symbol,
    start: Annotated[
        str | None,
        Field(
            description="Start date 'YYYY-MM-DD'. Without it the series covers "
            "the last 18 months only."
        ),
    ] = None,
    end: Annotated[
        str | None,
        Field(
            description="End date 'YYYY-MM-DD' to bound the series (optional), "
            "after 'start'."
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of (most recent) data points to return.",
            ge=1,
            le=250,
        ),
    ] = 50,
) -> dict[str, Any]:
    """Get the shares-outstanding history for a Yahoo symbol.

    Each point is a date and the reported shares outstanding. Only the most
    recent ``limit`` points are returned. Without ``start`` the series covers
    the last 18 months, so pass one for anything older.
    """
    return yahoo.get_shares(symbol, start=start, end=end, limit=limit)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool, title in (
        (get_company_info, "Company profile"),
        (get_financials, "Financial statements"),
        (get_dividends, "Dividends and splits"),
        (get_news, "News"),
        (get_calendar, "Corporate calendar"),
        (get_shares, "Shares outstanding"),
    ):
        register_tool(server, tool, title)
