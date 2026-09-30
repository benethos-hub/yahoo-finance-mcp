"""Everything this server can be configured with, resolved once.

A setting comes from a command-line flag, a ``YF_MCP_*`` environment variable,
or its default, in that order of precedence. :func:`load_settings` is the one
place that reads the environment, and every other module gets its values from
the :class:`Settings` it returns.

This module stands on nothing else in the package, so it cannot log. A value it
has to throw away is recorded in :attr:`Settings.ignored` instead, and the
caller reports it once logging is set up, which needs the log level resolved
here first.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
TRANSPORTS = ("stdio", "streamable-http", "sse")

# There is deliberately no command-line flag for the token. An argument is
# visible in the process list to every other user on the machine and lands in
# shell history, and neither is where a secret belongs.
TOKEN_VAR = "YF_MCP_BEARER_TOKEN"

# Default time-to-live per tool category, in seconds. Tuned to the volatility of
# each data type: quotes change constantly, fundamentals rarely. Each category
# is one ``@cache.cached("<category>")`` in the yahoo package, and each can be
# overridden with ``YF_MCP_CACHE_TTL_<CATEGORY>`` or ``--cache-ttl``.
DEFAULT_TTLS: dict[str, float] = {
    "search": 3600,
    "quote": 30,
    "quotes": 30,
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
    "shares": 24 * 3600,
    "fund_data": 24 * 3600,
    "sector": 24 * 3600,
    "industry": 24 * 3600,
    # Index prices move constantly, the open/closed status changes twice a day.
    "market": 60,
}

_FALSY = {"0", "false", "no", "off", ""}


class SettingsError(ValueError):
    """A flag value that cannot be used. The message is written for the user."""


@dataclass(frozen=True)
class Settings:
    """The resolved configuration. The defaults are what a bare start gets."""

    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    # ``None`` means the transport's own default, see :attr:`http_path`.
    path: str | None = None
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()
    log_level: str = "INFO"
    cache_enabled: bool = False
    # Resolved only when the cache is on: finding the platform default can
    # fail on a machine without a home directory, and a server that does not
    # cache has no reason to look.
    cache_dir: Path | None = None
    cache_ttls: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_TTLS))
    bearer_token: str | None = None
    # ``(variable, value)`` for every environment value that was unusable and
    # replaced by its default.
    ignored: tuple[tuple[str, str], ...] = ()

    @property
    def http_path(self) -> str:
        """The URL path an HTTP transport serves on, defaulted per transport."""
        if self.path:
            return self.path
        return "/sse" if self.transport == "sse" else "/mcp"


def load_settings(
    flags: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Resolve every setting: flag first, then environment, then default.

    ``flags`` maps a setting to the value given on the command line, with
    ``None`` (or a missing key) for a flag that was not given. ``cache_ttl``
    takes the raw ``<NAME>=<SECONDS>`` items. Raises :class:`SettingsError`
    for a flag value that cannot be used. An unusable environment value falls
    back to the default and is recorded in :attr:`Settings.ignored`, because a
    variable set somewhere out of sight should not stop the server.
    """
    flags = flags or {}
    env = os.environ if environ is None else environ
    ignored: list[tuple[str, str]] = []

    def given(name: str) -> Any:
        return flags.get(name)

    def from_env(var: str, parse: Any, default: Any) -> Any:
        raw = env.get(var)
        if raw is None:
            return default
        try:
            return parse(raw)
        except ValueError:
            ignored.append((var, raw))
            return default

    transport = given("transport") or from_env(
        "YF_MCP_TRANSPORT", _choice(TRANSPORTS, str.lower), "stdio"
    )
    log_level = given("log_level") or from_env(
        "YF_MCP_LOG_LEVEL", _choice(LOG_LEVELS, str.upper), "INFO"
    )
    port = given("port")
    if port is None:
        port = from_env("YF_MCP_PORT", int, 8000)

    cache_enabled = given("cache")
    if cache_enabled is None:
        cache_enabled = from_env("YF_MCP_CACHE", _truthy, False)
    cache_dir_raw = given("cache_dir") or env.get("YF_MCP_CACHE_DIR")
    cache_dir: Path | None = Path(cache_dir_raw) if cache_dir_raw else None
    if cache_enabled and cache_dir is None:
        cache_dir = default_cache_dir(env)

    ttls = dict(DEFAULT_TTLS)
    for name in DEFAULT_TTLS:
        ttls[name] = from_env(f"YF_MCP_CACHE_TTL_{name.upper()}", float, ttls[name])
    ttls.update(parse_ttl_items(given("cache_ttl") or ()))

    return Settings(
        transport=transport,
        host=given("host") or env.get("YF_MCP_HOST", "127.0.0.1"),
        port=port,
        path=given("path") or env.get("YF_MCP_PATH") or None,
        allowed_hosts=split_csv(
            given("allowed_hosts") or env.get("YF_MCP_ALLOWED_HOSTS")
        ),
        allowed_origins=split_csv(
            given("allowed_origins") or env.get("YF_MCP_ALLOWED_ORIGINS")
        ),
        log_level=log_level,
        cache_enabled=bool(cache_enabled),
        cache_dir=cache_dir,
        cache_ttls=ttls,
        bearer_token=token_from(env),
        ignored=tuple(ignored),
    )


def _choice(allowed: tuple[str, ...], normalize: Any) -> Any:
    """A parser that accepts one of ``allowed`` after ``normalize``."""

    def parse(raw: str) -> str:
        value = normalize(raw.strip())
        if value not in allowed:
            raise ValueError(raw)
        return str(value)

    return parse


def _truthy(raw: str) -> bool:
    return raw.strip().lower() not in _FALSY


def split_csv(value: str | None) -> tuple[str, ...]:
    """Split a comma-separated option value into a clean tuple of items."""
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_ttl_items(items: Any) -> dict[str, float]:
    """Parse ``<NAME>=<SECONDS>`` ``--cache-ttl`` items into a mapping."""
    overrides: dict[str, float] = {}
    for item in items:
        name, sep, raw = item.partition("=")
        name = name.strip().lower()
        if not sep or name not in DEFAULT_TTLS:
            raise SettingsError(
                f"invalid --cache-ttl {item!r}, expected <NAME>=<SECONDS> with <NAME> "
                f"one of {', '.join(DEFAULT_TTLS)}"
            )
        try:
            overrides[name] = float(raw)
        except ValueError:
            raise SettingsError(f"invalid --cache-ttl seconds in {item!r}") from None
    return overrides


def token_from(environ: Mapping[str, str]) -> str | None:
    """The configured bearer token, or ``None`` when the port is left unguarded.

    An empty or blank value counts as unset rather than as a token nobody can
    guess, because ``YF_MCP_BEARER_TOKEN=`` in a Compose file or a shell profile
    reads as "off" to everyone who writes it.
    """
    return (environ.get(TOKEN_VAR) or "").strip() or None


def default_cache_dir(environ: Mapping[str, str] | None = None) -> Path:
    """The OS user cache directory for this app.

    Follows the platform convention, falling back to the system temp directory
    on Windows when ``LOCALAPPDATA`` is missing.
    """
    env = os.environ if environ is None else environ
    if sys.platform == "win32":
        base = env.get("LOCALAPPDATA") or tempfile.gettempdir()
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = env.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "benethos-yahoo-finance-mcp"
