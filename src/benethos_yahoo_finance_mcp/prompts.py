"""The prompts a client offers a person: recipes that chain the tools.

A prompt asks Yahoo nothing. It returns one user message that tells the model
which tools to call, in which order, and which traps of the data to mind, so
a person who picks "Stock snapshot" and types a symbol gets the same careful
sequence every time. Each recipe gathers and reports data. None of them judges
an instrument or recommends anything, that is left to the person.

The text names tools and fields in backticks, and ``tests/test_prompts.py``
checks every such name against the registered tools and the fields they
return, so a renamed tool cannot leave a recipe pointing nowhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

__all__ = ["register_prompts"]

_SYMBOL = Annotated[
    str,
    Field(description="Yahoo ticker such as SAP.DE, an ISIN, or a company name."),
]

_RESOLVE = (
    "If {what} is a company name rather than a ticker or an ISIN, resolve it with "
    "`search` first and use the symbol it returns. Tickers and ISINs go to every "
    "tool as they are."
)

# Closes every recipe, so each one minds the same traps of the data.
_RULES = (
    "Every price and figure is in the instrument's own currency and is never "
    "converted. Prices of London listings are in pence (GBp). The data comes "
    "from Yahoo's unofficial endpoints and may be delayed. Name every figure that "
    "is missing rather than estimating it. Report what the data shows and give "
    "no buy, sell or hold recommendation."
)


def snapshot(symbol: _SYMBOL) -> str:
    """A factual overview of one instrument: price, range, valuation, analysts."""
    return f"""Give a factual snapshot of {symbol}.

1. {_RESOLVE.format(what=symbol)}
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

{_RULES}"""


def compare(
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
{_RESOLVE.format(what="an entry")}
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

{_RULES}"""


def earnings_preview(symbol: _SYMBOL) -> str:
    """What to expect from the next report of a company, and its record so far."""
    return f"""Prepare an earnings preview for {symbol}.

1. {_RESOLVE.format(what=symbol)}
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

{_RULES}"""


def etf_profile(symbol: _SYMBOL) -> str:
    """What a fund or ETF holds, what it costs and how it did."""
    return f"""Profile the fund or ETF {symbol}.

1. {_RESOLVE.format(what=symbol)}
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

{_RULES}"""


def find_symbol(
    query: Annotated[
        str,
        Field(description="Company name or ISIN to look up."),
    ],
    exchange: Annotated[
        str | None,
        Field(description="Preferred exchange, such as Xetra or NASDAQ."),
    ] = None,
) -> str:
    """The Yahoo symbol for a company name or an ISIN, on the right exchange."""
    if exchange:
        choice = (
            f"Pick the listing on {exchange}. If there is none, say so and "
            "name the others."
        )
    else:
        choice = (
            "Recommend the listing on the company's home exchange and say why. "
            "Name the other listings as alternatives."
        )
    return f"""Find the Yahoo symbol for {query}.

1. Call `search` with {query} and limit 25, since an ISIN often has a listing \
on many exchanges.
2. List the matches as a table: symbol, name, exchange and type.
3. {choice}

If nothing comes back and {query} has six letters and digits, it is likely a \
German WKN. WKNs resolve nowhere, not even through `search`. Say so and ask \
for the ISIN or the company name rather than guessing. Pass on every symbol \
exactly as `search` returns it, never build one by adding an exchange suffix."""


def register_prompts(server: MCPServer) -> None:
    """Register every prompt with ``server``, in the order a client lists them."""
    for prompt, title in (
        (snapshot, "Stock snapshot"),
        (compare, "Compare instruments"),
        (earnings_preview, "Earnings preview"),
        (etf_profile, "ETF profile"),
        (find_symbol, "Find a symbol"),
    ):
        server.prompt(title=title)(prompt)
