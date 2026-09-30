"""Option chains."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from .. import yahoo
from ._base import Symbol, register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def get_options(
    symbol: Symbol,
    expiration: Annotated[
        str | None,
        Field(
            description="Expiration date 'YYYY-MM-DD' from the list returned when "
            "called without it. Omit to list available expiration dates."
        ),
    ] = None,
) -> dict[str, Any]:
    """Get the option chain for a Yahoo symbol.

    Call without ``expiration`` to list available expiration dates. Call with
    an ``expiration`` (``YYYY-MM-DD`` from that list) to get the calls and puts
    for that date, up to 60 strikes each centred on the current price, with
    ``truncated`` set when a wider chain was cut. Yahoo carries chains for
    US-listed instruments only, so a non-US symbol has none and that says
    nothing about the symbol.
    """
    return yahoo.get_options(symbol, expiration=expiration)


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    for tool in (get_options,):
        register_tool(server, tool)
