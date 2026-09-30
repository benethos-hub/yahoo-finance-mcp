"""Turning the values a line is given into the text it may carry.

Every rule about what reaches the log is applied here, so a new line cannot
forget one. The functions take whole values, a tool's arguments or its result,
and pick out only what is safe to write.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PACKAGE = "benethos_yahoo_finance_mcp"

# Longer than any ticker, ISIN or sector key, short enough for one line.
_SUBJECT_MAX = 32


def printable(text: str, limit: int = _SUBJECT_MAX) -> str:
    """``text`` with printable characters only, at most ``limit`` of them.

    A symbol or a key comes from the caller, and a line is written before
    Yahoo says whether it exists. A line break in it would forge a second log
    line, an escape sequence would reach a terminal, and nothing else bounds
    its length. A cut is marked with ``...``.
    """
    kept = "".join(ch for ch in text if ch.isprintable())
    return kept if len(kept) <= limit else kept[: limit - 3] + "..."


def subject(arguments: Mapping[str, Any]) -> str:
    """What a call was about: its symbol, its key, or how many symbols.

    A ticker, an ISIN or a sector key is a public identifier and tells the
    operator more than anything else could. A search query is free text a
    person typed and is never named, the line for a search has no subject.
    Both pass through :func:`printable`, since the caller chose them.
    """
    symbol = arguments.get("symbol")
    if isinstance(symbol, str) and symbol.strip():
        return printable(symbol.strip().upper())
    key = arguments.get("key")
    if isinstance(key, str) and key.strip():
        return printable(key.strip())
    symbols = arguments.get("symbols")
    if isinstance(symbols, list):
        return f"{len(symbols)} symbols"
    return ""


def size(result: Any) -> str:
    """How much a call returned, counted, never quoted.

    A list is a set of search matches. A multi-quote answer says how many
    symbols were found and how many were not. Anything else counts the rows
    across its list-valued fields, and says whether it was cut.
    """
    if isinstance(result, list):
        return f"{len(result)} matches"
    if not isinstance(result, Mapping):
        return ""
    if "not_found" in result and "quotes" in result:
        text = f"{len(result['quotes'])} found, {len(result['not_found'])} missing"
    else:
        lists = [value for value in result.values() if isinstance(value, list)]
        text = f"{sum(len(value) for value in lists)} rows" if lists else ""
    if result.get("truncated") is True:
        text = f"{text}, truncated" if text else "truncated"
    return text


def error(exc: BaseException) -> str:
    """An error by its class. Its text is written for the model, not the log."""
    return type(exc).__name__


def fault(exc: BaseException) -> str:
    """A failure of this machine rather than of a call, with its message.

    Kept for errors from the standard library, a locked SQLite file say, whose
    text says what went wrong and carries nothing a caller sent.
    """
    return f"{type(exc).__name__}: {exc}"


def millis(seconds: float) -> str:
    return f"{round(seconds * 1000)} ms"


def path_only(path: str) -> str:
    """A request path without its query string, which may carry a session."""
    return path.split("?", 1)[0]


def joined(*parts: str) -> str:
    """Parts separated by commas, empty ones left out."""
    return ", ".join(part for part in parts if part)
