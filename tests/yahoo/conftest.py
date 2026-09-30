"""Fixtures for the yahoo package tests, which mock yfinance completely."""

from __future__ import annotations

import pytest
from fakes import FakeTicker

from benethos_yahoo_finance_mcp.yahoo import tickers


@pytest.fixture
def patch_ticker(monkeypatch):
    """Patch ``tickers.get_ticker`` to return a supplied FakeTicker."""

    def _install(ticker: FakeTicker):
        monkeypatch.setattr(tickers, "get_ticker", lambda symbol: ticker)
        return ticker

    return _install
