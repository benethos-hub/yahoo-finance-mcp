"""uvicorn's request log, held to the same rules as every other line.

uvicorn writes one line per answered request to ``uvicorn.access``, by default
to stdout and with the full URL. Here it goes to the same stderr handler as
everything else, without the query string, and at INFO only for a request that
was refused: status 400 and above, 401 from the bearer guard and 421 from the
Host check included. Those carry the address that tried, which is what an
operator looks for. Every answered request is a DEBUG line.
"""

from __future__ import annotations

import logging
from typing import Any

from . import _describe

ACCESS_LOGGER = "uvicorn.access"
SERVER_LOGGER = "uvicorn.error"


class AccessFilter(logging.Filter):
    """Drops the query string and demotes a served request to DEBUG.

    uvicorn logs ``'%s - "%s %s HTTP/%s" %d'`` with the client address, method,
    path with query, HTTP version and status as arguments. A record in any
    other shape passes untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) != 5:
            return True
        client, method, path, version, status = args
        record.args = (client, method, _describe.path_only(str(path)), version, status)
        if isinstance(status, int) and status < 400:
            record.levelno = logging.DEBUG
            record.levelname = logging.getLevelName(logging.DEBUG)
        return True


def configure() -> None:
    """Route uvicorn's loggers through the root handler, shaped as above.

    Their levels are left to the root logger, except that uvicorn's own server
    log stops at INFO: its DEBUG lines are about connections, not about this
    server.
    """
    access = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(f, AccessFilter) for f in access.filters):
        access.addFilter(AccessFilter())
    logging.getLogger(SERVER_LOGGER).setLevel(logging.INFO)


def uvicorn_options() -> dict[str, Any]:
    """The logging part of uvicorn's ``Config``.

    No ``log_config``, so uvicorn installs no handlers of its own and its
    records reach the root handler. No ``log_level``, so it does not override
    the levels set here.
    """
    return {"log_config": None, "log_level": None, "access_log": True}
