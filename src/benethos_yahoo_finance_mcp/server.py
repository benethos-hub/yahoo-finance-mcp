"""MCP server entry point exposing Yahoo Finance tools.

Run directly (``python -m benethos_yahoo_finance_mcp``) or via the installed
``benethos-yahoo-finance-mcp`` console script. The transport is selectable on the
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

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from . import __version__, cache, client, transport

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_TRANSPORTS = ["stdio", "streamable-http", "sse"]


def _default_log_level() -> str:
    """Default log level from the YF_MCP_LOG_LEVEL env var, falling back to INFO."""
    level = os.environ.get("YF_MCP_LOG_LEVEL", "INFO").upper()
    return level if level in _LOG_LEVELS else "INFO"


def _default_transport() -> str:
    """Default transport from the YF_MCP_TRANSPORT env var, falling back to stdio."""
    name = os.environ.get("YF_MCP_TRANSPORT", "stdio").strip().lower()
    return name if name in _TRANSPORTS else "stdio"


def _default_port() -> int:
    """Default port from the YF_MCP_PORT env var, falling back to 8000."""
    try:
        return int(os.environ.get("YF_MCP_PORT", "8000"))
    except ValueError:
        return 8000


# Host values for which we keep DNS-rebinding protection on by default.
_LOCALHOST_BINDS = frozenset({"127.0.0.1", "localhost", "::1", ""})


def _split_csv(value: str | None) -> list[str]:
    """Split a comma-separated option value into a clean list of items."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _transport_security_for(
    host: str, allowed_hosts: list[str], allowed_origins: list[str]
) -> TransportSecuritySettings:
    """Compute the transport security policy for the host the server binds.

    The SDK defaults this to a localhost-only allow-list. Left alone, an HTTP
    transport bound to a non-localhost host would reject every remote client
    with HTTP 421 ("Invalid Host header"), which is exactly what containers and
    gateways run into. Derive it from the host actually being bound:

    - An explicit allow-list always wins: enable protection with those values.
    - A localhost bind keeps the protective localhost defaults.
    - A deliberately exposed bind (e.g. 0.0.0.0) with no allow-list turns
      DNS-rebinding protection off, mirroring the SDK's own default for a
      non-localhost bind.
    """
    if allowed_hosts or allowed_origins:
        origins = allowed_origins or [
            f"{scheme}://{h}" for h in allowed_hosts for scheme in ("http", "https")
        ]
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=origins,
        )
    if host in _LOCALHOST_BINDS:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


# Log to stderr only: stdout carries the MCP JSON-RPC protocol.
logging.basicConfig(
    level=_default_log_level(),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("benethos_yahoo_finance_mcp")

# Sent once during the initialize handshake, not per tool, so this is the
# natural place for rules that hold across the whole server.
#
# Do not rely on it. Verified against Claude Desktop 2026-08-16: the shortened
# tool descriptions arrive, these instructions do not. Whether a client surfaces
# them is entirely its own decision, and at least one major client does not.
# Anything that must reach the model therefore also has to be stated at the tool
# or parameter itself, however briefly. This block is kept because it costs
# nothing per request and other clients may well use it.
_INSTRUCTIONS = """\
Read-only access to Yahoo Finance market data. Three things decide whether a \
call succeeds, and two more decide whether its answer is read correctly.

Symbols. Every tool taking a `symbol` accepts a Yahoo ticker such as `AAPL`, \
`SAP.DE` or `BTC-USD`, or a plain ISIN such as `US0378331005`, which Yahoo \
resolves server-side. Pass either through unchanged — a symbol should never be \
assembled or transformed. A company name is not a symbol: resolve it with \
`search` and pass back what that returns. German WKNs resolve nowhere, not even \
through `search`, so ask for a ticker, an ISIN or the company name instead. \
`get_sector`, `get_industry` and `get_market` are the exceptions: they take a \
key, not a ticker.

Empty results are normal. Analyst, holder, earnings, insider, filing and \
calendar data exist for equities only and come back empty for ETFs, funds and \
crypto. `get_fund_data` is the reverse and fails for anything that is not a \
fund. An empty field usually means the instrument has no such data, not that \
the call went wrong.

Rate limits. Yahoo throttles aggressively and unpredictably. A rate-limit error \
is temporary and says nothing about the arguments — wait and retry rather than \
changing the call.

Currencies are never converted. Every price, market cap and statement figure is \
in the instrument's own currency, reported as `currency` where the tool has it. \
Comparing `AAPL` with `SAP.DE`, or summing them, means mixing USD and EUR, and \
nothing in the data will flag that.

Results are capped, mostly in silence. Only `get_history` and `get_quotes` \
report a `truncated` flag. Every other tool quietly returns at most its top or \
most recent rows, so a short list is not evidence that the list is short. Where \
a tool takes a `limit`, raise it rather than concluding there is no more.

Data is delayed and may be incomplete. This is not investment advice.
"""

# Identity reported to clients during the MCP initialize handshake. ``name`` is
# the programmatic identifier and is kept identical to the PyPI distribution
# name, so the server a client lists is traceable to the package it came from.
# ``title`` is what a client shows to a person.
mcp = MCPServer(
    name="benethos-yahoo-finance-mcp",
    title="Unofficial Yahoo Finance MCP Server",
    version=__version__,
    instructions=_INSTRUCTIONS,
)


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


# Repeated once per symbol-taking tool, so every character here is paid 17 times
# in the client's context.
#
# This used to carry a long warning that an ISIN is not a symbol. Yahoo now
# resolves plain ISINs server-side — measured 2026-08-16, all 18 symbol-taking
# tools return correct data for one — so the warning guarded against a failure
# mode that no longer exists. Only the company-name case still needs `search`.
Symbol = Annotated[
    str,
    Field(
        description=(
            "A Yahoo ticker or an ISIN, e.g. 'AAPL', 'SAP.DE' or "
            "'US0378331005'. For a company name, use 'search' first."
        )
    ),
]


@mcp.tool()
def get_quote(symbol: Symbol) -> dict[str, Any]:
    """Get the current price and key intraday figures for a Yahoo symbol."""
    return client.get_quote(symbol)


@mcp.tool()
def get_quotes(
    symbols: Annotated[
        list[str],
        Field(
            description="Yahoo tickers or ISINs, e.g. ['AAPL', 'MSFT', "
            "'SAP.DE']. Not company names. Up to 50, extras are dropped."
        ),
    ],
) -> dict[str, Any]:
    """Get compact current quotes for several Yahoo symbols in one call.

    Use this to compare or fetch prices for multiple tickers at once. Each symbol
    is looked up individually and returns currency, last price, previous close,
    open, day high/low, and market cap. Symbols that return no data are listed
    under ``not_found`` rather than failing the whole call.
    """
    return client.get_quotes(symbols)


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
    business summary.
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
        Field(
            description="Reporting frequency: 'annual', 'quarterly', or 'ttm' "
            "(trailing twelve months, income and cashflow only)."
        ),
    ] = "annual",
) -> dict[str, Any]:
    """Get a financial statement for a Yahoo symbol.

    ``statement`` is one of ``income`` (income statement), ``balance`` (balance
    sheet), or ``cashflow`` (cash flow statement). ``freq`` is ``annual``,
    ``quarterly``, or ``ttm`` (trailing twelve months, available for the income
    and cash-flow statements only). Each row is a line item and each column a
    reporting periods.
    """
    return client.get_financials(symbol, statement=statement, freq=freq)


@mcp.tool()
def get_dividends(symbol: Symbol) -> dict[str, Any]:
    """Get the dividend and stock-split history for a Yahoo symbol."""
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

    Each article includes title, summary, publisher, publish time, and URL.
    """
    return client.get_news(symbol, limit=limit)


@mcp.tool()
def get_recommendations(symbol: Symbol) -> dict[str, Any]:
    """Get analyst recommendation trends and price targets for a Yahoo symbol.

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

    Call without ``expiration`` to list available expiration dates. Call with
    an ``expiration`` (``YYYY-MM-DD`` from that list) to get the calls and puts
    for that date. Yahoo carries chains for US-listed instruments only, so a
    non-US symbol has none and that says nothing about the symbol.
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

    Returns the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) plus the recent earnings history. Equity-only,
    empty for ETFs, funds, and crypto.
    """
    return client.get_earnings(symbol, limit=limit)


@mcp.tool()
def get_estimates(symbol: Symbol) -> dict[str, Any]:
    """Get forward analyst estimates for a Yahoo symbol.

    Returns earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (small tables keyed by period). Equity-only, empty for ETFs,
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

    Each entry is a firm's rating change with the from/to grade and action, most
    recent first. Equity-only, empty for ETFs, funds, and crypto.
    """
    return client.get_upgrades_downgrades(symbol, max_rows=limit)


@mcp.tool()
def get_holders(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of institutional/mutual-fund holders to "
            "return per list.",
            ge=1,
            le=100,
        ),
    ] = 25,
) -> dict[str, Any]:
    """Get the ownership breakdown for a Yahoo symbol.

    Returns the high-level holder summary (insider/institutional percentages)
    plus the top institutional and mutual-fund holders. Equity-only, empty for
    ETFs, funds, and crypto.
    """
    return client.get_holders(symbol, max_rows=limit)


@mcp.tool()
def get_insider_activity(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of insider transactions/roster rows to return.",
            ge=1,
            le=100,
        ),
    ] = 50,
) -> dict[str, Any]:
    """Get insider trading activity for a Yahoo symbol.

    Returns individual insider transactions, a 6-month purchases/sales summary,
    and the current insider roster. Equity-only, empty for ETFs, funds, and
    crypto.
    """
    return client.get_insider_activity(symbol, max_rows=limit)


@mcp.tool()
def get_sec_filings(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of filings to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Get recent SEC filings for a Yahoo symbol.

    Each entry has the filing date, type (e.g. ``10-K``, ``10-Q``, ``8-K``),
    title, the Yahoo EDGAR URL, and exhibit links. Only issuers registered with
    the U.S. SEC file there, so a non-US symbol has none, and neither do ETFs,
    funds or crypto. An empty result says nothing about the symbol.
    """
    return client.get_sec_filings(symbol, limit=limit)


@mcp.tool()
def get_calendar(symbol: Symbol) -> dict[str, Any]:
    """Get upcoming corporate-calendar events for a Yahoo symbol.

    Returns the next earnings date(s) with analyst estimate ranges and the next
    dividend / ex-dividend dates. Equity-only, empty for ETFs, funds, and crypto.
    """
    return client.get_calendar(symbol)


@mcp.tool()
def get_shares(
    symbol: Symbol,
    start: Annotated[
        str | None,
        Field(description="Start date 'YYYY-MM-DD' to bound the series (optional)."),
    ] = None,
    end: Annotated[
        str | None,
        Field(description="End date 'YYYY-MM-DD' to bound the series (optional)."),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of (most recent) data points to return.",
            ge=1,
            le=250,
        ),
    ] = 50,
) -> dict[str, Any]:
    """Get the shares-outstanding history for a Yahoo symbol.

    Each point is a date and the reported shares outstanding. Only the most
    recent ``limit`` points are returned. Optionally bound the range with
    ``start`` / ``end`` (``YYYY-MM-DD``).
    """
    return client.get_shares(symbol, start=start, end=end, max_rows=limit)


@mcp.tool()
def get_fund_data(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of top holdings to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Get fund/ETF profile data for a Yahoo symbol.

    Returns the fund overview, asset-class and sector weightings, and the top
    holdings. Fund/ETF-only, raises for stocks and crypto, which have no fund
    data.
    """
    return client.get_fund_data(symbol, max_rows=limit)


# Built from yfinance's own constant (via client) so the tool description the
# LLM sees stays in sync with upstream's sector keys.
_SECTOR_KEYS_DESC = (
    "A Yahoo sector key (lowercase, hyphenated). One of: "
    + ", ".join(client.SECTOR_KEYS)
    + "."
)


@mcp.tool()
def get_sector(
    key: Annotated[
        str,
        Field(description=_SECTOR_KEYS_DESC),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of top companies to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Browse a market sector by its Yahoo key (not a ticker symbol).

    Returns the sector overview (company count, market cap/weight, description),
    its top companies, ETFs, and mutual funds, and the constituent industries.
    Each industry's ``key`` can be passed to ``get_industry`` to drill down.
    This takes a sector key like ``technology`` or ``healthcare`` — not a ticker.
    """
    return client.get_sector(key, max_rows=limit)


@mcp.tool()
def get_industry(
    key: Annotated[
        str,
        Field(
            description="A Yahoo industry key (lowercase, hyphenated), e.g. "
            "'semiconductors' or 'software-infrastructure'. Discover valid keys "
            "from the 'industries' list returned by get_sector."
        ),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of top companies to return.", ge=1, le=100),
    ] = 25,
) -> dict[str, Any]:
    """Browse an industry by its Yahoo key (not a ticker symbol).

    Returns the industry overview, its parent sector, top companies, and the
    top-performing and top-growth companies. Discover valid industry keys from
    the ``industries`` list returned by ``get_sector``. This takes an industry
    key like ``semiconductors`` — not a ticker symbol.
    """
    return client.get_industry(key, max_rows=limit)


@mcp.tool()
def get_market(
    key: Annotated[
        str,
        Field(
            description="A Yahoo market key (uppercase). One of: "
            + ", ".join(client.MARKET_KEYS)
            + ". Only 'US' reports a trading status, the others return the index "
            "summary with 'status' set to null."
        ),
    ] = "US",
) -> dict[str, Any]:
    """Get the trading status and headline index summary for a market.

    Answers questions like whether the market is open, when it opens or closes
    next, and how the major indices are doing. Takes a market key such as
    ``US`` or ``EUROPE`` — not a ticker symbol. ``status`` (open/closed plus the
    next open and close times) is only available for ``US`` and is ``null`` for
    every other key, which is an upstream limitation rather than an error. The
    index summary, with price, previous close and change, works for all keys.
    """
    return client.get_market(key)


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the server entry point."""
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
        choices=_TRANSPORTS,
        default=_default_transport(),
        help="Transport to serve on (default: stdio, set via YF_MCP_TRANSPORT).",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("YF_MCP_HOST", "127.0.0.1"),
        help="Host to bind for HTTP transports (default: 127.0.0.1, set via "
        "YF_MCP_HOST). Use 0.0.0.0 to accept remote connections.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_default_port(),
        help="Port for HTTP transports (default: 8000, set via YF_MCP_PORT).",
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("YF_MCP_PATH"),
        help="URL path to serve MCP on for HTTP transports (default: /mcp for "
        "streamable-http, /sse for sse, set via YF_MCP_PATH).",
    )
    parser.add_argument(
        "--allowed-hosts",
        default=os.environ.get("YF_MCP_ALLOWED_HOSTS"),
        metavar="HOST[,HOST...]",
        help="Comma-separated Host header allow-list for the DNS-rebinding "
        "guard on HTTP transports (e.g. benethos-yahoo-finance-mcp:8000). Set via "
        "YF_MCP_ALLOWED_HOSTS. A localhost bind keeps its protective default. "
        "An exposed bind (e.g. 0.0.0.0) with no list accepts any Host.",
    )
    parser.add_argument(
        "--allowed-origins",
        default=os.environ.get("YF_MCP_ALLOWED_ORIGINS"),
        metavar="ORIGIN[,ORIGIN...]",
        help="Comma-separated Origin header allow-list for HTTP transports. "
        "Set via YF_MCP_ALLOWED_ORIGINS. Defaults to http(s) origins derived "
        "from --allowed-hosts.",
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
        help="Enable the persistent result cache (default: off, "
        "set via YF_MCP_CACHE). Use --cache to enable.",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("YF_MCP_CACHE_DIR"),
        help="Directory for the cache file (default: the OS user cache dir, "
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
                f"invalid --cache-ttl {item!r}, expected <NAME>=<SECONDS> with <NAME> "
                f"one of {', '.join(cache.DEFAULT_TTLS)}"
            )
        try:
            overrides[name] = float(raw)
        except ValueError:
            parser.error(f"invalid --cache-ttl seconds in {item!r}")
    return overrides


def _http_path(args: argparse.Namespace) -> str:
    """The URL path an HTTP transport serves on, defaulted per transport."""
    if args.path:
        return args.path
    return "/sse" if args.transport == "sse" else "/mcp"


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

    token = transport.token_from_env()

    if args.transport == "stdio":
        logger.info("Starting Yahoo Finance MCP server (stdio)")
        if token is not None:
            logger.warning(
                "%s is set, but stdio has no port for anyone to reach. The "
                "client owns this process, so the token is ignored.",
                transport.ENV_VAR,
            )
        mcp.run(transport="stdio")
        return

    path = _http_path(args)
    logger.info(
        "Starting Yahoo Finance MCP server (%s) on http://%s:%s%s",
        args.transport,
        args.host,
        args.port,
        path,
    )
    if token is None:
        logger.warning(
            "No %s set: anything that can reach %s:%s can call every tool. "
            "That is fine for a loopback bind on your own machine and is not "
            "fine anywhere else.",
            transport.ENV_VAR,
            args.host,
            args.port,
        )
    else:
        logger.info("Bearer token required: requests without it get HTTP 401.")

    app = transport.http_app(
        mcp,
        transport=args.transport,
        path=path,
        host=args.host,
        transport_security=_transport_security_for(
            args.host,
            _split_csv(args.allowed_hosts),
            _split_csv(args.allowed_origins),
        ),
        token=token,
    )
    transport.run_http(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
