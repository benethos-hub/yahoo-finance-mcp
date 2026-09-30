"""Where the log goes: one handler, on stderr, installed by the command line.

stdout carries the MCP JSON-RPC stream under stdio, so nothing here ever
writes to it. Nothing is installed at import either. :func:`configure` is
called once from ``cli.main``, and a program that imports the package and
builds a server itself keeps whatever logging it set up.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from . import access, formats
from ._describe import PACKAGE

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
    "yfinance",
    "curl_cffi",
    "urllib3",
    "peewee",
    "httpx",
    "httpcore",
)


class _Handler(logging.StreamHandler):
    """The stderr handler, a class of its own so it is found again."""


def configure(level: str) -> None:
    """Send this server's lines at ``level`` and above to stderr.

    The line is plain, or in colour when stderr is a terminal, see
    :mod:`.formats`.

    ``level`` applies to this package and to uvicorn's request log. The root
    logger stays at WARNING, so every other library says only what went
    wrong. A second call only changes the level. When the root logger already
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
    root.setLevel(logging.WARNING)
    logging.getLogger(PACKAGE).setLevel(level)
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
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
