"""What analysts say: recommendations, earnings against estimates,
estimates and rating changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def get_recommendations(symbol: Symbol) -> dict[str, Any]:
    """Get analyst recommendation trends and price targets for a Yahoo symbol.

    Returns the buy/hold/sell trend over recent months plus current/high/low/
    mean/median analyst price targets when available.
    """
    return yahoo.get_recommendations(symbol)


def get_earnings(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of earnings rows to return.", ge=1, le=50),
    ] = 12,
) -> dict[str, Any]:
    """Get upcoming and historical earnings for a Yahoo symbol.

    Returns the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) plus the recent earnings history. Equity-only:
    an ETF, fund or crypto symbol answers with an error that says so.
    """
    return yahoo.get_earnings(symbol, limit=limit)


def get_estimates(symbol: Symbol) -> dict[str, Any]:
    """Get forward analyst estimates for a Yahoo symbol.

    Returns earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (small tables keyed by period). Equity-only: an ETF, fund or
    crypto symbol answers with an error that says so.
    """
    return yahoo.get_estimates(symbol)


def get_upgrades_downgrades(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of rating changes to return.", ge=1, le=100),
    ] = 50,
) -> dict[str, Any]:
    """Get recent analyst rating changes (upgrades/downgrades) for a Yahoo symbol.

    Each entry is a firm's rating change with the from/to grade and action, most
    recent first. Equity-only: an ETF, fund or crypto symbol answers with an
    error that says so.
    """
    return yahoo.get_upgrades_downgrades(symbol, limit=limit)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool in (
        get_recommendations,
        get_earnings,
        get_estimates,
        get_upgrades_downgrades,
    ):
        register_tool(server, tool)
