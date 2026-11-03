"""Fund and ETF profiles."""

from __future__ import annotations

from typing import Any

from yfinance.exceptions import YFDataException

from .. import cache
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers

# Yahoo states a fund's ratios and returns in two scales: the expense ratio of
# fund_operations and the multi-year returns of `info` as fractions (0.000945,
# 0.2328), `info`'s ytdReturn and netExpenseRatio in percent (12.68, 0.0945).
# Probed 2026-11-03 for SPY, QQQ and FFOJX. The answer gives every one as a
# fraction, rounded past float noise (0.0018000001).
_DECIMALS = 6

# `info` keys read as fractions already, and the name each gets.
_FRACTION_FIELDS = (
    ("threeYearAverageReturn", "three_year_average_return"),
    ("fiveYearAverageReturn", "five_year_average_return"),
)


def _number(value: Any) -> float | None:
    """``value`` as a float, ``None`` for a missing or NaN value."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # NaN is not equal to itself


def _fraction(value: Any, *, percent: bool = False) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number / 100 if percent else number, _DECIMALS)


def _operations(frame: Any, column: str) -> dict[str, Any]:
    """One column of ``fund_operations`` as {row: value}, empty without it."""
    try:
        return dict(frame[column])
    except (KeyError, TypeError):
        return {}


def _key_figures(operations: Any, info: dict[str, Any]) -> dict[str, Any]:
    """Costs, size and returns, each a fraction, the missing ones left out.

    The fund's own column of ``fund_operations`` is its first, the second is
    "Category Average". Its "Total Net Assets" is not used: on 2026-11-03 it
    gave the same number for the fund and its category, in no stated unit,
    while ``info``'s totalAssets matched the fund's published size.
    """
    columns = list(getattr(operations, "columns", ()))
    own = _operations(operations, columns[0]) if columns else {}
    category = _operations(operations, "Category Average")
    expense = _fraction(own.get("Annual Report Expense Ratio"))
    if expense is None:
        expense = _fraction(info.get("netExpenseRatio"), percent=True)
    figures: dict[str, Any] = {
        "expense_ratio": expense,
        "category_expense_ratio": _fraction(
            category.get("Annual Report Expense Ratio")
        ),
        "holdings_turnover": _fraction(own.get("Annual Holdings Turnover")),
        "total_assets": _number(info.get("totalAssets") or info.get("netAssets")),
        "ytd_return": _fraction(info.get("ytdReturn"), percent=True),
    }
    for key, name in _FRACTION_FIELDS:
        figures[name] = _fraction(info.get(key))
    return {name: value for name, value in figures.items() if value is not None}


@cache.cached("fund_data")
def get_fund_data(symbol: str, *, limit: int = 25) -> dict[str, Any]:
    """Return fund/ETF profile data for ``symbol``.

    Includes the fund overview, the key figures (costs, size and returns, see
    ``_key_figures``), asset-class and sector weightings, and the top
    holdings. Fund/ETF-only; raises for stocks and crypto, which have no fund
    data.
    """
    ticker = tickers.get_ticker(symbol)
    # yfinance raises YFDataException for a stock or crypto, which has no
    # fund data: that is a missing symbol, not a failure. So is an unknown
    # symbol, which this route answers with a 404 that yfinance lets through,
    # while its other scrapers read the same error as no data.
    with tickers.upstream(
        f"Failed to load fund data for {symbol!r}",
        not_found=(YFDataException,),
        not_found_status=404,
        symbol=symbol,
    ):
        fd = ticker.funds_data
        description = fd.description
        overview = fd.fund_overview
        asset_classes = fd.asset_classes
        sector_weightings = fd.sector_weightings
        top_holdings = fd.top_holdings
        operations = fd.fund_operations
        info = ticker.info or {}

    holdings_rows = dataframe_to_records(
        top_holdings, max_rows=limit, index_name="symbol", head=True
    )
    return {
        "symbol": tickers.normalize(symbol),
        "description": description,
        "fund_overview": to_jsonable(overview),
        "key_figures": _key_figures(operations, info),
        "asset_classes": to_jsonable(asset_classes),
        "sector_weightings": to_jsonable(sector_weightings),
        "top_holdings": holdings_rows,
    }
