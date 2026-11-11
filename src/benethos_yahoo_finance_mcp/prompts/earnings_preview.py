"""What to expect from a company's next report."""

from __future__ import annotations

from ._base import RESOLVE, RULES, Prompt, Symbol


class EarningsPreview(Prompt):
    name = "earnings_preview"
    title = "Earnings preview"

    def render(self, symbol: Symbol) -> str:
        """What to expect from the next report of a company, and its record so far."""
        return f"""Prepare an earnings preview for {symbol}.

1. {RESOLVE.format(what=symbol)}
2. Call `get_calendar` for the next earnings date and the estimate ranges.
3. Call `get_earnings` for the reported EPS of the last quarters against the \
estimate.
4. Call `get_estimates` for the EPS and revenue estimates and how they were \
revised.
5. Call `get_upgrades_downgrades` and keep the rating changes of the last 30 \
days.

Pass `methodology` normalized to both `get_earnings` and `get_estimates`, so \
reported and expected EPS share one basis, and name the basis. When it comes \
back empty, use gaap for both and say so. These tools cover equities only. If \
the first one answers that {symbol} is an ETF, a fund or a cryptocurrency, \
stop there and say so.

Then report the date of the next report, the EPS and revenue expected for that \
quarter, how often the company beat or missed the estimate in the quarters \
returned and by how much, which way the estimates were revised over the last \
7, 30 and 90 days, and each recent rating change with the firm and the grades.

{RULES}"""
