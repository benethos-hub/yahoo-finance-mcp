"""Unit tests for recommendations, earnings, estimates and rating changes.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fakes import FakeTicker

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    SymbolNotFoundError,
)

# --- get_recommendations --------------------------------------------------


def test_get_recommendations_combines_trend_and_targets(patch_ticker):
    recs = pd.DataFrame({"period": ["0m"], "buy": [10]})
    patch_ticker(
        FakeTicker(
            recommendations=recs,
            analyst_price_targets={"mean": 200.0},
        )
    )
    out = yahoo.get_recommendations("aapl")
    assert out["price_targets"] == {"mean": 200.0}
    assert out["recommendation_trend"][0]["buy"] == 10


def test_get_recommendations_rows_are_keyed_by_period(patch_ticker):
    """No positional "index" column, the period names the row."""
    recs = pd.DataFrame({"period": ["0m", "-1m"], "buy": [10, 9]})
    patch_ticker(FakeTicker(recommendations=recs, analyst_price_targets=None))
    out = yahoo.get_recommendations("aapl")
    assert out["recommendation_trend"] == [
        {"period": "0m", "buy": 10},
        {"period": "-1m", "buy": 9},
    ]


def test_get_recommendations_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(recommendations=None, analyst_price_targets=None))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_recommendations("nope")


# --- get_earnings ---------------------------------------------------------


def test_get_earnings_combines_dates_and_history(patch_ticker):
    dates = pd.DataFrame(
        {"EPS Estimate": [1.5], "Reported EPS": [1.6]},
        index=pd.DatetimeIndex(["2024-01-25"], name="Earnings Date"),
    )
    history = pd.DataFrame(
        {"epsActual": [1.6]},
        index=pd.Index(["1Q2024"], name="quarter"),
    )
    ticker = patch_ticker(FakeTicker(earnings_dates=dates, earnings_history=history))
    out = yahoo.get_earnings("aapl", limit=8)
    assert out["symbol"] == "AAPL"
    assert out["earnings_dates"][0]["EPS Estimate"] == 1.5
    assert out["earnings_history"][0]["epsActual"] == 1.6
    assert ticker.earnings_dates_kwargs == {"limit": 8}


def test_get_earnings_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(earnings_dates=None, earnings_history=None))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_earnings("nope")


# --- get_estimates --------------------------------------------------------


def test_get_estimates_returns_tables(patch_ticker):
    est = pd.DataFrame({"avg": [2.0]}, index=pd.Index(["0q"], name="period"))
    patch_ticker(
        FakeTicker(
            earnings_estimate=est,
            revenue_estimate=None,
            eps_trend=None,
            eps_revisions=None,
            growth_estimates=None,
        )
    )
    out = yahoo.get_estimates("aapl")
    assert out["earnings_estimate"][0]["avg"] == 2.0
    assert out["revenue_estimate"] == []


def test_get_estimates_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            earnings_estimate=None,
            revenue_estimate=None,
            eps_trend=None,
            eps_revisions=None,
            growth_estimates=None,
        )
    )
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_estimates("nope")


# --- get_upgrades_downgrades ----------------------------------------------


def test_get_upgrades_downgrades_sorts_newest_first_and_caps(patch_ticker):
    idx = pd.DatetimeIndex(["2024-01-01", "2024-03-01", "2024-02-01"], name="GradeDate")
    df = pd.DataFrame(
        {"Firm": ["A", "B", "C"], "ToGrade": ["Buy", "Hold", "Sell"]}, index=idx
    )
    patch_ticker(FakeTicker(upgrades_downgrades=df))
    out = yahoo.get_upgrades_downgrades("aapl", limit=2)
    assert len(out["changes"]) == 2
    # Newest first: 2024-03-01 (B) then 2024-02-01 (C).
    assert out["changes"][0]["Firm"] == "B"
    assert out["changes"][1]["Firm"] == "C"


def test_get_upgrades_downgrades_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(upgrades_downgrades=pd.DataFrame()))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_upgrades_downgrades("nope")
