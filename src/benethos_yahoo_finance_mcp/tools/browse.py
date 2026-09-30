"""Browsing by a fixed Yahoo key: sectors, industries and markets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


# Built from yfinance's own constant (via yahoo) so the tool description the
# LLM sees stays in sync with upstream's sector keys.
_SECTOR_KEYS_DESC = (
    "A Yahoo sector key (lowercase, hyphenated). One of: "
    + ", ".join(yahoo.SECTOR_KEYS)
    + "."
)


def get_sector(
    key: Annotated[
        str,
        Field(description=_SECTOR_KEYS_DESC),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of top companies to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Browse a market sector by its Yahoo key (not a ticker symbol).

    Returns the sector overview (company count, market cap/weight, description),
    its top companies, ETFs, and mutual funds, and the constituent industries.
    Each industry's ``key`` can be passed to ``get_industry`` to drill down.
    This takes a sector key like ``technology`` or ``healthcare`` — not a ticker.
    """
    return yahoo.get_sector(key, limit=limit)


def get_industry(
    key: Annotated[
        str,
        Field(
            description="A Yahoo industry key (lowercase, hyphenated), e.g. "
            "'semiconductors' or 'software-infrastructure'. Discover valid keys "
            "from the 'industries' list returned by get_sector."
        ),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of top companies to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Browse an industry by its Yahoo key (not a ticker symbol).

    Returns the industry overview, its parent sector, top companies, and the
    top-performing and top-growth companies. Discover valid industry keys from
    the ``industries`` list returned by ``get_sector``. This takes an industry
    key like ``semiconductors`` — not a ticker symbol.
    """
    return yahoo.get_industry(key, limit=limit)


def get_market(
    key: Annotated[
        str,
        Field(
            description="A Yahoo market key (uppercase). One of: "
            + ", ".join(yahoo.MARKET_KEYS)
            + ". Only 'US' reports a trading status, the others return the index "
            "summary with 'status' set to null."
        ),
    ] = "US",
) -> dict[str, Any]:
    """Get the trading status and headline index summary for a market.

    Answers questions like whether the market is open, when it opens or closes
    next, and how the major indices are doing. Takes a market key such as
    ``US`` or ``EUROPE`` — not a ticker symbol. ``status`` (open/closed plus the
    next open and close times) is only available for ``US`` and is ``null`` for
    every other key, which is an upstream limitation rather than an error. The
    index summary, with price, previous close and change, works for all keys.
    """
    return yahoo.get_market(key)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool in (
        get_sector,
        get_industry,
        get_market,
    ):
        register_tool(server, tool)
