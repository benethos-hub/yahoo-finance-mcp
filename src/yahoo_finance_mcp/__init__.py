"""Yahoo Finance MCP server.

An MCP server that exposes Yahoo Finance data (via the ``yfinance`` library)
to MCP clients such as Claude Desktop over stdio or HTTP.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yahoo-finance-mcp")
except PackageNotFoundError:  # pragma: no cover - package not installed
    __version__ = "0.0.0+unknown"
