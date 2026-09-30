"""What analysts say: recommendations, estimates, rating changes and
earnings against them."""

from __future__ import annotations

from typing import Any

from .. import cache
from ..errors import SymbolNotFoundError
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers


@cache.cached("recommendations")
def get_recommendations(symbol: str) -> dict[str, Any]:
    """Return analyst recommendation trends and price targets for ``symbol``."""
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load recommendations for {symbol!r}"):
        recs = ticker.recommendations
        targets = ticker.analyst_price_targets

    # The trend table has a plain RangeIndex, which would come out as an
    # "index" of 0 to 3 on every row, while the column that names the row
    # ("0m", "-1m", ...) is "period". Make that the key and drop the counter.
    if recs is not None and "period" in recs.columns:
        recs = recs.set_index("period")
    trend = dataframe_to_records(recs, max_rows=12, index_name="period")
    if not trend and not targets:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": tickers.normalize(symbol),
        "price_targets": to_jsonable(targets) if targets else None,
        "recommendation_trend": trend,
    }


@cache.cached("earnings")
def get_earnings(symbol: str, *, limit: int = 12) -> dict[str, Any]:
    """Return upcoming and historical earnings for ``symbol``.

    Combines the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) with the recent earnings history. Equity-only;
    empty for ETFs/funds/crypto.
    """
    limit = max(1, min(int(limit), 50))
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load earnings for {symbol!r}"):
        dates = ticker.get_earnings_dates(limit=limit)
        history = ticker.earnings_history

    dates_rows = dataframe_to_records(dates, max_rows=limit, index_name="earnings_date")
    history_rows = dataframe_to_records(history, max_rows=limit, index_name="quarter")
    if not dates_rows and not history_rows:
        raise SymbolNotFoundError(symbol, reason=tickers.EQUITY_ONLY_REASON)

    return {
        "symbol": tickers.normalize(symbol),
        "earnings_dates": dates_rows,
        "earnings_history": history_rows,
    }


# Maps the output key to the Ticker attribute for the analyst-estimate tables.
_ESTIMATE_ATTRS = {
    "earnings_estimate": "earnings_estimate",
    "revenue_estimate": "revenue_estimate",
    "eps_trend": "eps_trend",
    "eps_revisions": "eps_revisions",
    "growth_estimates": "growth_estimates",
}


@cache.cached("estimates")
def get_estimates(symbol: str) -> dict[str, Any]:
    """Return forward analyst estimates for ``symbol``.

    Includes earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (each a small table keyed by period). Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = tickers.get_ticker(symbol)
    out: dict[str, Any] = {"symbol": tickers.normalize(symbol)}
    have_data = False
    for key, attr in _ESTIMATE_ATTRS.items():
        with tickers.upstream(f"Failed to load estimates for {symbol!r}"):
            df = getattr(ticker, attr)
        rows = dataframe_to_records(df, max_rows=12, index_name="period")
        if rows:
            have_data = True
        out[key] = rows

    if not have_data:
        raise SymbolNotFoundError(symbol, reason=tickers.EQUITY_ONLY_REASON)
    return out


@cache.cached("upgrades_downgrades")
def get_upgrades_downgrades(symbol: str, *, limit: int = 50) -> dict[str, Any]:
    """Return recent analyst rating changes for ``symbol``.

    Each entry is a firm's upgrade/downgrade with the from/to grade and action,
    most recent first. Equity-only; empty for ETFs/funds/crypto.
    """
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load upgrades/downgrades for {symbol!r}"):
        df = ticker.upgrades_downgrades

    if df is not None and not df.empty:
        # Source order varies, so sort newest-first before capping.
        df = df.sort_index(ascending=False)
    rows = dataframe_to_records(df, max_rows=limit, index_name="date", head=True)
    if not rows:
        raise SymbolNotFoundError(symbol, reason=tickers.EQUITY_ONLY_REASON)

    return {"symbol": tickers.normalize(symbol), "changes": rows}
