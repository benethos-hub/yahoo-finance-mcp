"""Where the log goes: one handler, on stderr, installed by the command line.

stdout carries the MCP JSON-RPC stream under stdio, so nothing here ever
writes to it. Nothing is installed at import either. :func:`configure` is
called once from ``cli.main``, and a program that imports the package and
builds a server itself keeps whatever logging it set up.

A line another library writes is reduced to printable characters on its way
out, since it may quote what a caller sent.
"""

from __future__ import annotations

import logging
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager

from . import access, formats
from ._describe import PACKAGE, one_line

# The chosen level applies to this package (PACKAGE) and to uvicorn's request
# log. Everything else inherits the root logger's WARNING, so a library nobody
# listed, asyncio's DEBUG line about its event loop say, stays out of the log
# at every level.

# Libraries pinned at WARNING by name on top of that, because what they say
# below it is noise or must not be in the log at all, and a pin holds even
# where something else lowers the root logger. The SDK's ``mcp`` logger quotes
# the text of every failed call at INFO, and that text is written for the
# model. ``sse_starlette`` logs every chunk it streams at DEBUG, which is every
# tool result in full, Yahoo's data and all. A failure the SDK did not expect
# still comes through, as an ERROR with its traceback.
QUIET = (
    "mcp",
    "sse_starlette",
    "curl_cffi",
    "urllib3",
    "peewee",
    "httpx",
    "httpcore",
)

# Held at CRITICAL, which in practice means silent. yfinance logs an unknown
# symbol as up to four ERROR lines, one of them Yahoo's whole answer body,
# while the tool has already said "not found" in a line of its own, or listed
# the symbol under not_found in a clean answer. That is Yahoo's data in the log,
# which no line here may carry. What yfinance raises still reaches the log,
# through the tool's own line and, for the unexpected kind, with a traceback.
SILENT = ("yfinance",)

# Deprecation warnings raised in yfinance's code, kept off stderr. yfinance
# switches them on for itself at import ("default" for module ^yfinance),
# and since pandas 3.1.0 deprecated `inplace`, which yfinance uses in 29
# places (ranaroussi/yfinance#3009), that meant up to 14 three-line warnings
# per tool call, repeated on every call, about code nobody here can change.
# Matched by the module a warning is raised in, so a deprecation yfinance
# raises about this server's own use of it still shows. Installed after the
# import of yfinance, which ``cli`` brings in through ``server``, or that
# filter would stand in front of this one.
QUIET_WARNINGS = r"yfinance(\.|$)"


class _Handler(logging.StreamHandler):
    """The stderr handler, a class of its own so it is found again."""


class _ForeignLines(logging.Filter):
    """Reduces a line another library wrote to printable characters.

    Such a line may quote what a caller sent, the SDK's SSE transport names a
    rejected ``session_id`` from the query string say, and a line break in it
    would forge a second line. This package's lines and uvicorn's request log
    are shaped already and pass untouched. A traceback keeps its lines.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        if name in (PACKAGE, access.ACCESS_LOGGER) or name.startswith(f"{PACKAGE}."):
            return True
        record.msg = one_line(record.getMessage())
        record.args = ()
        return True


def configure(level: str) -> None:
    """Send this server's lines at ``level`` and above to stderr.

    The line is plain, or in colour when stderr is a terminal, see
    :mod:`.formats`.

    ``level`` applies to this package and to uvicorn's request log. The root
    logger stays at WARNING, so every other library says only what went
    wrong, and yfinance's deprecation warnings are dropped (QUIET_WARNINGS).
    A second call only changes the level. When the root logger already
    has handlers of someone else's, as under a test runner, they are kept and
    none is added, the way ``logging.basicConfig`` behaves.
    """
    root = logging.getLogger()
    ours = [h for h in root.handlers if isinstance(h, _Handler)]
    if not root.handlers:
        handler = _Handler(sys.stderr)
        handler.setFormatter(formats.for_stderr())
        root.addHandler(handler)
        ours = [handler]
    for handler in ours:
        handler.setLevel(level)
        if not any(isinstance(f, _ForeignLines) for f in handler.filters):
            handler.addFilter(_ForeignLines())
    root.setLevel(logging.WARNING)
    logging.getLogger(PACKAGE).setLevel(level)
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in SILENT:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    warnings.filterwarnings(
        "ignore", category=DeprecationWarning, module=QUIET_WARNINGS
    )
    access.configure(level)


@contextmanager
def untouched_root() -> Iterator[None]:
    """Undo whatever the block does to the root logger's handlers and level.

    The SDK's ``MCPServer`` constructor calls ``logging.basicConfig`` with a
    RichHandler of its own. On a root logger that has a handler already that
    does nothing, but a server built before :func:`configure` ran, or built by
    a program that logs nowhere, would get Rich's layout for every line after
    it, wrapped to a terminal width a container log does not have.
    """
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    try:
        yield
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
