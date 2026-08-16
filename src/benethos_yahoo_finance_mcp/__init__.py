"""Unofficial Yahoo Finance MCP server.

An MCP server that exposes Yahoo Finance data (via the ``yfinance`` library)
to MCP clients such as Claude Desktop over stdio or HTTP. Not affiliated with
Yahoo.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # The distribution (PyPI) name, which differs from the import package name.
    __version__ = version("benethos-yahoo-finance-mcp")
except PackageNotFoundError:  # pragma: no cover - package not installed
    __version__ = "0.0.0+unknown"
