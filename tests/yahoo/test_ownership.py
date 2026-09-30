"""Unit tests for holders, insider activity and SEC filings.

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

# --- get_holders ----------------------------------------------------------


def test_get_holders_combines_lists(patch_ticker):
    major = pd.DataFrame(
        {"Value": [0.016, 0.65]},
        index=pd.Index(["insidersPercentHeld", "institutionsPercentHeld"]),
    )
    institutional = pd.DataFrame({"Holder": ["Blackrock"], "Shares": [100]})
    mutualfund = pd.DataFrame({"Holder": ["Vanguard 500"], "Shares": [50]})
    patch_ticker(
        FakeTicker(
            major_holders=major,
            institutional_holders=institutional,
            mutualfund_holders=mutualfund,
        )
    )
    out = yahoo.get_holders("aapl")
    assert out["symbol"] == "AAPL"
    assert out["major_holders"][0]["metric"] == "insidersPercentHeld"
    assert out["institutional_holders"][0]["Holder"] == "Blackrock"
    assert out["mutualfund_holders"][0]["Holder"] == "Vanguard 500"


def test_get_holders_caps_rows(patch_ticker):
    institutional = pd.DataFrame({"Holder": [f"H{i}" for i in range(100)]})
    patch_ticker(
        FakeTicker(
            major_holders=None,
            institutional_holders=institutional,
            mutualfund_holders=None,
        )
    )
    out = yahoo.get_holders("aapl", limit=5)
    assert len(out["institutional_holders"]) == 5


def test_get_holders_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            major_holders=None, institutional_holders=None, mutualfund_holders=None
        )
    )
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_holders("nope")


# --- get_insider_activity -------------------------------------------------


def test_get_insider_activity_combines_tables(patch_ticker):
    transactions = pd.DataFrame({"Insider": ["BORDERS BEN"], "Shares": [116]})
    purchases = pd.DataFrame(
        {"Insider Purchases Last 6m": ["Purchases"], "Shares": [10]}
    )
    roster = pd.DataFrame(
        {"Name": ["COOK TIMOTHY D"], "Shares Owned Directly": [3280420]}
    )
    patch_ticker(
        FakeTicker(
            insider_transactions=transactions,
            insider_purchases=purchases,
            insider_roster_holders=roster,
        )
    )
    out = yahoo.get_insider_activity("aapl")
    assert out["transactions"][0]["Insider"] == "BORDERS BEN"
    assert out["purchases_summary"][0]["Shares"] == 10
    assert out["roster"][0]["Name"] == "COOK TIMOTHY D"


def test_get_insider_activity_caps_rows(patch_ticker):
    transactions = pd.DataFrame({"Insider": [f"I{i}" for i in range(100)]})
    patch_ticker(
        FakeTicker(
            insider_transactions=transactions,
            insider_purchases=None,
            insider_roster_holders=None,
        )
    )
    out = yahoo.get_insider_activity("aapl", limit=5)
    assert len(out["transactions"]) == 5


def test_get_insider_activity_empty_raises(patch_ticker):
    patch_ticker(
        FakeTicker(
            insider_transactions=None,
            insider_purchases=None,
            insider_roster_holders=None,
        )
    )
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_insider_activity("nope")


# --- get_sec_filings ------------------------------------------------------


def test_get_sec_filings_curates_fields(patch_ticker):
    import datetime

    filings = [
        {
            "date": datetime.date(2026, 5, 1),
            "epochDate": 1777593600,
            "type": "10-Q",
            "title": "Periodic Financial Reports",
            "edgarUrl": "https://example.com/10q",
            "exhibits": {"10-Q": "https://example.com/ex"},
            "maxAge": 1,
        }
    ]
    patch_ticker(FakeTicker(sec_filings=filings))
    out = yahoo.get_sec_filings("aapl")
    assert out["count"] == 1
    item = out["filings"][0]
    assert item["type"] == "10-Q"
    assert item["date"] == "2026-05-01"
    assert item["url"] == "https://example.com/10q"
    assert item["exhibits"] == {"10-Q": "https://example.com/ex"}
    # Noisy fields are dropped.
    assert "epochDate" not in item
    assert "maxAge" not in item


def test_get_sec_filings_caps_rows(patch_ticker):
    filings = [{"type": "8-K", "title": str(i)} for i in range(50)]
    patch_ticker(FakeTicker(sec_filings=filings))
    out = yahoo.get_sec_filings("aapl", limit=5)
    assert out["count"] == 5


def test_get_sec_filings_empty_raises(patch_ticker):
    patch_ticker(FakeTicker(sec_filings=[]))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_sec_filings("nope")


def test_get_sec_filings_empty_explains_why(patch_ticker):
    """Only SEC registrants file, so empty says nothing about the symbol.

    SAP.DE is a real, tradeable stock with no SEC filings by construction. The
    error must not tell the caller to go and look the symbol up.
    """
    patch_ticker(FakeTicker(sec_filings=[]))
    with pytest.raises(SymbolNotFoundError) as excinfo:
        yahoo.get_sec_filings("sap.de")
    message = str(excinfo.value)
    assert "U.S. SEC" in message
    assert "does not show that the symbol is wrong" in message
    assert excinfo.value.reason is not None
