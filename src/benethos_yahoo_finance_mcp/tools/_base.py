"""What every tool shares: the symbol parameter, the hints, the log line.

A tool is registered with :func:`register_tool`, which sets the annotations
every tool carries and wraps it so each call writes its one line to the log.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from .. import logbook
from ..errors import RateLimitError

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

# Every tool here only reads, and every one of them asks Yahoo, so they all
# carry the same two hints. A client may use them to call a read-only tool
# without asking the user first. destructiveHint and idempotentHint are left
# out on purpose: the spec defines them only for tools that are not read-only,
# and this server has none, so they would be bytes in every tool listing that
# no client is meant to read.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

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


def register_tool(server: MCPServer, tool: Callable[..., Any]) -> None:
    """Add ``tool`` to ``server`` with the shared hints and its log line."""
    server.add_tool(_logged(tool), annotations=READ_ONLY)


def _logged(tool: Callable[..., Any]) -> Callable[..., Any]:
    """The tool, writing its one log line per call.

    ``wraps`` carries the name, the docstring and the signature over, so the
    schema a client sees is the tool's own. The SDK passes arguments by name,
    which is what the line reads its subject from.
    """
    name = tool.__name__

    @wraps(tool)
    def logged(**arguments: Any) -> Any:
        started = time.perf_counter()
        with logbook.calls.watching_cache():
            try:
                result = tool(**arguments)
            except RateLimitError:
                logbook.upstream.rate_limited(name, arguments)
                raise
            except Exception as exc:
                logbook.calls.ended(name, arguments, exc, time.perf_counter() - started)
                raise
            logbook.calls.read(name, arguments, result, time.perf_counter() - started)
        return result

    return logged
