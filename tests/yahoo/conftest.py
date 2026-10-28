"""Fixtures for the yahoo package tests, which mock yfinance completely."""

from __future__ import annotations

import pytest

from benethos_yahoo_finance_mcp.yahoo import tickers
from fakes import FakeSearch


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
