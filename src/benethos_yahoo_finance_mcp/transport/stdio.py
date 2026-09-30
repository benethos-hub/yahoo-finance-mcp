"""Serving the tools over stdio, the transport a local client starts itself."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer


def run_stdio(server: MCPServer) -> None:
    """Serve on stdin and stdout until the client closes the pipe."""
    server.run(transport="stdio")
