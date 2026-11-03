"""Fund and ETF profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def get_fund_data(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of top holdings to return.",
            ge=1,
            le=yahoo.HOLDINGS_MAX,
        ),
    ] = 25,
) -> dict[str, Any]:
    """Get fund/ETF profile data for a Yahoo symbol.

    Returns the fund overview, key figures, asset-class and sector weightings,
    and the top holdings. The key figures are the expense ratio (with the
    category average), holdings turnover, total assets, and the returns year
    to date and averaged over three and five years. Ratios and returns are
    fractions, 0.0007 for 0.07%, and a figure Yahoo lacks is left out, which
    for European ETFs is often the returns and the size. Fund/ETF-only, raises
    for stocks and crypto, which have no fund data.
    """
    return yahoo.get_fund_data(symbol, limit=limit)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    register_tool(server, get_fund_data, "Fund profile")
