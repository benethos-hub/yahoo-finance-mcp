"""A factual overview of one instrument."""

from __future__ import annotations

from ._base import RESOLVE, RULES, Prompt, Symbol


class Snapshot(Prompt):
    name = "snapshot"
    title = "Stock snapshot"

    def render(self, symbol: Symbol) -> str:
        """A factual overview of one instrument: price, range, valuation, analysts."""
        return f"""Give a factual snapshot of {symbol}.

1. {RESOLVE.format(what=symbol)}
2. Call `get_quote`. Its `quoteType` decides the rest. For ETF or MUTUALFUND \
call `get_fund_data` and skip steps 3 and 4. For anything other than EQUITY \
skip step 4, analyst data exists for equities only.
3. Call `get_company_info` for the business, the sector and the valuation.
4. Call `get_recommendations` for the analyst trend and the price targets.
5. Call `get_history` with period 1y and interval 1d.

Then report what the instrument is, the last price with its currency, the \
distance from the 52-week high and low in percent, the deepest drawdown of the \
year from the daily closes, the trailing and the forward P/E each named as \
such, and the analyst consensus with the distance of the mean price target \
from the last price. `get_history` keeps the most recent 250 rows, so when \
`truncated` is set the year starts a few days late. Say so.

{RULES}"""
