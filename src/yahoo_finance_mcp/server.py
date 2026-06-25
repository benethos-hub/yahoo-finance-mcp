"""MCP server entry point exposing Yahoo Finance tools.

Run directly (``python -m yahoo_finance_mcp``) or via the installed
``yahoo-finance-mcp`` console script. The transport is selectable on the
command line (``--transport``): ``stdio`` (default, for Claude Desktop and
other local clients) or an HTTP transport (``streamable-http`` / ``sse``) for
running the server as a standalone, network-reachable service.

Logging always goes to stderr so that, under stdio, stdout stays reserved for
the JSON-RPC stream.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from . import cache, client

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_TRANSPORTS = ["stdio", "streamable-http", "sse"]


def _default_log_level() -> str:
    """Default log level from the YF_MCP_LOG_LEVEL env var, falling back to INFO."""
    level = os.environ.get("YF_MCP_LOG_LEVEL", "INFO").upper()
    return level if level in _LOG_LEVELS else "INFO"


def _default_transport() -> str:
    """Default transport from the YF_MCP_TRANSPORT env var, falling back to stdio."""
    transport = os.environ.get("YF_MCP_TRANSPORT", "stdio").strip().lower()
    return transport if transport in _TRANSPORTS else "stdio"


def _default_port() -> int:
    """Default port from the YF_MCP_PORT env var, falling back to 8000."""
    try:
        return int(os.environ.get("YF_MCP_PORT", "8000"))
    except ValueError:
        return 8000


# Log to stderr only: stdout carries the MCP JSON-RPC protocol.
logging.basicConfig(
    level=_default_log_level(),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("yahoo_finance_mcp")

mcp = FastMCP("yahoo-finance")


@mcp.tool()
def search(
    query: Annotated[
        str, Field(description="Company name, ticker symbol, or ISIN to look up.")
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of matches to return.", ge=1, le=25),
    ] = 8,
) -> list[dict[str, Any]]:
    """Search Yahoo Finance by company name, ticker symbol, or ISIN.

    Use this first to resolve a name or ISIN into a Yahoo ``symbol`` that the
    other tools accept. Returns up to ``limit`` matches (1-25), each with its
    symbol, name, exchange, and instrument type.
    """
    return client.search(query, limit=limit)


Symbol = Annotated[
    str,
    Field(
        description=(
            "A native Yahoo Finance ticker symbol, e.g. 'AAPL', 'MSFT', "
            "'SAP.DE', or 'BMW.DE'. This is NOT an ISIN, a WKN, or a company "
            "name, and must NOT be built by appending an exchange suffix to an "
            "ISIN (e.g. 'US0378331005.DE' is invalid). If you only have a name "
            "or ISIN, call the 'search' tool first and pass the 'symbol' value "
            "it returns."
        )
    ),
]


@mcp.tool()
def get_quote(symbol: Symbol) -> dict[str, Any]:
    """Get the current price and key intraday figures for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name. Do not build a symbol by appending an
    exchange suffix to an ISIN. If you only have a name or ISIN, call the
    ``search`` tool first and use the ``symbol`` it returns.
    """
    return client.get_quote(symbol)


@mcp.tool()
def get_history(
    symbol: Symbol,
    period: Annotated[
        str,
        Field(
            description="Look-back window. One of: 1d, 5d, 1mo, 3mo, 6mo, 1y, "
            "2y, 5y, 10y, ytd, max. Ignored when 'start' is given."
        ),
    ] = "1mo",
    interval: Annotated[
        str,
        Field(
            description="Bar size. One of: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, "
            "1d, 5d, 1wk, 1mo, 3mo. Intraday intervals only cover recent dates."
        ),
    ] = "1d",
    start: Annotated[
        str | None,
        Field(description="Start date 'YYYY-MM-DD'. Overrides 'period' when set."),
    ] = None,
    end: Annotated[
        str | None,
        Field(description="End date 'YYYY-MM-DD'. Used only together with 'start'."),
    ] = None,
) -> dict[str, Any]:
    """Get historical OHLCV (open/high/low/close/volume) data for a symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    ``period`` accepts Yahoo values such as ``1d``, ``5d``, ``1mo``, ``6mo``,
    ``1y``, ``5y``, ``max``. ``interval`` accepts e.g. ``1m``, ``5m``, ``1h``,
    ``1d``, ``1wk``, ``1mo``. Provide ``start`` (and optional ``end``) as
    ``YYYY-MM-DD`` to query an explicit date range instead of ``period``.
    Results are capped at the most recent 250 rows.
    """
    return client.get_history(
        symbol, period=period, interval=interval, start=start, end=end
    )


@mcp.tool()
def get_company_info(symbol: Symbol) -> dict[str, Any]:
    """Get a company profile and key statistics for a Yahoo symbol.

    Returns name, sector/industry, location, employee count, and valuation
    metrics (market cap, P/E, beta, 52-week range, dividend yield) plus a
    business summary. ``symbol`` must be a native Yahoo Finance ticker (e.g.
    ``AAPL``, ``SAP.DE``), never an ISIN, WKN, or company name; resolve those
    via ``search`` first.
    """
    return client.get_company_info(symbol)


@mcp.tool()
def get_financials(
    symbol: Symbol,
    statement: Annotated[
        str,
        Field(
            description="Which statement: 'income' (income statement), "
            "'balance' (balance sheet), or 'cashflow' (cash flow)."
        ),
    ] = "income",
    freq: Annotated[
        str,
        Field(description="Reporting frequency: 'annual' or 'quarterly'."),
    ] = "annual",
) -> dict[str, Any]:
    """Get a financial statement for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    ``statement`` is one of ``income`` (income statement), ``balance`` (balance
    sheet), or ``cashflow`` (cash flow statement). ``freq`` is ``annual`` or
    ``quarterly``. Each row is a line item; columns are reporting periods.
    """
    return client.get_financials(symbol, statement=statement, freq=freq)


@mcp.tool()
def get_dividends(symbol: Symbol) -> dict[str, Any]:
    """Get the dividend and stock-split history for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    """
    return client.get_dividends(symbol)


@mcp.tool()
def get_news(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of headlines to return.", ge=1, le=30),
    ] = 10,
) -> dict[str, Any]:
    """Get recent news headlines for a Yahoo symbol (up to ``limit``, 1-30).

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Each article includes title, summary, publisher, publish time, and URL.
    """
    return client.get_news(symbol, limit=limit)


@mcp.tool()
def get_recommendations(symbol: Symbol) -> dict[str, Any]:
    """Get analyst recommendation trends and price targets for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Returns the buy/hold/sell trend over recent months plus current/high/low/
    mean/median analyst price targets when available.
    """
    return client.get_recommendations(symbol)


@mcp.tool()
def get_options(
    symbol: Symbol,
    expiration: Annotated[
        str | None,
        Field(
            description="Expiration date 'YYYY-MM-DD' from the list returned when "
            "called without it. Omit to list available expiration dates."
        ),
    ] = None,
) -> dict[str, Any]:
    """Get the option chain for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Call without ``expiration`` to list available expiration dates. Call with
    an ``expiration`` (``YYYY-MM-DD`` from that list) to get the calls and puts
    for that date.
    """
    return client.get_options(symbol, expiration=expiration)


@mcp.tool()
def get_earnings(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of earnings rows to return.", ge=1, le=50),
    ] = 12,
) -> dict[str, Any]:
    """Get upcoming and historical earnings for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Returns the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) plus the recent earnings history. Equity-only;
    empty for ETFs, funds, and crypto.
    """
    return client.get_earnings(symbol, limit=limit)


@mcp.tool()
def get_estimates(symbol: Symbol) -> dict[str, Any]:
    """Get forward analyst estimates for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Returns earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (small tables keyed by period). Equity-only; empty for ETFs,
    funds, and crypto.
    """
    return client.get_estimates(symbol)


@mcp.tool()
def get_upgrades_downgrades(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of rating changes to return.", ge=1, le=100),
    ] = 50,
) -> dict[str, Any]:
    """Get recent analyst rating changes (upgrades/downgrades) for a Yahoo symbol.

    ``symbol`` must be a native Yahoo Finance ticker (e.g. ``AAPL``, ``SAP.DE``),
    never an ISIN, WKN, or company name; resolve those via ``search`` first.
    Each entry is a firm's rating change with the from/to grade and action, most
    recent first. Equity-only; empty for ETFs, funds, and crypto.
    """
    return client.get_upgrades_downgrades(symbol, max_rows=limit)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the server entry point."""
    parser = argparse.ArgumentParser(
        prog="yahoo-finance-mcp",
        description="Yahoo Finance MCP server. Defaults to stdio; pass "
        "--transport for an HTTP transport.",
    )
    parser.add_argument(
        "--transport",
        choices=_TRANSPORTS,
        default=_default_transport(),
        help="Transport to serve on (default: stdio; set via YF_MCP_TRANSPORT).",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("YF_MCP_HOST", "127.0.0.1"),
        help="Host to bind for HTTP transports (default: 127.0.0.1; set via "
        "YF_MCP_HOST). Use 0.0.0.0 to accept remote connections.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port(),
        help="Port for HTTP transports (default: 8000; set via YF_MCP_PORT).",
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("YF_MCP_PATH"),
        help="URL path to serve MCP on for HTTP transports (default: /mcp for "
        "streamable-http, /sse for sse; set via YF_MCP_PATH).",
    )
    parser.add_argument(
        "--log-level",
        choices=_LOG_LEVELS,
        default=_default_log_level(),
        help="Logging verbosity. Defaults to the YF_MCP_LOG_LEVEL env var, "
        "or INFO if unset.",
    )
    parser.add_argument(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=cache.env_enabled(),
        help="Enable the persistent result cache (default: off; "
        "set via YF_MCP_CACHE). Use --cache to enable.",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("YF_MCP_CACHE_DIR"),
        help="Directory for the cache file (default: the OS user cache dir; "
        "set via YF_MCP_CACHE_DIR).",
    )
    parser.add_argument(
        "--cache-ttl",
        action="append",
        default=[],
        metavar="<NAME>=<SECONDS>",
        help="Override a tool's cache TTL, e.g. --cache-ttl quote=15. May be "
        "repeated. Valid names: " + ", ".join(cache.DEFAULT_TTLS) + ".",
    )
    return parser


def _parse_ttl_overrides(
    parser: argparse.ArgumentParser, items: list[str]
) -> dict[str, float]:
    """Parse ``<NAME>=<SECONDS>`` ``--cache-ttl`` items into a mapping."""
    overrides: dict[str, float] = {}
    for item in items:
        name, sep, raw = item.partition("=")
        name = name.strip().lower()
        if not sep or name not in cache.DEFAULT_TTLS:
            parser.error(
                f"invalid --cache-ttl {item!r}; expected <NAME>=<SECONDS> with <NAME> "
                f"one of {', '.join(cache.DEFAULT_TTLS)}"
            )
        try:
            overrides[name] = float(raw)
        except ValueError:
            parser.error(f"invalid --cache-ttl seconds in {item!r}")
    return overrides


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point: parse CLI args and run the MCP server."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.getLogger().setLevel(args.log_level)

    # Result cache: CLI overrides win over env vars, which win over defaults.
    ttl_overrides = {
        **cache.ttls_from_env(),
        **_parse_ttl_overrides(parser, args.cache_ttl),
    }
    cache.configure(
        enabled=args.cache, cache_dir=args.cache_dir, ttl_overrides=ttl_overrides
    )

    # Host/port/path only matter for the HTTP transports; setting them for
    # stdio is harmless.
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    if args.path:
        if args.transport == "sse":
            mcp.settings.sse_path = args.path
        else:
            mcp.settings.streamable_http_path = args.path

    if args.transport == "stdio":
        logger.info("Starting Yahoo Finance MCP server (stdio)")
    else:
        logger.info(
            "Starting Yahoo Finance MCP server (%s) on http://%s:%s",
            args.transport,
            args.host,
            args.port,
        )

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
