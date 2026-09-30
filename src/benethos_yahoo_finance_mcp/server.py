"""The MCP server: its identity, its instructions and the tools it offers.

:func:`build_server` makes a server with every tool registered. Nothing runs at
import beyond definitions, the command line in :mod:`.cli` decides when a server
is built and which transport it is handed to.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, client

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

Results are capped, mostly in silence. Only `get_history`, `get_quotes` and \
`get_options` report a `truncated` flag. Every other tool quietly returns at \
most its top or most recent rows, so a short list is not evidence that the list \
is short. Where a tool takes a `limit`, raise it rather than concluding there is \
no more.

Data is delayed and may be incomplete. This is not investment advice.
"""

# Every tool here only reads, and every one of them asks Yahoo, so they all
# carry the same two hints. A client may use them to call a read-only tool
# without asking the user first. destructiveHint and idempotentHint are left
# out on purpose: the spec defines them only for tools that are not read-only,
# and this server has none, so they would be bytes in every tool listing that
# no client is meant to read.
_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


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


def get_quote(symbol: Symbol) -> dict[str, Any]:
    """Get the current price and key intraday figures for a Yahoo symbol."""
    return client.get_quote(symbol)


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

    Query a look-back ``period`` or an explicit ``start``/``end`` range. Results
    are capped at the most recent 250 rows, with ``truncated`` set when cut.
    """
    return client.get_history(
        symbol, period=period, interval=interval, start=start, end=end
    )


def get_company_info(symbol: Symbol) -> dict[str, Any]:
    """Get a company profile and key statistics for a Yahoo symbol.

    Returns name, sector/industry, location, employee count, and valuation
    metrics (market cap, P/E, beta, 52-week range, dividend yield) plus a
    business summary.
    """
    return client.get_company_info(symbol)


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

    Each row is a line item and each column a reporting period, most recent
    first.
    """
    return client.get_financials(symbol, statement=statement, freq=freq)


def get_dividends(symbol: Symbol) -> dict[str, Any]:
    """Get the dividend and stock-split history for a Yahoo symbol."""
    return client.get_dividends(symbol)


def get_news(
    symbol: Symbol,
    limit: Annotated[
        int,
        Field(description="Maximum number of headlines to return.", ge=1, le=10),
    ] = 10,
) -> dict[str, Any]:
    """Get recent news headlines for a Yahoo symbol (up to ``limit``, 1-10).

    Each article includes title, summary, publisher, publish time, and URL.
    """
    return client.get_news(symbol, limit=limit)


def get_recommendations(symbol: Symbol) -> dict[str, Any]:
    """Get analyst recommendation trends and price targets for a Yahoo symbol.

    Returns the buy/hold/sell trend over recent months plus current/high/low/
    mean/median analyst price targets when available.
    """
    return client.get_recommendations(symbol)


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
    for that date, up to 60 strikes each centred on the current price, with
    ``truncated`` set when a wider chain was cut. Yahoo carries chains for
    US-listed instruments only, so a non-US symbol has none and that says
    nothing about the symbol.
    """
    return client.get_options(symbol, expiration=expiration)


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


def get_estimates(symbol: Symbol) -> dict[str, Any]:
    """Get forward analyst estimates for a Yahoo symbol.

    Returns earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (small tables keyed by period). Equity-only, empty for ETFs,
    funds, and crypto.
    """
    return client.get_estimates(symbol)


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
    return client.get_upgrades_downgrades(symbol, limit=limit)


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
    return client.get_holders(symbol, limit=limit)


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
    return client.get_insider_activity(symbol, limit=limit)


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


def get_calendar(symbol: Symbol) -> dict[str, Any]:
    """Get upcoming corporate-calendar events for a Yahoo symbol.

    Returns the next earnings date(s) with analyst estimate ranges and the next
    dividend / ex-dividend dates. Equity-only, empty for ETFs, funds, and crypto.
    """
    return client.get_calendar(symbol)


def get_shares(
    symbol: Symbol,
    start: Annotated[
        str | None,
        Field(
            description="Start date 'YYYY-MM-DD'. Without it the series covers "
            "the last 18 months only."
        ),
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
    recent ``limit`` points are returned. Without ``start`` the series covers
    the last 18 months, so pass one for anything older.
    """
    return client.get_shares(symbol, start=start, end=end, limit=limit)


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
    return client.get_fund_data(symbol, limit=limit)


# Built from yfinance's own constant (via client) so the tool description the
# LLM sees stays in sync with upstream's sector keys.
_SECTOR_KEYS_DESC = (
    "A Yahoo sector key (lowercase, hyphenated). One of: "
    + ", ".join(client.SECTOR_KEYS)
    + "."
)


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
    return client.get_sector(key, limit=limit)


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
    return client.get_industry(key, limit=limit)


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


# The listing order a client sees.
_TOOLS = (
    search,
    get_quote,
    get_quotes,
    get_history,
    get_company_info,
    get_financials,
    get_dividends,
    get_news,
    get_recommendations,
    get_options,
    get_earnings,
    get_estimates,
    get_upgrades_downgrades,
    get_holders,
    get_insider_activity,
    get_sec_filings,
    get_calendar,
    get_shares,
    get_fund_data,
    get_sector,
    get_industry,
    get_market,
)


def build_server() -> MCPServer:
    """A server with every tool registered, ready to be handed to a transport.

    ``name`` is the programmatic identifier reported in the MCP initialize
    handshake and is kept identical to the PyPI distribution name, so the
    server a client lists is traceable to the package it came from. ``title``
    is what a client shows to a person.
    """
    server = MCPServer(
        name="benethos-yahoo-finance-mcp",
        title="Unofficial Yahoo Finance MCP Server",
        version=__version__,
        instructions=_INSTRUCTIONS,
    )
    for tool in _TOOLS:
        server.add_tool(tool, annotations=_READ_ONLY)
    return server


def __getattr__(name: str) -> Any:
    """``server.mcp``: a server built on first use, for inspecting the tools.

    Kept for the one-liners that list what a client would see, see CLAUDE.md.
    Serving goes through :func:`build_server` from the command line.
    """
    if name == "mcp":
        server = build_server()
        globals()["mcp"] = server
        return server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
