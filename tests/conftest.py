"""Shared test fixtures."""

from __future__ import annotations

import logging

import pytest

from benethos_yahoo_finance_mcp import cache
from benethos_yahoo_finance_mcp.settings import Settings


@pytest.fixture(autouse=True)
def _cache_disabled_by_default(monkeypatch):
    """Keep the result cache off for tests unless a test enables it explicitly.

    Sets ``YF_MCP_CACHE=0`` (so CLI defaults resolve to disabled) and resets the
    cache module state after each test so cached results never leak between tests.
    """
    monkeypatch.setenv("YF_MCP_CACHE", "0")
    yield
    cache.configure(Settings())


# Loggers whose level cli.main and logbook.output.configure set. Restored after
# every test, so a level one test chose is not what the next one starts with.
_LOGGERS = ("", "benethos_yahoo_finance_mcp", "uvicorn.access", "uvicorn.error")


@pytest.fixture(autouse=True)
def _logging_levels_restored():
    saved = {name: logging.getLogger(name).level for name in _LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)
