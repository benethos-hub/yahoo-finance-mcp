"""The Yahoo symbol for a name or an ISIN."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ._base import Prompt


class FindSymbol(Prompt):
    name = "find_symbol"
    title = "Find a symbol"

    def render(
        self,
        query: Annotated[
            str,
            Field(description="Company name or ISIN to look up."),
        ],
        exchange: Annotated[
            str,
            Field(
                description="Preferred exchange, such as Xetra or NASDAQ. The "
                "home exchange if left empty."
            ),
        ] = "",
    ) -> str:
        """The Yahoo symbol for a company name or an ISIN, on the right exchange."""
        return f"""Find the Yahoo symbol for {query}.
Preferred exchange: {exchange} (none when empty)

1. Call `search` with {query} and limit 25, since an ISIN often has a listing \
on many exchanges.
2. List the matches as a table: symbol, name, exchange and type.
3. With a preferred exchange, pick the listing there, and when it has none, \
say so and name the others. Without one, recommend the listing on the \
company's home exchange, say why, and name the other listings as \
alternatives.

If nothing comes back and {query} has six letters and digits, it is likely a \
German WKN. WKNs resolve nowhere, not even through `search`. Say so and ask \
for the ISIN or the company name rather than guessing. Pass on every symbol \
exactly as `search` returns it, never build one by adding an exchange suffix."""
