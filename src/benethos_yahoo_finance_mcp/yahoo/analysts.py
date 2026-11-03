"""What analysts say: recommendations, estimates, rating changes and
earnings against them."""

from __future__ import annotations

from typing import Any

from .. import cache
from ..errors import SymbolNotFoundError, ToolError
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers

# The recommendation trend and the estimate tables have a row per period:
# 0m to -3m, or 0q, +1q, 0y, +1y, and growth adds LTG. At most five on
# 2026-10-08 for AAPL. The cap keeps them whole with room to spare, it is
# not a page size.
_PERIOD_ROWS = 12


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
    trend = dataframe_to_records(recs, max_rows=_PERIOD_ROWS, index_name="period")
    if not trend and not targets:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": tickers.normalize(symbol),
        "price_targets": to_jsonable(targets) if targets else None,
        "recommendation_trend": trend,
    }


# The bases Yahoo counts earnings per share on, as yfinance names them.
# Yahoo picks one per symbol by default, GAAP for AMZN and GOOGL, normalized
# for MSFT and SAP.DE, and the two can differ by a quarter (GOOGL's EPS
# estimate for the year, 19.71 against 15.50 on 2026-11-03). yfinance 1.8.0
# asks for either (ranaroussi/yfinance#2999).
EPS_METHODOLOGIES = ("gaap", "normalized")


def _methodology(value: str | None) -> str | None:
    """``value`` checked and lowered, ``None`` for Yahoo's default."""
    if value is None or not value.strip():
        return None
    chosen = value.strip().lower()
    if chosen not in EPS_METHODOLOGIES:
        raise ToolError(
            f"Invalid methodology {value!r}, expected one of "
            f"{', '.join(EPS_METHODOLOGIES)}, or none for Yahoo's default."
        )
    return chosen


# The most earnings dates get_earnings returns.
EARNINGS_MAX = 50


@cache.cached("earnings")
def get_earnings(
    symbol: str, *, limit: int = 12, methodology: str | None = None
) -> dict[str, Any]:
    """Return upcoming and historical earnings for ``symbol``.

    Combines the earnings calendar (upcoming and past dates with EPS estimate,
    reported EPS, and surprise %) with the recent earnings history. Equity-only:
    an ETF, fund or crypto symbol raises SymbolNotFoundError with
    ``tickers.EQUITY_ONLY_REASON``. ``methodology`` picks the EPS basis of
    the history, ``gaap`` or ``normalized``, ``None`` for Yahoo's default.
    The calendar has no such choice.
    """
    limit = max(1, min(int(limit), EARNINGS_MAX))
    chosen = _methodology(methodology)
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load earnings for {symbol!r}"):
        dates = ticker.get_earnings_dates(limit=limit)
        history = ticker.get_earnings_history(methodology=chosen)

    # yfinance rounds limit up to a page of 25, 50 or 100 and returns all of it,
    # so the cut happens here. Newest first, which holds the next date and the
    # latest quarters, whichever order the page came in.
    if dates is not None and not dates.empty:
        dates = dates.sort_index(ascending=False)
    dates_rows = dataframe_to_records(
        dates, max_rows=limit, index_name="earnings_date", head=True
    )
    history_rows = dataframe_to_records(history, max_rows=limit, index_name="quarter")
    if not dates_rows and not history_rows:
        raise SymbolNotFoundError(symbol, reason=tickers.EQUITY_ONLY_REASON)

    return {
        "symbol": tickers.normalize(symbol),
        "earnings_dates": dates_rows,
        "earnings_history": history_rows,
    }


# Maps the output key to the Ticker method for the analyst-estimate tables,
# and whether that table counts earnings per share, so takes a methodology.
_ESTIMATE_GETTERS = {
    "earnings_estimate": ("get_earnings_estimate", True),
    "revenue_estimate": ("get_revenue_estimate", False),
    "eps_trend": ("get_eps_trend", True),
    "eps_revisions": ("get_eps_revisions", True),
    "growth_estimates": ("get_growth_estimates", False),
}


@cache.cached("estimates")
def get_estimates(symbol: str, *, methodology: str | None = None) -> dict[str, Any]:
    """Return forward analyst estimates for ``symbol``.

    Includes earnings and revenue estimates, EPS trend and revisions, and growth
    estimates (each a small table keyed by period). Equity-only: an ETF, fund or
    crypto symbol raises SymbolNotFoundError with
    ``tickers.EQUITY_ONLY_REASON``. ``methodology`` picks the EPS basis of
    the three EPS tables, ``gaap`` or ``normalized``, ``None`` for Yahoo's
    default. Revenue and growth have no such choice.
    """
    chosen = _methodology(methodology)
    ticker = tickers.get_ticker(symbol)
    out: dict[str, Any] = {"symbol": tickers.normalize(symbol)}
    have_data = False
    for key, (getter, per_share) in _ESTIMATE_GETTERS.items():
        with tickers.upstream(f"Failed to load estimates for {symbol!r}"):
            fetch = getattr(ticker, getter)
            df = fetch(methodology=chosen) if per_share else fetch()
        rows = dataframe_to_records(df, max_rows=_PERIOD_ROWS, index_name="period")
        if rows:
            have_data = True
        out[key] = rows

    if not have_data:
        raise SymbolNotFoundError(symbol, reason=tickers.EQUITY_ONLY_REASON)
    return out


# The most rating changes get_upgrades_downgrades returns.
CHANGES_MAX = 100


@cache.cached("upgrades_downgrades")
def get_upgrades_downgrades(symbol: str, *, limit: int = 50) -> dict[str, Any]:
    """Return recent analyst rating changes for ``symbol``.

    Each entry is a firm's upgrade/downgrade with the from/to grade and action,
    most recent first. Equity-only: an ETF, fund or crypto symbol raises
    SymbolNotFoundError with ``tickers.EQUITY_ONLY_REASON``.
    """
    limit = max(1, min(int(limit), CHANGES_MAX))
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
