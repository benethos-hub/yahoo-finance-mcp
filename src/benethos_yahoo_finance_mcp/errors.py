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
    """Raised when a symbol cannot be resolved or returns no data.

    Some data is structurally unavailable for whole classes of perfectly valid
    symbols — Yahoo lists option chains for US instruments only, and only SEC
    registrants file with the SEC. For those, an empty result says nothing about
    whether the symbol exists, and the default advice to go and look it up sends
    the caller hunting for a ticker that was already correct. Pass ``reason`` to
    say so instead. Distinguishing the two cases for certain would take a second
    upstream request, which is deliberately not spent here.
    """

    def __init__(self, symbol: str, reason: str | None = None) -> None:
        if reason is None:
            message = (
                f"No data found for symbol {symbol!r}. "
                "Use the 'search' tool to look it up by name, ticker, or ISIN."
            )
        else:
            message = (
                f"No data for symbol {symbol!r}. {reason} An empty result here "
                "therefore does not show that the symbol is wrong. Use the "
                "'search' tool only if you doubt the symbol itself."
            )
        super().__init__(message)
        self.symbol = symbol
        self.reason = reason


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
