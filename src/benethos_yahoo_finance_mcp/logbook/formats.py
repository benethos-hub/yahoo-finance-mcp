"""How a line looks: plain for a file or a container log, in colour at a terminal.

Both name the source short: ``tools`` for this server's tool calls,
``server`` for the server itself, ``uvicorn`` for uvicorn's server log and
``http`` for its request log. uvicorn calls its server log ``uvicorn.error``,
after the web servers' error log, which holds everything a server says about
itself. Written out, a start read as a failure.

Both write the time the same way, as ISO 8601 to the millisecond with its
offset, since a log may be read far from where it was written and by a
parser: ``2026-09-30T13:19:02.840+02:00 INFO     tools: text``.

At a terminal a person reads the lines as they come. The time is dim, the
level in colour, the source in cyan and a request as method, path and
status in colour.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from http import HTTPStatus

from ._describe import PACKAGE

FORMAT = "%(asctime)s %(levelname)-8s %(source)s: %(message)s"

# ANSI colours, for a terminal only.
_RESET = "\033[0m"
_DIM = "\033[2m"
_SOURCE = "\033[36m"
_LEVEL_COLOURS = {
    logging.DEBUG: "\033[34m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
# As uvicorn colours a status: 2xx green, 3xx yellow, 4xx red, 5xx bold red.
_STATUS_COLOURS = {2: "\033[32m", 3: "\033[33m", 4: "\033[31m", 5: "\033[1;31m"}

# uvicorn's request line: client, method, path, HTTP version, status.
_ACCESS_ARGS = 5

# Wide enough for every short source of this server, ``uvicorn`` the longest.
SOURCE_WIDTH = 8


def timestamp(record: logging.LogRecord) -> str:
    """``2026-09-30T13:19:02.840+02:00``, in this machine's time zone."""
    moment = datetime.fromtimestamp(record.created).astimezone()
    return moment.isoformat(timespec="milliseconds")


class Plain(logging.Formatter):
    """The line for a file or a container log, see the module docstring."""

    def __init__(self) -> None:
        super().__init__(FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        record.source = short_source(record.name)
        return super().format(record)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return timestamp(record)


class Console(logging.Formatter):
    """The line for a person at a terminal, see the module docstring."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return timestamp(record)

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        head = (
            f"{_DIM}{self.formatTime(record)}{_RESET} "
            f"{colour}{record.levelname:<8}{_RESET} "
            f"{_SOURCE}{short_source(record.name):<{SOURCE_WIDTH}}{_RESET} "
        )
        text = _request(record) or record.getMessage()
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        if record.stack_info:
            text += "\n" + self.formatStack(record.stack_info)
        return head + text


def short_source(name: str) -> str:
    """``tools`` for this server's ``<package>.tools``, ``server`` for the
    package itself, ``http`` for the request log, ``uvicorn`` for the server
    log. Any other logger keeps its name."""
    if name == PACKAGE:
        return "server"
    if name == "uvicorn.access":
        return "http"
    if name.startswith("uvicorn"):
        return "uvicorn"
    return name.removeprefix(f"{PACKAGE}.")


def _request(record: logging.LogRecord) -> str | None:
    """``POST /mcp 401 Unauthorized 10.0.0.7:5555`` for a request line."""
    if record.name != "uvicorn.access" or not isinstance(record.args, tuple):
        return None
    if len(record.args) != _ACCESS_ARGS:
        return None
    client, method, path, _, status = record.args
    if not isinstance(status, int):
        return None
    try:
        phrase = f" {HTTPStatus(status).phrase}"
    except ValueError:
        phrase = ""
    colour = _STATUS_COLOURS.get(status // 100, "")
    return f"{method} {path} {colour}{status}{phrase}{_RESET} {_DIM}{client}{_RESET}"


def colours_wanted() -> bool:
    """Colours on a terminal, unless ``NO_COLOR`` is set (no-color.org)."""
    return sys.stderr.isatty() and "NO_COLOR" not in os.environ


def for_stderr() -> logging.Formatter:
    """The formatter for the stderr handler, chosen by where stderr goes."""
    return Console() if colours_wanted() else Plain()
