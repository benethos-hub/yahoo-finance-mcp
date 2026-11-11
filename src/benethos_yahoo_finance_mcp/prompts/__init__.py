"""The prompts a client offers a person: recipes that chain the tools.

A prompt asks Yahoo nothing. It returns one user message that tells the model
which tools to call, in which order, and which traps of the data to mind, so
a person who picks "Stock snapshot" and types a symbol gets the same careful
sequence every time. The data recipes gather and report data, and
``dividend_calendar`` also calculates. None of them judges an instrument or
recommends anything, that is left to the person.

Each prompt is a subclass of ``_base.Prompt`` in a module of its own name, as
each tool sits in the module of its subject. The text names tools and fields
in backticks, and ``tests/test_prompts.py`` checks every such name against
the registered tools and the fields they return, so a renamed tool cannot
leave a recipe pointing nowhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .compare import Compare
from .dividend_calendar import DividendCalendar
from .earnings_preview import EarningsPreview
from .etf_profile import EtfProfile
from .find_symbol import FindSymbol
from .snapshot import Snapshot

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

__all__ = ["register_prompts"]

# The order of this tuple is the order a client lists the prompts in.
_PROMPTS = (
    Snapshot(),
    Compare(),
    EarningsPreview(),
    EtfProfile(),
    DividendCalendar(),
    FindSymbol(),
)


def register_prompts(server: MCPServer) -> None:
    """Register every prompt with ``server``, in the order a client lists them."""
    for prompt in _PROMPTS:
        prompt.register(server)
