"""What every prompt shares: the base class, the symbol argument, the rules.

A prompt is a subclass of :class:`Prompt`, one per module, its module named
like the prompt. It sets ``name`` and ``title`` and writes ``render``. The
parameters of ``render`` become the arguments a client asks a person for, its
docstring the description a client shows, as a tool's do.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Annotated, Any, ClassVar

from pydantic import Field

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

# Unlike the tools' symbol this one takes a company name too, since every
# recipe resolves a name through `search` before it calls anything else.
Symbol = Annotated[
    str,
    Field(description="Yahoo ticker such as SAP.DE, an ISIN, or a company name."),
]

# The first step of most recipes, with {what} the argument it is about.
RESOLVE = (
    "If {what} is a company name rather than a ticker or an ISIN, resolve it with "
    "`search` first and use the symbol it returns. Tickers and ISINs go to every "
    "tool as they are."
)

# Closes every data recipe, so each one minds the same traps of the data.
RULES = (
    "Every price and figure is in the instrument's own currency and is never "
    "converted. Prices of London listings are in pence (GBp). The data comes "
    "from Yahoo's unofficial endpoints and may be delayed. Name every figure that "
    "is missing rather than estimating it. Report what the data shows and give "
    "no buy, sell or hold recommendation."
)


class Prompt(ABC):
    """One recipe a client offers a person.

    ``render`` returns the text of the one user message the client sends. It
    asks Yahoo nothing and writes no log line. Every argument is a string or
    left out, as MCP prompt arguments are.

    ``render`` is a plain template: each argument goes into the text as it
    came, an optional one defaults to ``""``, and the text says in words what
    an empty one means. No condition picks another sentence and no default
    stands in for an empty value. Claude Desktop checks a prompt of the
    pinned bundle against the manifest's text with the arguments put in, an
    empty one as ``""``, and refuses one that differs (measured 2026-11-11).
    """

    #: The name a client calls the prompt by, and the name of its module.
    name: ClassVar[str]
    #: What a client shows a person in place of the name.
    title: ClassVar[str]

    @abstractmethod
    def render(self, *args: Any, **kwargs: Any) -> str:
        """The message, with the arguments filled in."""

    def register(self, server: MCPServer) -> None:
        """Add this prompt to ``server``, described by the docstring of ``render``."""
        server.prompt(name=self.name, title=self.title)(self.render)
