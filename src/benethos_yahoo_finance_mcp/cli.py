"""The command line: parse it, say what is starting, hand over to a transport.

Run directly (``python -m benethos_yahoo_finance_mcp``) or via the installed
``benethos-yahoo-finance-mcp`` console script. The transport is selectable on
the command line (``--transport``): ``stdio`` (default, for Claude Desktop and
other local clients) or an HTTP transport (``streamable-http`` / ``sse``) for
running the server as a standalone, network-reachable service.

Logging always goes to stderr so that, under stdio, stdout stays reserved for
the JSON-RPC stream.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from . import __version__, cache, transport
from .logbook import lifecycle, output
from .server import build_server
from .settings import (
    CACHE_MAX_ENTRIES,
    DEFAULT_TTLS,
    LOG_LEVELS,
    TOKEN_VAR,
    TRANSPORTS,
    Settings,
    SettingsError,
    load_settings,
)

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the server entry point.

    Every default is ``None``, meaning "not given", so that
    :func:`~benethos_yahoo_finance_mcp.settings.load_settings` can fall back
    to the environment and then to the real default.
    """
    parser = argparse.ArgumentParser(
        prog="benethos-yahoo-finance-mcp",
        description="Yahoo Finance MCP server. Defaults to stdio. Pass "
        "--transport for an HTTP transport.",
    )
    # The same version the server reports in the MCP handshake, which is
    # otherwise only reachable by opening a session. Someone running this from
    # a container has no `pip show` to fall back on.
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print the version and exit.",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORTS,
        help="Transport to serve on (default: stdio, set via YF_MCP_TRANSPORT).",
    )
    parser.add_argument(
        "--host",
        help="Host to bind for HTTP transports (default: 127.0.0.1, set via "
        "YF_MCP_HOST). Use 0.0.0.0 to accept remote connections.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port for HTTP transports (default: 8000, set via YF_MCP_PORT).",
    )
    parser.add_argument(
        "--path",
        help="URL path to serve MCP on for HTTP transports (default: /mcp for "
        "streamable-http, /sse for sse, set via YF_MCP_PATH).",
    )
    parser.add_argument(
        "--allowed-hosts",
        metavar="HOST[,HOST...]",
        help="Comma-separated Host header allow-list for the DNS-rebinding "
        "guard on HTTP transports (e.g. benethos-yahoo-finance-mcp:8000). Set via "
        "YF_MCP_ALLOWED_HOSTS. A localhost bind keeps its protective default. "
        "An exposed bind (e.g. 0.0.0.0) with no list accepts any Host.",
    )
    parser.add_argument(
        "--allowed-origins",
        metavar="ORIGIN[,ORIGIN...]",
        help="Comma-separated Origin header allow-list for HTTP transports. "
        "Set via YF_MCP_ALLOWED_ORIGINS. Defaults to http(s) origins derived "
        "from --allowed-hosts.",
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVELS,
        help="Logging verbosity. Defaults to the YF_MCP_LOG_LEVEL env var, "
        "or INFO if unset.",
    )
    parser.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        help="Enable the persistent result cache (default: off, "
        "set via YF_MCP_CACHE). Use --cache to enable.",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory for the cache file (default: the OS user cache dir, "
        "set via YF_MCP_CACHE_DIR).",
    )
    parser.add_argument(
        "--cache-max-entries",
        type=int,
        metavar="N",
        help="Most entries the cache keeps, the oldest go first "
        f"(default: {CACHE_MAX_ENTRIES}, set via YF_MCP_CACHE_MAX_ENTRIES).",
    )
    parser.add_argument(
        "--cache-ttl",
        action="append",
        default=[],
        metavar="<NAME>=<SECONDS>",
        help="Override a tool's cache TTL, e.g. --cache-ttl quote=15. May be "
        "repeated. Valid names: " + ", ".join(DEFAULT_TTLS) + ".",
    )
    return parser


def parse_settings(argv: list[str] | None = None) -> Settings:
    """Parse the command line and resolve it against the environment.

    A value that cannot be used is a usage error, reported the way argparse
    reports its own, with exit status 2.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        settings = load_settings(vars(args))
    except SettingsError as exc:
        parser.error(str(exc))
    # Checked here rather than by argparse, because YF_MCP_PORT arrives from
    # the environment and argparse never sees it. Only an HTTP transport binds
    # the port, so stdio does not trip over a stray value.
    if settings.transport != "stdio" and not 1 <= settings.port <= 65535:
        parser.error(f"--port must be between 1 and 65535, got {settings.port}")
    # Starlette asserts on a route path without a leading slash, which ended
    # the server with an AssertionError after its start line.
    if settings.path is not None and not settings.path.startswith("/"):
        parser.error(f"--path must start with '/', got {settings.path!r}")
    return settings


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point: parse CLI args and run the MCP server."""
    settings = parse_settings(argv)

    # Before anything that might log, the server construction included.
    output.configure(settings.log_level)
    for variable, value in settings.ignored:
        lifecycle.setting_ignored(variable, value)

    cache.configure(settings)
    server = build_server()

    try:
        _serve(settings, server)
    except KeyboardInterrupt:
        # Ctrl+C. uvicorn shuts down cleanly first and then raises the signal
        # again, so that the process ends as interrupted. Uncaught, that
        # printed a traceback after "Finished server process", which read as
        # a crash. stdio stops the same way. 130 is 128 plus SIGINT.
        lifecycle.interrupted()
        raise SystemExit(130) from None


def _serve(settings: Settings, server: MCPServer) -> None:
    """Say what is starting and hand ``server`` to the chosen transport."""
    if settings.transport == "stdio":
        lifecycle.starting_stdio(__version__)
        if settings.bearer_token is not None:
            lifecycle.token_ignored_under_stdio(TOKEN_VAR)
        transport.run_stdio(server)
        return

    lifecycle.starting_http(
        __version__,
        settings.transport,
        settings.host,
        settings.port,
        settings.http_path,
    )
    if settings.bearer_token is None:
        lifecycle.port_unguarded(TOKEN_VAR, settings.host, settings.port)
    else:
        lifecycle.token_required()
    transport.run_http(server, settings)


if __name__ == "__main__":
    main()
