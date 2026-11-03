"""Unit tests for fund and ETF profiles.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from yfinance._http import HTTPError
from yfinance.exceptions import YFDataException, YFRateLimitError

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    RateLimitError,
    SymbolNotFoundError,
    ToolError,
)
from benethos_yahoo_finance_mcp.yahoo import funds, tickers
from fakes import FakeTicker

# --- get_fund_data --------------------------------------------------------


def _fake_funds_data():
    import types

    top = pd.DataFrame(
        {"Name": ["NVIDIA Corp", "Apple Inc"], "Holding Percent": [0.078, 0.070]},
        index=pd.Index(["NVDA", "AAPL"], name="Symbol"),
    )
    return types.SimpleNamespace(
        description="An index ETF.",
        fund_overview={"categoryName": "Large Blend"},
        asset_classes={"stockPosition": 0.99},
        sector_weightings={"technology": 0.39},
        top_holdings=top,
        fund_operations=None,
    )


def test_get_fund_data_returns_profile(patch_ticker):
    patch_ticker(FakeTicker(funds_data=_fake_funds_data()))
    out = yahoo.get_fund_data("spy")
    assert out["symbol"] == "SPY"
    assert out["description"] == "An index ETF."
    assert out["fund_overview"] == {"categoryName": "Large Blend"}
    assert out["sector_weightings"] == {"technology": 0.39}
    assert out["top_holdings"][0]["symbol"] == "NVDA"


def test_get_fund_data_caps_holdings(patch_ticker):
    import types

    top = pd.DataFrame(
        {"Name": [f"H{i}" for i in range(100)]},
        index=pd.Index([f"S{i}" for i in range(100)], name="Symbol"),
    )
    fd = types.SimpleNamespace(
        description=None,
        fund_overview={},
        asset_classes={},
        sector_weightings={},
        top_holdings=top,
        fund_operations=None,
    )
    patch_ticker(FakeTicker(funds_data=fd))
    out = yahoo.get_fund_data("spy", limit=5)
    assert len(out["top_holdings"]) == 5


def test_get_fund_data_holds_its_ceiling(patch_ticker):
    top = pd.DataFrame(
        {"Name": [f"H{i}" for i in range(150)]},
        index=pd.Index([f"S{i}" for i in range(150)], name="Symbol"),
    )
    fd = SimpleNamespace(
        description=None,
        fund_overview={},
        asset_classes={},
        sector_weightings={},
        top_holdings=top,
        fund_operations=None,
    )
    patch_ticker(FakeTicker(funds_data=fd))
    out = yahoo.get_fund_data("spy", limit=10_000)
    assert len(out["top_holdings"]) == yahoo.HOLDINGS_MAX


def _operations(own, category, symbol="SPY"):
    """fund_operations as yfinance 1.8.0 builds it, the fund's column first."""
    rows = [
        "Annual Report Expense Ratio",
        "Annual Holdings Turnover",
        "Total Net Assets",
    ]
    return pd.DataFrame(
        {symbol: own, "Category Average": category}, index=pd.Index(rows)
    )


# SPY as Yahoo gave it on 2026-11-03, in its two scales.
_SPY_INFO = {
    "netExpenseRatio": 0.0945,
    "totalAssets": 809216114688,
    "ytdReturn": 12.67538,
    "threeYearAverageReturn": 0.2328269,
    "fiveYearAverageReturn": 0.11966,
}


def _fund(operations, info):
    fd = _fake_funds_data()
    fd.fund_operations = operations
    return FakeTicker(funds_data=fd, info=info)


def test_get_fund_data_key_figures_are_fractions(patch_ticker):
    operations = _operations(
        [0.000945, 0.03, 542460.75], [0.0072176997, 0.9461, 542460.75]
    )
    patch_ticker(_fund(operations, _SPY_INFO))
    assert yahoo.get_fund_data("spy")["key_figures"] == {
        "expense_ratio": 0.000945,
        "category_expense_ratio": 0.007218,
        "holdings_turnover": 0.03,
        "total_assets": 809216114688.0,
        "ytd_return": 0.126754,
        "three_year_average_return": 0.232827,
        "five_year_average_return": 0.11966,
    }


def test_get_fund_data_key_figures_leave_out_what_yahoo_lacks(patch_ticker):
    """EUNL.DE on 2026-11-03: costs and turnover, no size, no returns."""
    operations = _operations(
        [0.002, 0.113299996, 308088.2], [None, None, 308088.2], symbol="EUNL.DE"
    )
    patch_ticker(_fund(operations, {"netExpenseRatio": 0.2}))
    assert yahoo.get_fund_data("eunl.de")["key_figures"] == {
        "expense_ratio": 0.002,
        "holdings_turnover": 0.1133,
    }


def test_get_fund_data_expense_ratio_falls_back_to_info_in_percent(patch_ticker):
    operations = _operations([float("nan"), 0.07, 1.0], [None, None, 1.0])
    patch_ticker(_fund(operations, {"netExpenseRatio": 0.19}))
    assert yahoo.get_fund_data("vwce.de")["key_figures"]["expense_ratio"] == 0.0019


def test_get_fund_data_without_operations_still_answers(patch_ticker):
    patch_ticker(_fund(None, {}))
    assert yahoo.get_fund_data("spy")["key_figures"] == {}


def test_get_fund_data_non_fund_raises_not_found(patch_ticker):
    patch_ticker(FakeTicker(funds_data=YFDataException("No Fund data found.")))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_fund_data("aapl")


def test_get_fund_data_unknown_symbol_raises_not_found(patch_ticker):
    """The fund route answers an unknown symbol with a 404, and it reached Yahoo."""
    error = HTTPError("HTTP Error 404: ", response=SimpleNamespace(status_code=404))
    patch_ticker(FakeTicker(funds_data=error))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_fund_data("NOSUCHFUND")
    assert tickers.last_answer() == (True, 0)


def test_get_fund_data_server_error_is_not_a_missing_symbol(patch_ticker):
    error = HTTPError("HTTP Error 503: ", response=SimpleNamespace(status_code=503))
    patch_ticker(FakeTicker(funds_data=error))
    with pytest.raises(ToolError, match="Yahoo answered HTTP 503") as info:
        yahoo.get_fund_data("SPY")
    assert not isinstance(info.value, SymbolNotFoundError)


def test_get_fund_data_with_nothing_in_it_raises_not_found(patch_ticker):
    """yfinance swallows a parse failure and leaves every attribute None.

    A hollow profile would be kept in the cache for a day.
    """
    hollow = SimpleNamespace(
        description=None,
        fund_overview=None,
        asset_classes=None,
        sector_weightings=None,
        top_holdings=None,
        fund_operations=None,
    )
    patch_ticker(FakeTicker(funds_data=hollow, info={"totalAssets": 1.0}))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_fund_data("SPY")


def test_get_fund_data_rate_limit(patch_ticker):
    patch_ticker(FakeTicker(funds_data=YFRateLimitError()))
    with pytest.raises(RateLimitError):
        yahoo.get_fund_data("spy")


def test_get_fund_data_upstream_error(patch_ticker):
    patch_ticker(FakeTicker(funds_data=RuntimeError("boom")))
    with pytest.raises(ToolError):
        yahoo.get_fund_data("spy")


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_a_figure_that_is_not_finite_is_left_out(value):
    """Infinity is not JSON, and the rule in formatting holds here too."""
    assert funds._fraction(value) is None
