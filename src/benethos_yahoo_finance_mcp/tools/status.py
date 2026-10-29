"""The server's own status: what runs, and whether Yahoo answered.

Unlike every other tool, this one asks Yahoo nothing. It answers from memory
in plain text, one ``key: value`` per line, and writes no log line, since a
status question is not an activity worth one. With ``details`` it adds what
the yahoo package remembers of its last request, never a request of its own.
"""

from __future__ import annotations

import sys
import time
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Annotated

from mcp.types import ToolAnnotations
from pydantic import Field

from .. import yahoo

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

# Read-only like the rest, but closed-world: the answer comes from this
# process alone.
_HINTS = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def register(server: MCPServer, transport: str) -> None:
    """Add ``server_status`` to ``server``, its uptime counted from now.

    Name and version are the server's own, the ones the MCP handshake reports.
    """
    started = time.monotonic()
    python = ".".join(str(part) for part in sys.version_info[:3])
    core = {
        "name": server.name,
        "version": server.version,
        "transport": transport,
        "python": python,
        "mcp": _installed("mcp"),
    }

    def server_status(
        details: Annotated[
            bool,
            Field(description="Also report whether Yahoo answered, and when."),
        ] = False,
    ) -> str:
        """Report this server's version, transport and uptime.

        With `details`, also whether its last request reached Yahoo and how
        long ago, without asking Yahoo again.
        """
        lines = [f"{key}: {value}" for key, value in core.items()]
        lines.append(f"uptime_seconds: {int(time.monotonic() - started)}")
        if details:
            lines += ["details:", "  upstream:", *_upstream()]
        return "\n".join(lines)

    server.add_tool(
        server_status,
        title="Server status",
        annotations=_HINTS,
        structured_output=False,
    )


def _upstream() -> list[str]:
    """The ``upstream:`` block's lines, from the last request to Yahoo."""
    last = yahoo.last_answer()
    if last is None:
        reachable, checked = "unknown", "never"
    else:
        reachable, checked = ("yes" if last[0] else "no"), str(last[1])
    # No token_set line: Yahoo is a public API and takes no key.
    return [
        f"    reachable: {reachable}",
        f"    checked_seconds_ago: {checked}",
    ]


def _installed(package: str) -> str:
    """The installed version of ``package``, ``unknown`` rather than an error."""
    try:
        return version(package)
    except PackageNotFoundError:  # pragma: no cover - mcp is a dependency
        return "unknown"
