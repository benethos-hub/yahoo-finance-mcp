"""Who owns a company, who inside it trades, and what it files."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def get_holders(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of institutional/mutual-fund holders to "
            "return per list.",
            ge=1,
            le=100,
        ),
    ] = 25,
) -> dict[str, Any]:
    """Get the ownership breakdown for a Yahoo symbol.

    Returns the high-level holder summary (insider/institutional percentages)
    plus the top institutional and mutual-fund holders. Equity-only: an ETF,
    fund or crypto symbol answers with an error that says so.
    """
    return yahoo.get_holders(symbol, limit=limit)


def get_insider_activity(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of insider transactions/roster rows to return.",
            ge=1,
            le=100,
        ),
    ] = 50,
) -> dict[str, Any]:
    """Get insider trading activity for a Yahoo symbol.

    Returns individual insider transactions, a 6-month purchases/sales summary,
    and the current insider roster. Equity-only: an ETF, fund or crypto symbol
    answers with an error that says so.
    """
    return yahoo.get_insider_activity(symbol, limit=limit)


def get_sec_filings(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of filings to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Get recent SEC filings for a Yahoo symbol.

    Each entry has the filing date, type (e.g. ``10-K``, ``10-Q``, ``8-K``),
    title, the Yahoo EDGAR URL, and exhibit links. Only issuers registered with
    the U.S. SEC file there, so a non-US symbol has none, and neither do ETFs,
    funds or crypto. An empty result says nothing about the symbol.
    """
    return yahoo.get_sec_filings(symbol, limit=limit)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool in (
        get_holders,
        get_insider_activity,
        get_sec_filings,
    ):
        register_tool(server, tool)
