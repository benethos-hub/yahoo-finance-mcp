"""Shared error types for the Yahoo Finance MCP server.

Tools raise :class:`ToolError` for any condition that should be reported back
to the MCP client as a clean, human-readable message instead of an opaque
stack trace.
"""

from __future__ import annotations


class ToolError(Exception):
    """An error that should be surfaced to the MCP client as-is.

    Raise this for expected failure modes (unknown symbol, empty result set,
    invalid argument, upstream rate limiting) so the client receives a concise
    message rather than an internal traceback.
    """


class SymbolNotFoundError(ToolError):
    """Raised when a symbol cannot be resolved or returns no data."""

    def __init__(self, symbol: str) -> None:
        super().__init__(
            f"No data found for symbol {symbol!r}. "
            "Use the 'search' tool to look it up by name, ticker, or ISIN."
        )
        self.symbol = symbol


class RateLimitError(ToolError):
    """Raised when Yahoo Finance throttles requests.

    Yahoo's unofficial endpoints rate limit aggressively. This signals the
    client that the request should simply be retried later, rather than that
    anything is wrong with the arguments.
    """

    def __init__(self) -> None:
        super().__init__(
            "Yahoo Finance is rate limiting requests right now. "
            "Please wait a bit and try again."
        )
