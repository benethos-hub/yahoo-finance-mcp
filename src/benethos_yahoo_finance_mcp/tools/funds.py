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
        Field(description="Maximum number of top holdings to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Get fund/ETF profile data for a Yahoo symbol.

    Returns the fund overview, asset-class and sector weightings, and the top
    holdings. Fund/ETF-only, raises for stocks and crypto, which have no fund
    data.
    """
    return yahoo.get_fund_data(symbol, limit=limit)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool in (get_fund_data,):
        register_tool(server, tool)
