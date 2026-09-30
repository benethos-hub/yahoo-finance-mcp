"""Fund and ETF profiles."""

from __future__ import annotations

from typing import Any

from yfinance.exceptions import YFDataException, YFRateLimitError

from .. import cache
from ..errors import RateLimitError, SymbolNotFoundError
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
    try:
        fd = ticker.funds_data
        description = fd.description
        overview = fd.fund_overview
        asset_classes = fd.asset_classes
        sector_weightings = fd.sector_weightings
        top_holdings = fd.top_holdings
    except YFRateLimitError as exc:
        raise RateLimitError() from exc
    except YFDataException as exc:
        # Raised for non-funds (stocks/crypto have no fund data).
        raise SymbolNotFoundError(symbol) from exc
    except Exception as exc:  # noqa: BLE001
        raise tickers.wrap_upstream(
            exc, f"Failed to load fund data for {symbol!r}"
        ) from exc

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
