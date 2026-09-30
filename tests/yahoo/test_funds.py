"""Unit tests for fund and ETF profiles.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fakes import FakeTicker
from yfinance.exceptions import YFDataException, YFRateLimitError

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    RateLimitError,
    SymbolNotFoundError,
    ToolError,
)

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
    )
    patch_ticker(FakeTicker(funds_data=fd))
    out = yahoo.get_fund_data("spy", limit=5)
    assert len(out["top_holdings"]) == 5


def test_get_fund_data_non_fund_raises_not_found(patch_ticker):
    patch_ticker(FakeTicker(funds_data=YFDataException("No Fund data found.")))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_fund_data("aapl")


def test_get_fund_data_rate_limit(patch_ticker):
    patch_ticker(FakeTicker(funds_data=YFRateLimitError()))
    with pytest.raises(RateLimitError):
        yahoo.get_fund_data("spy")


def test_get_fund_data_upstream_error(patch_ticker):
    patch_ticker(FakeTicker(funds_data=RuntimeError("boom")))
    with pytest.raises(ToolError):
        yahoo.get_fund_data("spy")
