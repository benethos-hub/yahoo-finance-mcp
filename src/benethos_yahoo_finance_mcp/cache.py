"""Optional persistent result cache with per-tool TTLs.

This caches the *normalized results* of the client functions (not yfinance HTTP
responses — yfinance uses curl_cffi and rejects caching sessions). Results are
stored in a small SQLite file so they survive restarts; each tool category has
its own time-to-live.

The cache is **disabled until :func:`configure` is called** (which the server
entry point does at startup). Importing the package or calling client functions
directly therefore does not touch the disk unless caching is explicitly turned
on — convenient for tests and library use.

Whether it is on, where its file lives and every TTL come from the
:class:`~benethos_yahoo_finance_mcp.settings.Settings` handed to
:func:`configure`. This module does not read the environment.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from . import logbook
from . import settings as settings_mod
from .settings import Settings

F = TypeVar("F", bound=Callable[..., Any])

# The categories and their default time-to-live live with the rest of the
# configuration. Re-exported because every category here is one of them.
DEFAULT_TTLS = settings_mod.DEFAULT_TTLS

# PRAGMA auto_vacuum: 0 none, 1 full, 2 incremental.
_INCREMENTAL = 2

# --- module state (set by configure) --------------------------------------
_lock = threading.Lock()
_enabled = False
_ttls: dict[str, float] = dict(DEFAULT_TTLS)
_cache: ResultCache | None = None


class ResultCache:
    """A tiny SQLite-backed key/value store with per-entry expiry.

    An expired entry is deleted when it is read, and every ``PURGE_EVERY``
    writes the whole file is swept. Startup used to be the only sweep, and a
    long-running HTTP server kept every entry nobody asked for again.

    The pages a sweep frees go back to the file system, so the file follows
    what it holds. SQLite reuses freed pages but never hands them back on
    its own, and the file used to stay at its largest size for good.
    """

    PURGE_EVERY = 100

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._make_shrinkable()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(key TEXT PRIMARY KEY, expires_at REAL NOT NULL, value TEXT NOT NULL)"
        )
        self._conn.commit()
        self._lock = threading.Lock()
        self._writes = 0

    def _make_shrinkable(self) -> None:
        """Put ``auto_vacuum`` in its incremental mode, which ``_shrink`` needs.

        The mode has to be set before the first table exists. A new file takes
        it as it is. One made without it, by a version before this, is
        rewritten once, which ``VACUUM`` does outside any transaction, and the
        log says so. Called before the table is created, with no lock yet.
        """
        mode = self._conn.execute("PRAGMA auto_vacuum").fetchone()[0]
        if mode == _INCREMENTAL:
            return
        self._conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        has_tables = self._conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        if has_tables.fetchone() is None:
            return
        logbook.cache.file_rewritten()
        self._conn.execute("VACUUM")

    def _shrink(self) -> None:
        """Give the pages a sweep freed back to the file system.

        Called with the lock held, after the sweep is committed. Cheap when
        there is nothing to give back.

        The pragma frees one page per step and returns no rows, so it only
        finishes if something keeps stepping it. ``execute`` does not on Python
        3.11: for a statement without result columns it steps once and stops,
        ``fetchall`` has nothing to fetch, and a sweep gave back one page out
        of hundreds with no error anywhere. 3.12 steps it to the end, so the
        tests passed there and failed only in CI on 3.11. ``executescript``
        steps every statement to completion on every version. It commits an
        open transaction first, which is why this runs only after a commit.
        """
        self._conn.executescript("PRAGMA incremental_vacuum;")

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
            logbook.cache.not_serializable()
            return
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, expires_at, value) "
                "VALUES (?, ?, ?)",
                (key, now + ttl, payload),
            )
            self._writes += 1
            sweep = self._writes % self.PURGE_EVERY == 0
            if sweep:
                self._conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
            self._conn.commit()
            if sweep:
                self._shrink()

    def purge_expired(self) -> None:
        """Delete all expired entries (housekeeping)."""
        with self._lock:
            self._conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
            self._conn.commit()
            self._shrink()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()
            self._shrink()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def configure(settings: Settings) -> None:
    """Enable or disable the cache and apply the TTLs, as ``settings`` says.

    Called once at startup. Safe to call again (e.g. in tests); it closes any
    existing cache first.
    """
    global _enabled, _ttls, _cache
    with _lock:
        _ttls = {**DEFAULT_TTLS, **settings.cache_ttls}
        if _cache is not None:
            _cache.close()
            _cache = None
        _enabled = settings.cache_enabled
        if _enabled:
            directory: Path = settings.cache_dir or settings_mod.default_cache_dir()
            _cache = ResultCache(directory / "cache.sqlite")
            _cache.purge_expired()
            logbook.cache.enabled(directory)
        else:
            logbook.cache.disabled()


def _make_key(category: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Build a stable cache key from the call's category and arguments."""
    raw = {
        "c": category,
        "a": [str(a).strip().lower() for a in args],
        "k": {k: str(v).strip().lower() for k, v in sorted(kwargs.items())},
    }
    blob = json.dumps(raw, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def cached(
    category: str, *, worth_keeping: Callable[[Any], bool] = bool
) -> Callable[[F], F]:
    """Decorate a client function to cache its successful results under ``category``.

    ``worth_keeping`` decides whether a result is stored. The default skips
    empty ones, a search with no matches say, so a transient empty response is
    not pinned for the whole TTL. A function whose "nothing found" is a
    non-empty dict passes its own test.

    When caching is disabled the wrapper is a transparent pass-through. Only
    successful returns are stored; exceptions propagate and are never cached.

    The cache is an optimisation, so its own failures never fail the call. A
    second process on the same cache directory can hold the database locked,
    and a file can be damaged. Either way the result is fetched and returned
    as if caching were off, and a warning says why.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _enabled or _cache is None:
                return fn(*args, **kwargs)
            store = _cache
            key = _make_key(category, args, kwargs)
            try:
                hit, value = store.get(key)
            except sqlite3.Error as exc:
                logbook.cache.read_failed(exc)
                hit, value = False, None
            if hit:
                logbook.calls.cache_hit()
                return value
            result = fn(*args, **kwargs)
            if worth_keeping(result):
                try:
                    store.set(key, result, _ttls.get(category, 0))
                except sqlite3.Error as exc:
                    logbook.cache.write_failed(exc)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
