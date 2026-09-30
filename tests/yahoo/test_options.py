"""Unit tests for option chains.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fakes import FakeTicker

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import (
    SymbolNotFoundError,
    ToolError,
)

# --- get_options ----------------------------------------------------------


def test_get_options_lists_expirations(patch_ticker):
    patch_ticker(FakeTicker(options=("2024-01-19", "2024-02-16")))
    out = yahoo.get_options("aapl")
    assert out["expirations"] == ["2024-01-19", "2024-02-16"]


def test_get_options_unknown_expiration_raises(patch_ticker):
    patch_ticker(FakeTicker(options=("2024-01-19",)))
    with pytest.raises(ToolError):
        yahoo.get_options("aapl", expiration="2030-01-01")


def test_get_options_no_options_raises(patch_ticker):
    patch_ticker(FakeTicker(options=()))
    with pytest.raises(SymbolNotFoundError):
        yahoo.get_options("aapl")


def test_get_options_no_options_explains_why(patch_ticker):
    """Yahoo lists chains for US instruments only, so empty is the norm abroad.

    Probed live: SAP.DE, NESN.SW and 7203.T are all valid and all come back
    without expirations, so the plain not-found message was misleading for the
    entire non-US universe.
    """
    patch_ticker(FakeTicker(options=()))
    with pytest.raises(SymbolNotFoundError) as excinfo:
        yahoo.get_options("7203.t")
    message = str(excinfo.value)
    assert "US-listed" in message
    assert "does not show that the symbol is wrong" in message
    assert excinfo.value.reason is not None


def test_symbol_not_found_without_reason_keeps_the_search_advice(patch_ticker):
    """A genuinely unknown symbol must still be sent to `search`."""
    patch_ticker(FakeTicker(shares_full=None))
    with pytest.raises(SymbolNotFoundError) as excinfo:
        yahoo.get_shares("xyzq123")
    assert "Use the 'search' tool to look it up" in str(excinfo.value)
    assert excinfo.value.reason is None


def test_get_options_returns_chain(patch_ticker):
    import types

    calls = pd.DataFrame({"strike": [100.0]})
    puts = pd.DataFrame({"strike": [90.0]})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19")
    assert out["calls"][0]["strike"] == 100.0
    assert out["puts"][0]["strike"] == 90.0


def test_get_options_caps_rows(patch_ticker):
    import types

    calls = pd.DataFrame({"strike": list(range(100))})
    puts = pd.DataFrame({"strike": list(range(100))})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19", limit=5)
    assert len(out["calls"]) == 5
    assert len(out["puts"]) == 5
    assert out["truncated"] is True


def test_get_options_keeps_the_strikes_around_the_money(patch_ticker):
    """A wide chain keeps the strikes near the price, not the highest ones.

    Price 50: calls below it and puts above it are in the money.
    """
    import types

    strikes = [float(s) for s in range(100)]
    calls = pd.DataFrame({"strike": strikes, "inTheMoney": [s < 50 for s in strikes]})
    puts = pd.DataFrame({"strike": strikes, "inTheMoney": [s > 50 for s in strikes]})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19", limit=6)
    assert [r["strike"] for r in out["calls"]] == [47.0, 48.0, 49.0, 50.0, 51.0, 52.0]
    assert [r["strike"] for r in out["puts"]] == [48.0, 49.0, 50.0, 51.0, 52.0, 53.0]


def test_get_options_window_stays_inside_the_chain(patch_ticker):
    """Price above every strike: the window is the top of the chain, full size."""
    import types

    strikes = [float(s) for s in range(20)]
    calls = pd.DataFrame({"strike": strikes, "inTheMoney": [True] * 20})
    puts = pd.DataFrame({"strike": strikes, "inTheMoney": [False] * 20})
    chain = types.SimpleNamespace(calls=calls, puts=puts)
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19", limit=4)
    assert [r["strike"] for r in out["calls"]] == [16.0, 17.0, 18.0, 19.0]
    assert [r["strike"] for r in out["puts"]] == [16.0, 17.0, 18.0, 19.0]


def test_get_options_rows_are_keyed_by_contract(patch_ticker):
    """No positional "index" column, the contract symbol names the row."""
    import types

    calls = pd.DataFrame({"contractSymbol": ["AAPL1C100"], "strike": [100.0]})
    chain = types.SimpleNamespace(calls=calls, puts=pd.DataFrame())
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19")
    assert out["calls"] == [{"contractSymbol": "AAPL1C100", "strike": 100.0}]


def test_get_options_short_chain_is_not_truncated(patch_ticker):
    import types

    chain = types.SimpleNamespace(
        calls=pd.DataFrame({"strike": [1.0, 2.0]}), puts=pd.DataFrame()
    )
    patch_ticker(FakeTicker(options=("2024-01-19",), option_chain=chain))
    out = yahoo.get_options("aapl", expiration="2024-01-19")
    assert out["truncated"] is False
    assert out["puts"] == []
