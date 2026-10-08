"""The MCP server: its identity and the instructions it sends a client.

:func:`build_server` makes a server with every tool from :mod:`.tools`
registered. Nothing runs at import beyond definitions, the command line in
:mod:`.cli` decides when a server is built and which transport it is handed to.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError as SDKToolError
from pydantic import ValidationError

from . import __version__, logbook
from .tools import register_tools

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
`SAP.DE` or `BTC-USD`, or a plain ISIN such as `US0378331005`, which is \
looked up through Yahoo's search and replaced by its ticker before the call. \
Pass either through unchanged — a symbol should never be \
assembled or transformed. A company name is not a symbol: resolve it with \
`search` and pass back what that returns. German WKNs resolve nowhere, not even \
through `search`, so ask for a ticker, an ISIN or the company name instead. \
Four tools are the exceptions: `get_sector`, `get_industry` and `get_market` \
take a key, not a ticker, and `screen` takes filters and finds the symbols \
itself.

Missing data is normal. Analyst, holder, earnings, insider, filing and \
calendar data exist for equities only, and for an ETF, fund or crypto those \
tools answer with an error that says so, which does not mean the symbol is \
wrong. `get_fund_data` is the reverse and fails for anything that is not a \
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


class _Server(MCPServer):
    """The SDK's server, noting arguments a tool's schema refused.

    Validation runs before the tool, so its own line never sees such a call.
    """

    async def call_tool(
        self, name: str, arguments: dict[str, Any], *args: Any, **kwargs: Any
    ) -> Any:
        try:
            return await super().call_tool(name, arguments, *args, **kwargs)
        except SDKToolError as exc:
            if isinstance(exc.__cause__, ValidationError):
                fields = sorted(
                    {
                        ".".join(str(p) for p in err["loc"])
                        for err in exc.__cause__.errors()
                    }
                )
                logbook.calls.arguments_refused(name, fields)
            raise


def build_server() -> MCPServer:
    """A server with every tool registered, ready to be handed to a transport.

    ``name`` is the programmatic identifier reported in the MCP initialize
    handshake and is kept identical to the PyPI distribution name, so the
    server a client lists is traceable to the package it came from. ``title``
    is what a client shows to a person.
    """
    # The constructor installs a RichHandler on the root logger if it has
    # none, see logbook.output.untouched_root.
    with logbook.output.untouched_root():
        server = _Server(
            name="benethos-yahoo-finance-mcp",
            title="Unofficial Yahoo Finance MCP Server",
            version=__version__,
            instructions=_INSTRUCTIONS,
        )
    register_tools(server)
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
