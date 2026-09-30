"""The tools a client sees, one module per subject, mirroring ``yahoo``.

``tools/options.py`` exposes what ``yahoo/options.py`` fetches, and so on for
every subject. A tool is thin: it declares its parameters for the schema, and
its docstring is the description the model reads. It hands the arguments to
the yahoo function of the same name and returns what comes back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import analysts, browse, company, funds, options, ownership, quotes

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

__all__ = ["register_tools"]

# The order of this tuple is the order a client lists the tools in.
_MODULES = (quotes, company, analysts, ownership, options, funds, browse)


def register_tools(server: MCPServer) -> None:
    """Register every tool with ``server``."""
    for module in _MODULES:
        module.register(server)
