"""Optional persistent result cache with per-tool TTLs.

This caches the *normalized results* of the client functions (not yfinance HTTP
responses — yfinance uses curl_cffi and rejects caching sessions). Results are
stored in a small SQLite file so they survive restarts; each tool category has
its own time-to-live.

The cache is **disabled until :func:`configure` is called** (which the server
entry point does at startup). Importing the package or calling client functions
directly therefore does not touch the disk unless caching is explicitly turned
on — convenient for tests and library use.

Configuration precedence is CLI > environment > default, resolved by the caller
(`server.main`); this module reads the environment only for the values it owns
(per-tool TTLs and the cache directory fallback).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Default time-to-live per tool category, in seconds. Tuned to the volatility of
# each data type: quotes change constantly, fundamentals rarely.
DEFAULT_TTLS: dict[str, float] = {
    "search": 3600,
    "quote": 30,
    "history": 600,
    "company_info": 6 * 3600,
    "financials": 24 * 3600,
    "dividends": 6 * 3600,
    "news": 600,
    "recommendations": 6 * 3600,
    "options": 600,
    "earnings": 6 * 3600,
    "estimates": 6 * 3600,
    "upgrades_downgrades": 6 * 3600,
    "holders": 24 * 3600,
    "insider_activity": 6 * 3600,
    "sec_filings": 6 * 3600,
    "calendar": 6 * 3600,
}

_FALSY = {"0", "false", "no", "off", ""}

# --- module state (set by configure) --------------------------------------
_lock = threading.Lock()
_enabled = False
_ttls: dict[str, float] = dict(DEFAULT_TTLS)
_cache: ResultCache | None = None


def env_enabled(default: bool = False) -> bool:
    """Whether caching is enabled per the ``YF_MCP_CACHE`` env var.

    Caching is **opt-in**: it is off unless ``YF_MCP_CACHE`` is truthy (or the
    ``--cache`` flag is passed).
    """
    val = os.environ.get("YF_MCP_CACHE")
    if val is None:
        return default
    return val.strip().lower() not in _FALSY


def ttls_from_env() -> dict[str, float]:
    """Read per-tool TTL overrides from ``YF_MCP_CACHE_TTL_<NAME>`` env vars."""
    overrides: dict[str, float] = {}
    for name in DEFAULT_TTLS:
        raw = os.environ.get(f"YF_MCP_CACHE_TTL_{name.upper()}")
        if raw is None:
            continue
        try:
            overrides[name] = float(raw)
        except ValueError:
            logger.warning("Ignoring invalid TTL for %s: %r", name, raw)
    return overrides


def default_cache_dir() -> Path:
    """Return the OS user cache directory for this app.

    Honors ``YF_MCP_CACHE_DIR`` first, then the platform convention, falling
    back to the system temp directory.
    """
    env = os.environ.get("YF_MCP_CACHE_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "yahoo-finance-mcp"


class ResultCache:
    """A tiny SQLite-backed key/value store with per-entry expiry."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(key TEXT PRIMARY KEY, expires_at REAL NOT NULL, value TEXT NOT NULL)"
        )
        self._conn.commit()
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[bool, Any]:
        """Return ``(hit, value)``; a miss or expired entry yields ``(False, None)``."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT expires_at, value FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return False, None
            expires_at, value = row
            if expires_at < now:
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._conn.commit()
                return False, None
        try:
            return True, json.loads(value)
        except (ValueError, TypeError):
            return False, None

    def set(self, key: str, value: Any, ttl: float) -> None:
        """Store ``value`` under ``key`` for ``ttl`` seconds (no-op if ``ttl <= 0``)."""
        if ttl <= 0:
            return
        try:
            payload = json.dumps(value)
        except (TypeError, ValueError):
            logger.debug("Skipping cache for non-serializable value under %s", key)
            return
        expires_at = time.time() + ttl
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, expires_at, value) "
                "VALUES (?, ?, ?)",
                (key, expires_at, payload),
            )
            self._conn.commit()

    def purge_expired(self) -> None:
        """Delete all expired entries (housekeeping)."""
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def configure(
    *,
    enabled: bool,
    cache_dir: str | None = None,
    ttl_overrides: dict[str, float] | None = None,
) -> None:
    """Enable or disable the cache and apply TTL overrides.

    Called once at startup. Safe to call again (e.g. in tests); it closes any
    existing cache first.
    """
    global _enabled, _ttls, _cache
    with _lock:
        _ttls = {**DEFAULT_TTLS, **(ttl_overrides or {})}
        if _cache is not None:
            _cache.close()
            _cache = None
        _enabled = enabled
        if enabled:
            directory = Path(cache_dir) if cache_dir else default_cache_dir()
            _cache = ResultCache(directory / "cache.sqlite")
            _cache.purge_expired()
            logger.info("Result cache enabled at %s", directory)
        else:
            logger.info("Result cache disabled")


def _make_key(category: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Build a stable cache key from the call's category and arguments."""
    raw = {
        "c": category,
        "a": [str(a).strip().lower() for a in args],
        "k": {k: str(v).strip().lower() for k, v in sorted(kwargs.items())},
    }
    blob = json.dumps(raw, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def cached(category: str) -> Callable[[F], F]:
    """Decorate a client function to cache its successful results under ``category``.

    When caching is disabled the wrapper is a transparent pass-through. Only
    successful returns are stored; exceptions propagate and are never cached.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _enabled or _cache is None:
                return fn(*args, **kwargs)
            key = _make_key(category, args, kwargs)
            hit, value = _cache.get(key)
            if hit:
                return value
            result = fn(*args, **kwargs)
            # Skip empty results (e.g. a search with no matches) so a transient
            # empty response is not pinned for the whole TTL.
            if result:
                _cache.set(key, result, _ttls.get(category, 0))
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
