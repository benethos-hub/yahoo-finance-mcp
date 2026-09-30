"""Unit tests for sectors, industries and markets.

yfinance is mocked completely, nothing here reaches the network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.errors import RateLimitError, ToolError
from benethos_yahoo_finance_mcp.yahoo import tickers

# --- get_sector -----------------------------------------------------------


def _fake_sector(name="Technology", n_companies=2):
    import types

    top = pd.DataFrame(
        {
            "name": [f"C{i}" for i in range(n_companies)],
            "rating": ["Buy"] * n_companies,
            "market weight": [0.1] * n_companies,
        },
        index=pd.Index([f"S{i}" for i in range(n_companies)], name="symbol"),
    )
    industries = pd.DataFrame(
        {"name": ["Semiconductors"], "symbol": ["^X"], "market weight": [0.4]},
        index=pd.Index(["semiconductors"], name="key"),
    )
    return types.SimpleNamespace(
        name=name,
        symbol="^YH311",
        overview={"companies_count": 842},
        top_companies=top,
        top_etfs={"VGT": "Vanguard Information Tech ETF"},
        top_mutual_funds={"VITAX": "Fidelity Select"},
        industries=industries,
    )


def test_get_sector_returns_overview(monkeypatch):
    monkeypatch.setattr(tickers.yf, "Sector", lambda key: _fake_sector())
    out = yahoo.get_sector("technology")
    assert out["key"] == "technology"
    assert out["name"] == "Technology"
    assert out["index_symbol"] == "^YH311"
    assert out["top_etfs"] == {"VGT": "Vanguard Information Tech ETF"}
    assert out["industries"][0]["key"] == "semiconductors"


def test_get_sector_caps_top_companies(monkeypatch):
    monkeypatch.setattr(tickers.yf, "Sector", lambda key: _fake_sector(n_companies=100))
    out = yahoo.get_sector("technology", limit=5)
    assert len(out["top_companies"]) == 5


def test_get_sector_unknown_key_raises(monkeypatch):
    import types

    none_sector = types.SimpleNamespace(
        name=None,
        symbol=None,
        overview=None,
        top_companies=None,
        top_etfs=None,
        top_mutual_funds=None,
        industries=None,
    )
    monkeypatch.setattr(tickers.yf, "Sector", lambda key: none_sector)
    with pytest.raises(ToolError):
        yahoo.get_sector("not-a-sector")


def test_get_sector_empty_key_raises():
    with pytest.raises(ToolError):
        yahoo.get_sector("   ")


def test_get_sector_valid_key_no_data_is_not_called_a_symbol(monkeypatch):
    import types

    none_sector = types.SimpleNamespace(
        name=None,
        symbol=None,
        overview=None,
        top_companies=None,
        top_etfs=None,
        top_mutual_funds=None,
        industries=None,
    )
    # A valid key with no data is neither an unknown key nor an unknown symbol.
    monkeypatch.setattr(tickers.yf, "Sector", lambda key: none_sector)
    with pytest.raises(ToolError, match="Yahoo returned nothing for the sector"):
        yahoo.get_sector("technology")


def test_get_sector_upstream_error(monkeypatch):
    def boom(key):
        raise RuntimeError("network down")

    monkeypatch.setattr(tickers.yf, "Sector", boom)
    with pytest.raises(ToolError):
        yahoo.get_sector("technology")


def test_sector_keys_derived_from_const():
    # Keys come from yfinance's constant (or the fallback); both include these.
    assert "technology" in yahoo.SECTOR_KEYS
    assert "healthcare" in yahoo.SECTOR_KEYS
    assert len(yahoo.SECTOR_KEYS) >= 11


# --- get_industry ---------------------------------------------------------


def _fake_industry(name="Semiconductors", n_companies=2):
    import types

    top = pd.DataFrame(
        {"name": [f"C{i}" for i in range(n_companies)]},
        index=pd.Index([f"S{i}" for i in range(n_companies)], name="symbol"),
    )
    performing = pd.DataFrame(
        {"name": ["NVDA Corp"], "ytd return": [0.5]},
        index=pd.Index(["NVDA"], name="symbol"),
    )
    growth = pd.DataFrame(
        {"name": ["AMD Inc"], "growth estimate": [0.3]},
        index=pd.Index(["AMD"], name="symbol"),
    )
    return types.SimpleNamespace(
        name=name,
        symbol="^YH31130020",
        sector_key="technology",
        sector_name="Technology",
        overview={"companies_count": 49},
        top_companies=top,
        top_performing_companies=performing,
        top_growth_companies=growth,
    )


def test_get_industry_returns_overview(monkeypatch):
    monkeypatch.setattr(tickers.yf, "Industry", lambda key: _fake_industry())
    out = yahoo.get_industry("semiconductors")
    assert out["name"] == "Semiconductors"
    assert out["sector_key"] == "technology"
    assert out["top_performing_companies"][0]["symbol"] == "NVDA"
    assert out["top_growth_companies"][0]["symbol"] == "AMD"


def test_get_industry_caps_top_companies(monkeypatch):
    monkeypatch.setattr(
        tickers.yf, "Industry", lambda key: _fake_industry(n_companies=100)
    )
    out = yahoo.get_industry("semiconductors", limit=5)
    assert len(out["top_companies"]) == 5


def test_get_industry_unknown_key_raises(monkeypatch):
    import types

    none_industry = types.SimpleNamespace(
        name=None,
        symbol=None,
        sector_key=None,
        sector_name=None,
        overview=None,
        top_companies=None,
        top_performing_companies=None,
        top_growth_companies=None,
    )
    monkeypatch.setattr(tickers.yf, "Industry", lambda key: none_industry)
    with pytest.raises(ToolError):
        yahoo.get_industry("not-an-industry")


def test_get_industry_empty_key_raises():
    with pytest.raises(ToolError):
        yahoo.get_industry("")


def test_get_industry_valid_key_no_data_is_not_called_a_symbol(monkeypatch):
    import types

    none_industry = types.SimpleNamespace(
        name=None,
        symbol=None,
        sector_key=None,
        sector_name=None,
        overview=None,
        top_companies=None,
        top_performing_companies=None,
        top_growth_companies=None,
    )
    monkeypatch.setattr(tickers.yf, "Industry", lambda key: none_industry)
    with pytest.raises(ToolError, match="Yahoo returned nothing for the industry"):
        yahoo.get_industry("semiconductors")


def test_get_industry_upstream_error(monkeypatch):
    def boom(key):
        raise RuntimeError("network down")

    monkeypatch.setattr(tickers.yf, "Industry", boom)
    with pytest.raises(ToolError):
        yahoo.get_industry("semiconductors")


# --- get_market -------------------------------------------------------------


def _fake_market(status=None, summary=None, status_raises=False):
    import types

    class _M:
        @property
        def status(self):
            if status_raises:
                # Mirrors upstream: every key other than "US" raises here.
                raise AttributeError("'NoneType' object has no attribute 'get'")
            return status

        @property
        def summary(self):
            return summary

    _ = types
    return _M()


_STATUS_US = {
    "id": "us",
    "name": "U.S. markets",
    "status": "closed",
    "open": "2026-08-17 13:30:00+00:00",
    "close": "2026-08-17 20:00:00+00:00",
    "tz": "EDT",
    "timezone": {"short": "EDT"},  # noise, must be dropped
}

_SUMMARY = {
    "SNP": {
        "symbol": "^GSPC",
        "shortName": "S&P 500",
        "fullExchangeName": "SNP",
        "marketState": "CLOSED",
        "regularMarketPrice": 7785.76,
        "regularMarketPreviousClose": 7798.99,
        "regularMarketChange": -13.23,
        "regularMarketChangePercent": -0.17,
        "language": "en-US",  # noise, must be dropped
        "triggerable": False,  # noise, must be dropped
    }
}


def test_get_market_returns_status_and_indices(monkeypatch):
    monkeypatch.setattr(
        tickers.yf, "Market", lambda key: _fake_market(_STATUS_US, _SUMMARY)
    )
    out = yahoo.get_market("US")
    assert out["key"] == "US"
    assert out["status"]["status"] == "closed"
    assert out["status"]["name"] == "U.S. markets"
    assert "timezone" not in out["status"], "noisy nested field must be dropped"
    assert out["count"] == 1
    index = out["indices"][0]
    assert index["symbol"] == "^GSPC"
    assert index["regularMarketPrice"] == 7785.76
    assert "language" not in index and "triggerable" not in index


def test_get_market_lowercase_key_is_accepted(monkeypatch):
    monkeypatch.setattr(
        tickers.yf, "Market", lambda key: _fake_market(_STATUS_US, _SUMMARY)
    )
    assert yahoo.get_market("us")["key"] == "US"


def test_get_market_status_unavailable_is_not_an_error(monkeypatch):
    """Only "US" serves a status upstream. Everything else must still work."""
    monkeypatch.setattr(
        tickers.yf,
        "Market",
        lambda key: _fake_market(None, _SUMMARY, status_raises=True),
    )
    out = yahoo.get_market("EUROPE")
    assert out["status"] is None
    assert out["count"] == 1


def test_get_market_rate_limit_propagates(monkeypatch):
    class _M:
        @property
        def status(self):
            raise YFRateLimitError()

        @property
        def summary(self):
            return _SUMMARY

    monkeypatch.setattr(tickers.yf, "Market", lambda key: _M())
    with pytest.raises(RateLimitError):
        yahoo.get_market("US")


def test_get_market_unknown_key_raises():
    with pytest.raises(ToolError) as exc:
        yahoo.get_market("MARS")
    assert "MARS" in str(exc.value)
    assert "US" in str(exc.value), "the error must list the valid keys"


def test_get_market_empty_key_raises():
    with pytest.raises(ToolError):
        yahoo.get_market("   ")


def test_get_market_no_data_is_not_called_a_symbol(monkeypatch):
    monkeypatch.setattr(
        tickers.yf, "Market", lambda key: _fake_market(None, {}, status_raises=True)
    )
    with pytest.raises(ToolError, match="Yahoo returned nothing for the market"):
        yahoo.get_market("US")


def test_get_market_summary_error_is_wrapped(monkeypatch):
    class _M:
        @property
        def status(self):
            return _STATUS_US

        @property
        def summary(self):
            raise RuntimeError("upstream broke")

    monkeypatch.setattr(tickers.yf, "Market", lambda key: _M())
    with pytest.raises(ToolError) as exc:
        yahoo.get_market("US")
    assert "market summary" in str(exc.value)


def test_get_market_status_none_becomes_null_not_empty_dict(monkeypatch):
    """Upstream returns None for some keys instead of raising.

    Both paths must produce the same answer, otherwise callers see an empty dict
    for one market and null for another.
    """
    monkeypatch.setattr(tickers.yf, "Market", lambda key: _fake_market(None, _SUMMARY))
    out = yahoo.get_market("EUROPE")
    assert out["status"] is None
    assert out["count"] == 1
