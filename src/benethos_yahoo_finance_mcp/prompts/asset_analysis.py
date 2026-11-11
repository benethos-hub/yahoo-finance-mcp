"""A factual analysis of one instrument, with the checks a data copy skips.

It gathers and calculates, and it stops short of judging: no outlook by
horizon, no case for or against, no recommendation. That part is left to
the person.
"""

from __future__ import annotations

from ._base import RESOLVE, RULES, Prompt, Symbol


class AssetAnalysis(Prompt):
    name = "asset_analysis"
    title = "Asset analysis"

    def render(self, symbol: Symbol) -> str:
        """One instrument in facts and own calculations: price, valuation, analysts."""
        return f"""Write a factual analysis of {symbol}.

1. {RESOLVE.format(what=symbol)} If the name that comes back could be \
mistaken for a better-known company, say so at the very top.
2. Call `get_quote`. Its `quoteType` decides the rest. For ETF or MUTUALFUND \
call `get_fund_data` and `get_history` with period 1y and interval 1d, and skip \
step 3. For CRYPTOCURRENCY only `get_history` follows.
3. For EQUITY, in one parallel block: `get_company_info`, \
`get_recommendations`, `get_calendar`, `get_shares`, `get_financials` with the \
annual income statement, `get_news` with limit 5, and `get_history` with period \
1y and interval 1d.

Then calculate, each with its derivation shown:

- Price targets. The distance of the last price from the mean, the median, \
the highest and the lowest target, in percent. Say when the price lies outside \
the range of targets, when mean and median lie far apart, and when the ratings \
in `recommendation_trend` are unanimous.
- Share count. The market cap divided by the last price gives the share count \
the price data assumes, the same count `get_shares` reports last. Hold it \
against the diluted average shares of the last fiscal year in the income \
statement, which come from the report. A year of buybacks or issues moves \
them a few percent apart. When they differ by more than ten percent, name \
both, value with the higher, and look for the capital measure behind it in \
the `get_shares` series and the headlines.
- Several years. Revenue, net income and diluted average shares from the \
income statement as one small table, oldest year first.
- Valuation. Name every P/E with its basis, trailing or forward. A negative or \
missing P/E means a loss: write loss-making, never quote it as a multiple, and \
give price to sales instead, the market cap divided by the last annual \
revenue. A foreign listing can report its statements in another currency than \
its price, so check the scale before dividing and say so when in doubt.
- Position. The last price against the 50- and 200-day averages, in one \
sentence, and the deepest drawdown of the year from the daily closes.

Then report: a top line with price, market cap and 52-week range, two or three \
sentences on what the figures show, the multi-year table, the valuation with \
the own calculations, the analyst picture with the number of buy, hold and \
sell ratings, the next report date, the headlines with their dates, and a \
list of gaps and contradictions in the data. Quote beta only when it is \
plausible, a negative beta or one far above 3 is an artefact. An ex-dividend \
date in the past in `get_calendar` is the last one, not the next. During \
trading hours the last row of `get_history` is the running session, not a \
close. The headlines can lag behind what moved the price.

Leave out an outlook by horizon and any case for or against, the judgement is \
the person's.

{RULES}"""
