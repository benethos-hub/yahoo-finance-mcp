"""Unit tests for recommendations, earnings, estimates and rating changes.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    SymbolNotFoundError,
    ToolError,
)
from fakes import FakeTicker

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


@pytest.mark.parametrize("newest_first", [True, False])
def test_get_earnings_keeps_the_newest_of_the_page(patch_ticker, newest_first):
    """yfinance rounds limit up to a page of 25, 50 or 100 and returns all of it.

    Yahoo sends the page newest first. Keeping the tail gave the oldest dates
    and lost the next one. The other order must not bring that back.
    """
    index = pd.date_range(
        "2020-01-01", periods=25, freq="QS", tz="America/New_York", name="Earnings Date"
    )
    dates = pd.DataFrame({"EPS Estimate": list(range(25))}, index=index)
    if newest_first:
        dates = dates.iloc[::-1]
    patch_ticker(FakeTicker(earnings_dates=dates, earnings_history=None))
    rows = yahoo.get_earnings("aapl", limit=12)["earnings_dates"]
    assert [row["EPS Estimate"] for row in rows] == list(range(24, 12, -1))


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


def _estimates_ticker():
    est = pd.DataFrame({"avg": [2.0]}, index=pd.Index(["0y"], name="period"))
    return FakeTicker(
        earnings_estimate=est,
        revenue_estimate=None,
        eps_trend=None,
        eps_revisions=None,
        growth_estimates=None,
    )


def test_get_estimates_asks_for_yahoos_default_basis_unless_told(patch_ticker):
    ticker = patch_ticker(_estimates_ticker())
    yahoo.get_estimates("aapl")
    assert ticker.eps_requests == [
        ("earnings_estimate", None),
        ("eps_trend", None),
        ("eps_revisions", None),
    ]


def test_get_estimates_asks_every_eps_table_for_the_chosen_basis(patch_ticker):
    """Revenue and growth have no basis to choose and are asked as before."""
    ticker = patch_ticker(_estimates_ticker())
    yahoo.get_estimates("aapl", methodology=" GAAP ")
    assert ticker.eps_requests == [
        ("earnings_estimate", "gaap"),
        ("eps_trend", "gaap"),
        ("eps_revisions", "gaap"),
    ]


def test_get_estimates_refuses_an_unknown_basis_before_asking_yahoo(patch_ticker):
    ticker = patch_ticker(_estimates_ticker())
    with pytest.raises(ToolError, match="gaap, normalized"):
        yahoo.get_estimates("aapl", methodology="ifrs")
    assert "eps_requests" not in vars(ticker)


def test_get_estimates_treats_a_blank_basis_as_the_default(patch_ticker):
    ticker = patch_ticker(_estimates_ticker())
    yahoo.get_estimates("aapl", methodology="  ")
    assert ticker.eps_requests[0] == ("earnings_estimate", None)


def test_get_earnings_asks_the_history_for_the_chosen_basis(patch_ticker):
    history = pd.DataFrame(
        {"epsActual": [1.6]}, index=pd.Index(["1Q2024"], name="quarter")
    )
    ticker = patch_ticker(FakeTicker(earnings_dates=None, earnings_history=history))
    yahoo.get_earnings("aapl", methodology="normalized")
    assert ticker.eps_requests == [("earnings_history", "normalized")]


def test_get_earnings_refuses_an_unknown_basis(patch_ticker):
    patch_ticker(FakeTicker(earnings_dates=None, earnings_history=None))
    with pytest.raises(ToolError, match="Invalid methodology 'ifrs'"):
        yahoo.get_earnings("aapl", methodology="ifrs")


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
