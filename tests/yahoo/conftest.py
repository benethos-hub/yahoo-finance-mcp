"""Fixtures for the yahoo package tests, which mock yfinance completely."""

from __future__ import annotations

import pytest
from fakes import FakeSearch, FakeTicker

from benethos_yahoo_finance_mcp.yahoo import tickers


@pytest.fixture
def patch_ticker(monkeypatch):
    """Patch ``tickers.get_ticker`` to return a supplied FakeTicker.

    Like ``yf.Ticker``, it knows its symbol upper-cased as ``ticker``, unless
    the test gave it another one (the symbol an ISIN resolves to, say).
    """

    def _install(ticker: FakeTicker):
        def lookup(symbol):
            ticker._attrs.setdefault("ticker", tickers.normalize(symbol))
            return ticker

        monkeypatch.setattr(tickers, "get_ticker", lookup)
        return ticker

    return _install


@pytest.fixture(autouse=True)
def patch_search(monkeypatch):
    """Patch ``yf.Search`` with a FakeSearch serving no news, in every test.

    get_news falls back to the search when the ticker has no articles, so a
    test with empty news would otherwise ask Yahoo. A test that patches
    ``Search`` itself replaces this one.
    """
    search = FakeSearch()
    monkeypatch.setattr(tickers.yf, "Search", search)
    return search
