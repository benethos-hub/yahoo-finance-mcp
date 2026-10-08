"""Fund and ETF profiles."""

from __future__ import annotations

from typing import Any

from yfinance.exceptions import YFDataException

from .. import cache
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers


@cache.cached("fund_data")
def get_fund_data(symbol: str, *, limit: int = 25) -> dict[str, Any]:
    """Return fund/ETF profile data for ``symbol``.

    Includes the fund overview, asset-class and sector weightings, and the top
    holdings. Fund/ETF-only; raises for stocks and crypto, which have no fund
    data.
    """
    ticker = tickers.get_ticker(symbol)
    # yfinance raises YFDataException for a stock or crypto, which has no
    # fund data: that is a missing symbol, not a failure.
    with tickers.upstream(
        f"Failed to load fund data for {symbol!r}",
        not_found=(YFDataException,),
        symbol=symbol,
    ):
        fd = ticker.funds_data
        description = fd.description
        overview = fd.fund_overview
        asset_classes = fd.asset_classes
        sector_weightings = fd.sector_weightings
        top_holdings = fd.top_holdings

    holdings_rows = dataframe_to_records(
        top_holdings, max_rows=limit, index_name="symbol", head=True
    )
    return {
        "symbol": tickers.normalize(symbol),
        "description": description,
        "fund_overview": to_jsonable(overview),
        "asset_classes": to_jsonable(asset_classes),
        "sector_weightings": to_jsonable(sector_weightings),
        "top_holdings": holdings_rows,
    }
