"""Dividends per position and month, the one recipe that calculates.

It is also the one that takes personal data. The share counts reach this
server in the ``positions`` argument and go into the text only. No tool and
nothing at Yahoo receives them, and no log line carries them,
tests/test_prompts.py holds both.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ._base import RESOLVE, Prompt


class DividendCalendar(Prompt):
    name = "dividend_calendar"
    title = "Dividend calendar"

    def render(
        self,
        positions: Annotated[
            str,
            Field(
                description="Holdings with their share counts in any form, such "
                "as SAP.DE:50, 50x IE00B4L5Y983, or rows pasted from a bank "
                "export. An entry without a count is shown per share only."
            ),
        ],
        year: Annotated[
            str,
            Field(
                description="Calendar year such as 2027. The current year if left "
                "empty."
            ),
        ] = "",
        currency: Annotated[
            str,
            Field(
                description="Currency every amount is converted to, such as EUR. "
                "EUR if left empty."
            ),
        ] = "",
    ) -> str:
        """Dividends per position and month for a year, paid and forecast, by rules."""
        return f"""Build a dividend calendar from these positions: {positions}
Year: {year} (the current year when empty)
Currency: {currency} (EUR when empty)

The positions may come in any form: SAP.DE:50, 50x IE00B4L5Y983, or rows \
pasted from a bank export or a spreadsheet with columns of their own. Read \
from each entry the instrument, by its ISIN where there is one and else by \
ticker or name, and the number of shares. A decimal comma is a decimal, so \
0,75 is three quarters of a share. Ignore every other column, an account number \
above all. An entry without a count is a watch item, shown per share and left \
out of the totals. The share counts are for the calculation only. Pass them, \
and anything else from the positions but the instrument, to no tool.

1. {RESOLVE.format(what="an entry")} A German WKN resolves nowhere. Use the \
ISIN of the same row where there is one, and else ask for it.
2. In one parallel block, call `get_dividends` for every position, \
`get_calendar` for every single stock (ETFs and funds have none), and \
`get_quote` for the currency of every listing. For every other currency, call \
`get_quote` on its rate against the calendar's currency, such as EURUSD=X for \
US dollars against euros.

Calculate by these fixed rules, so that the same data always gives the same \
numbers.

- Pay date. The dividend history is dated by the ex-date. When `get_calendar` \
gives an ex-date and a pay date of the same payment 0 to 70 days apart, that \
gap applies to every payment of the position. Otherwise add 14 days and mark \
the pay date as estimated. The pay date decides the month.
- Basis. The payments with a pay date in the 365 days before today. When one \
calendar month appears twice, keep only the later payment.
- Forecast. Each payment of the basis recurs in the same month at the same \
amount, with no growth and no cut.
- Paid or forecast. In the current year the months before the current one \
show what was paid, at today's share count. From the current month on, and \
for a coming year throughout, the forecast applies.
- Currency. Amount per share times the shares in the distribution currency, \
converted at today's rate. EURUSD=X is US dollars per euro, so a dollar amount \
is divided by it. An amount in GBp is in pence, divide it by 100 first. \
Without a rate the amount stays in its own currency and out of the total. \
Round each payment to cents and add up the rounded payments.
- Gross. Every amount is before tax, nothing is deducted or estimated.
- Splits. The history is already restated to today's share count.
- Special payments. A payment of one and a half times the position's median \
or more stays in and is named as a possible special dividend. A position \
without payments shows "no distributions in the data".

Then report a table with a row per position, a column per month and one for \
the year, forecast values in italics and the totals below, the rates used, and \
a list of gaps: estimated pay dates, missing data or rates, possible special \
dividends, missing share counts.

The data comes from Yahoo's unofficial endpoints and may be delayed, and every \
future amount is a forecast. Name every gap rather than filling it with a \
guess. Give no buy, sell or hold recommendation and no tax advice."""
