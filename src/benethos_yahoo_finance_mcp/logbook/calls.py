"""One line per tool call, written by the wrapper every tool is registered with.

No tool writes its own. A call that returned is an INFO line with how much it
returned and how long it took, a call that raised is a WARNING naming the
error's class. Whether the answer came from the result cache is set by the
cache as the call runs, see :func:`cache_hit`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from . import _describe

_log = logging.getLogger(f"{_describe.PACKAGE}.tools")

# Set by the result cache when it answers, read back by the call's own line.
# A context variable rather than a global: calls run concurrently, each in a
# worker thread that carries its own copy of the context.
_served_from_cache: ContextVar[bool] = ContextVar("served_from_cache", default=False)


def cache_hit() -> None:
    """Note that the call running in this context was answered from the cache."""
    _served_from_cache.set(True)


@contextmanager
def watching_cache() -> Iterator[None]:
    """Scope :func:`cache_hit` to one call. :func:`was_cached` reads it inside."""
    token = _served_from_cache.set(False)
    try:
        yield
    finally:
        _served_from_cache.reset(token)


def was_cached() -> bool:
    return _served_from_cache.get()


def _head(tool: str, arguments: Mapping[str, Any]) -> str:
    subject = _describe.subject(arguments)
    return f"{tool} {subject}" if subject else tool


def read(tool: str, arguments: Mapping[str, Any], result: Any, seconds: float) -> None:
    """A call that returned, e.g. ``get_history SAP.DE 250 rows, truncated, 412 ms``.

    A counted subject, ``3 symbols``, is followed by a comma, a symbol is not.
    """
    head = _head(tool, arguments)
    tail = _describe.joined(
        _describe.size(result),
        _describe.millis(seconds),
        "cached" if was_cached() else "",
    )
    separator = ", " if head.endswith(" symbols") else " "
    _log.info("%s%s%s", head, separator, tail)


def ended(
    tool: str, arguments: Mapping[str, Any], error: BaseException, seconds: float
) -> None:
    """A call that raised, e.g. ``get_options SAP.DE failed: SymbolNotFoundError``."""
    _log.warning(
        "%s failed: %s, %s",
        _head(tool, arguments),
        _describe.error(error),
        _describe.millis(seconds),
    )


def arguments_refused(tool: str, fields: list[str]) -> None:
    """Arguments that failed the tool's schema. The field names, never the values."""
    _log.warning("%s refused arguments: %s", tool, ", ".join(fields) or "-")
