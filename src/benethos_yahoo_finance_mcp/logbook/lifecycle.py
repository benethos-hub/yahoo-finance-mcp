"""Starting up: what is being served, how the port is guarded, what was ignored."""

from __future__ import annotations

import logging

from ._describe import PACKAGE

_log = logging.getLogger(PACKAGE)


def setting_ignored(variable: str, value: str) -> None:
    """An environment value that could not be used and was replaced by its default.

    The value is quoted: these are transports, ports, levels and TTLs, and the
    token is never among them, since any value is a valid token.
    """
    _log.warning("Ignoring invalid %s: %r", variable, value)


def starting_stdio() -> None:
    _log.info("Starting Yahoo Finance MCP server (stdio)")


def token_ignored_under_stdio(variable: str) -> None:
    _log.warning(
        "%s is set, but stdio has no port for anyone to reach. The client owns "
        "this process, so the token is ignored.",
        variable,
    )


def starting_http(transport: str, host: str, port: int, path: str) -> None:
    _log.info(
        "Starting Yahoo Finance MCP server (%s) on http://%s:%s%s",
        transport,
        host,
        port,
        path,
    )


def port_unguarded(variable: str, host: str, port: int) -> None:
    _log.warning(
        "No %s set: anything that can reach %s:%s can call every tool. That is "
        "fine for a loopback bind on your own machine and is not fine anywhere "
        "else.",
        variable,
        host,
        port,
    )


def token_required() -> None:
    _log.info("Bearer token required: requests without it get HTTP 401.")
