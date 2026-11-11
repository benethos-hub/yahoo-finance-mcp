"""What a fund or ETF holds, costs and returned."""

from __future__ import annotations

from ._base import RESOLVE, RULES, Prompt, Symbol


class EtfProfile(Prompt):
    name = "etf_profile"
    title = "ETF profile"

    def render(self, symbol: Symbol) -> str:
        """What a fund or ETF holds, what it costs and how it did."""
        return f"""Profile the fund or ETF {symbol}.

1. {RESOLVE.format(what=symbol)}
2. Call `get_fund_data`. If it answers that {symbol} is not a fund, stop there \
and say so.
3. Call `get_quote` for the last price and its currency.
4. When the three- or five-year return is missing, which is common for European \
ETFs, call `get_history` with period 5y and interval 1mo and compute the \
annualised return from the closes, which are adjusted for distributions. Say \
that it was computed, not reported.

Then report what the fund invests in and who runs it, the expense ratio against \
the category average, the total assets, the return year to date and over three \
and five years, the ten largest holdings with their weights, and the largest \
sector and asset-class weights. Ratios and returns arrive as fractions, 0.0007 \
is 0.07%. A fund has no statements, earnings or analyst coverage, so do not \
call `get_financials`, `get_earnings` or `get_recommendations`.

{RULES}"""
