"""The server's own status: what runs, and whether Yahoo answered.

Unlike every other tool, this one asks Yahoo nothing. It answers from memory
in plain text, one ``key: value`` per line, and writes no log line, since a
status question is not an activity worth one. With ``details`` it adds the
installed yfinance, which decides what the data looks like and can differ
between two installations of one version, and what the yahoo package remembers
of its last request: whether Yahoo answered, when, and whether the answer was
a rate limit. Never a request of its own.
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
    yfinance = _installed("yfinance")

    def server_status(
        details: Annotated[
            bool,
            Field(
                description="Also report the yfinance version, whether Yahoo "
                "answered, when, and whether it held the server off with a rate "
                "limit."
            ),
        ] = False,
    ) -> str:
        """Report this server's version, transport and uptime.

        With `details`, also the yfinance version in use, whether its last
        request reached Yahoo, how long ago, and whether Yahoo answered it with
        a rate limit, without asking Yahoo again. An
        answer holds for the moment it was given: after a restart or an update,
        call it again rather than rely on an earlier one.
        """
        lines = [f"{key}: {value}" for key, value in core.items()]
        lines.append(f"uptime_seconds: {int(time.monotonic() - started)}")
        if details:
            lines += [
                "details:",
                f"  yfinance: {yfinance}",
                "  upstream:",
                *_upstream(),
            ]
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
        reachable, checked, rate_limited = "unknown", "never", "unknown"
    else:
        reachable = _yes_no(last.reachable)
        checked = str(last.seconds_ago)
        rate_limited = _yes_no(last.rate_limited)
    # No token_set line: Yahoo is a public API and takes no key. Why a request
    # failed is said by rate_limited alone, never by Yahoo's own text.
    return [
        f"    reachable: {reachable}",
        f"    checked_seconds_ago: {checked}",
        f"    rate_limited: {rate_limited}",
    ]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _installed(package: str) -> str:
    """The installed version of ``package``, ``unknown`` rather than an error."""
    try:
        return version(package)
    except PackageNotFoundError:  # pragma: no cover - both are dependencies
        return "unknown"
