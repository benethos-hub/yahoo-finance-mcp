"""Shared test fixtures."""

from __future__ import annotations

import pytest

from yahoo_finance_mcp import cache


@pytest.fixture(autouse=True)
def _cache_disabled_by_default(monkeypatch):
    """Keep the result cache off for tests unless a test enables it explicitly.

    Sets ``YF_MCP_CACHE=0`` (so CLI defaults resolve to disabled) and resets the
    cache module state after each test so cached results never leak between tests.
    """
    monkeypatch.setenv("YF_MCP_CACHE", "0")
    yield
    cache.configure(enabled=False)
