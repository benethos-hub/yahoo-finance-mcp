"""Unit tests for the persistent result cache."""

from __future__ import annotations

import time

import pytest

from yahoo_finance_mcp import cache


@pytest.fixture
def enabled_cache(tmp_path):
    """Enable the cache against a temp dir; disable (and close) on teardown.

    Depends on ``tmp_path`` so its teardown (closing the SQLite connection)
    runs before ``tmp_path`` is removed.
    """
    cache.configure(enabled=True, cache_dir=str(tmp_path))
    yield tmp_path
    cache.configure(enabled=False)


# --- ResultCache ----------------------------------------------------------


def test_result_cache_set_get_roundtrip(tmp_path):
    rc = cache.ResultCache(tmp_path / "c.sqlite")
    try:
        rc.set("k", {"v": 1}, ttl=60)
        hit, value = rc.get("k")
        assert hit is True
        assert value == {"v": 1}
    finally:
        rc.close()


def test_result_cache_miss(tmp_path):
    rc = cache.ResultCache(tmp_path / "c.sqlite")
    try:
        assert rc.get("absent") == (False, None)
    finally:
        rc.close()


def test_result_cache_expiry(tmp_path):
    rc = cache.ResultCache(tmp_path / "c.sqlite")
    try:
        rc.set("k", "x", ttl=0.05)
        time.sleep(0.07)
        assert rc.get("k") == (False, None)
    finally:
        rc.close()


def test_result_cache_zero_ttl_not_stored(tmp_path):
    rc = cache.ResultCache(tmp_path / "c.sqlite")
    try:
        rc.set("k", "x", ttl=0)
        assert rc.get("k") == (False, None)
    finally:
        rc.close()


# --- cached() decorator ---------------------------------------------------


def test_cached_decorator_caches_results(enabled_cache):
    calls = {"n": 0}

    @cache.cached("quote")
    def fetch(symbol):
        calls["n"] += 1
        return {"symbol": symbol}

    assert fetch("AAPL") == {"symbol": "AAPL"}
    assert fetch("AAPL") == {"symbol": "AAPL"}
    assert calls["n"] == 1  # second call served from cache


def test_cached_decorator_key_is_case_insensitive(enabled_cache):
    calls = {"n": 0}

    @cache.cached("quote")
    def fetch(symbol):
        calls["n"] += 1
        return symbol

    fetch("aapl")
    fetch("AAPL")
    assert calls["n"] == 1


def test_cached_decorator_passthrough_when_disabled():
    cache.configure(enabled=False)
    calls = {"n": 0}

    @cache.cached("quote")
    def fetch(symbol):
        calls["n"] += 1
        return symbol

    fetch("AAPL")
    fetch("AAPL")
    assert calls["n"] == 2  # no caching


def test_cached_decorator_does_not_cache_exceptions(enabled_cache):
    calls = {"n": 0}

    @cache.cached("quote")
    def fetch(symbol):
        calls["n"] += 1
        raise ValueError("boom")

    with pytest.raises(ValueError):
        fetch("AAPL")
    with pytest.raises(ValueError):
        fetch("AAPL")
    assert calls["n"] == 2  # error path re-runs every time


def test_ttl_override_zero_disables_category(tmp_path):
    cache.configure(enabled=True, cache_dir=str(tmp_path), ttl_overrides={"quote": 0})
    try:
        calls = {"n": 0}

        @cache.cached("quote")
        def fetch(symbol):
            calls["n"] += 1
            return symbol

        fetch("AAPL")
        fetch("AAPL")
        assert calls["n"] == 2  # ttl 0 -> not stored
    finally:
        cache.configure(enabled=False)


# --- config helpers -------------------------------------------------------


def test_env_enabled(monkeypatch):
    monkeypatch.delenv("YF_MCP_CACHE", raising=False)
    assert cache.env_enabled() is True
    monkeypatch.setenv("YF_MCP_CACHE", "off")
    assert cache.env_enabled() is False
    monkeypatch.setenv("YF_MCP_CACHE", "1")
    assert cache.env_enabled() is True


def test_ttls_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_CACHE_TTL_QUOTE", "15")
    monkeypatch.setenv("YF_MCP_CACHE_TTL_NEWS", "not-a-number")
    out = cache.ttls_from_env()
    assert out["quote"] == 15.0
    assert "news" not in out  # invalid value ignored


def test_default_cache_dir_honors_env(monkeypatch, tmp_path):
    monkeypatch.setenv("YF_MCP_CACHE_DIR", str(tmp_path))
    assert cache.default_cache_dir() == tmp_path
