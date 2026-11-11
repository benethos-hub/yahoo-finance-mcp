"""Several instruments side by side."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ._base import RESOLVE, RULES, Prompt


class Compare(Prompt):
    name = "compare"
    title = "Compare instruments"

    def render(
        self,
        symbols: Annotated[
            str,
            Field(description="Two or more tickers or ISINs, separated by commas."),
        ],
        period: Annotated[
            str,
            Field(description="Look-back window such as 3mo, 1y or 5y."),
        ] = "1y",
    ) -> str:
        """Several instruments side by side over one period, on one basis."""
        return f"""Compare {symbols} over {period}.

1. Each comma-separated entry is one instrument. \
{RESOLVE.format(what="an entry")}
2. Call `get_quotes` once with all of them, and name every symbol it lists \
under `not_found`.
3. Call `get_history` for each with period {period}, with interval 1d up to \
6mo and 1wk beyond.
4. Call `get_company_info` for each, for market cap, trailing P/E and dividend \
yield.

Then report one table with a row per instrument: the last price and its \
currency, the performance over the period rebased to 100 at the first date all \
of them share, the deepest drawdown, the market cap, the trailing P/E and the \
dividend yield. Use the trailing P/E in every row, never the forward one for \
some, and leave a cell empty where an instrument has no such figure. The \
closes are adjusted for dividends and splits. Performance is measured in each \
instrument's own currency, so when the currencies differ a move between them \
is not in it. Say so.

{RULES}"""
