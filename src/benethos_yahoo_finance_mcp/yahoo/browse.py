"""Browsing without a ticker: sectors, industries and whole markets,
each by a fixed Yahoo key."""

from __future__ import annotations

from typing import Any

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from .. import cache, logbook
from ..errors import RateLimitError, SymbolNotFoundError, ToolError
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers

# Sector/industry keys are sourced from yfinance's own constant so they stay in
# sync with upstream. That constant is semi-internal (note the upstream typo in
# its name), so the import is defensive: if it is ever renamed or removed we fall
# back to a known-good snapshot of the 11 sector keys, and correctness never
# depends on this list alone — an invalid key is still caught at runtime when
# yfinance returns no data.
_FALLBACK_SECTOR_KEYS = (
    "basic-materials",
    "communication-services",
    "consumer-cyclical",
    "consumer-defensive",
    "energy",
    "financial-services",
    "healthcare",
    "industrials",
    "real-estate",
    "technology",
    "utilities",
)

try:
    from yfinance.const import (
        SECTOR_INDUSTY_MAPPING_LC as _SECTOR_INDUSTRY_MAP_RAW,
    )

    SECTOR_INDUSTRY_MAP: dict[str, tuple[str, ...]] = {
        str(sec): tuple(inds) for sec, inds in _SECTOR_INDUSTRY_MAP_RAW.items()
    }
except Exception:  # noqa: BLE001 - constant is semi-internal; degrade gracefully
    logbook.upstream.sector_keys_unavailable()
    SECTOR_INDUSTRY_MAP = {key: () for key in _FALLBACK_SECTOR_KEYS}

# Public, derived from the mapping above (single source of truth for code + docs).
SECTOR_KEYS: tuple[str, ...] = tuple(SECTOR_INDUSTRY_MAP)
# Flat set of all valid industry keys; empty only if the fallback is in effect,
# in which case industry validation defers entirely to the runtime check.
INDUSTRY_KEYS: frozenset[str] = frozenset(
    ind for inds in SECTOR_INDUSTRY_MAP.values() for ind in inds
)


@cache.cached("sector")
def get_sector(key: str, *, limit: int = 25) -> dict[str, Any]:
    """Return an overview of a market sector by its Yahoo ``key``.

    ``key`` is one of Yahoo's fixed sector keys (e.g. ``technology``,
    ``healthcare``, ``financial-services``). Returns the sector overview, top
    companies/ETFs/mutual funds, and the constituent industries (whose ``key``
    feeds :func:`get_industry`).
    """
    key = (key or "").strip().lower()
    if not key:
        raise ToolError("A non-empty sector key is required.")
    if key not in SECTOR_KEYS:
        raise ToolError(
            f"Unknown sector key {key!r}. Valid keys: {', '.join(SECTOR_KEYS)}."
        )

    with tickers.upstream(f"Failed to load sector {key!r}"):
        sector = yf.Sector(key)
        name = sector.name
        index_symbol = sector.symbol
        overview = sector.overview
        top_companies = sector.top_companies
        top_etfs = sector.top_etfs
        top_mutual_funds = sector.top_mutual_funds
        industries = sector.industries

    if not name:
        # Key is valid but yfinance returned no data (transient/upstream issue).
        raise SymbolNotFoundError(key)

    return {
        "key": key,
        "name": name,
        "index_symbol": index_symbol,
        "overview": to_jsonable(overview),
        "top_companies": dataframe_to_records(
            top_companies, max_rows=limit, index_name="symbol", head=True
        ),
        "top_etfs": to_jsonable(top_etfs),
        "top_mutual_funds": to_jsonable(top_mutual_funds),
        "industries": dataframe_to_records(industries, index_name="key"),
    }


@cache.cached("industry")
def get_industry(key: str, *, limit: int = 25) -> dict[str, Any]:
    """Return an overview of an industry by its Yahoo ``key``.

    ``key`` is a Yahoo industry key (e.g. ``semiconductors``,
    ``software-infrastructure``); discover valid keys from the ``industries``
    list returned by :func:`get_sector`. Returns the industry overview, its
    parent sector, top companies, and the top-performing and top-growth
    companies.
    """
    key = (key or "").strip().lower()
    if not key:
        raise ToolError("A non-empty industry key is required.")
    # Offline pre-check when the upstream key set is known; otherwise defer to
    # the runtime check below.
    if INDUSTRY_KEYS and key not in INDUSTRY_KEYS:
        raise ToolError(
            f"Unknown industry key {key!r}. Discover valid keys from the "
            "'industries' list returned by get_sector."
        )

    with tickers.upstream(f"Failed to load industry {key!r}"):
        industry = yf.Industry(key)
        name = industry.name
        index_symbol = industry.symbol
        sector_key = industry.sector_key
        sector_name = industry.sector_name
        overview = industry.overview
        top_companies = industry.top_companies
        top_performing = industry.top_performing_companies
        top_growth = industry.top_growth_companies

    if not name:
        # Key is valid but yfinance returned no data (transient/upstream issue).
        raise SymbolNotFoundError(key)

    return {
        "key": key,
        "name": name,
        "index_symbol": index_symbol,
        "sector_key": sector_key,
        "sector_name": sector_name,
        "overview": to_jsonable(overview),
        "top_companies": dataframe_to_records(
            top_companies, max_rows=limit, index_name="symbol", head=True
        ),
        "top_performing_companies": dataframe_to_records(
            top_performing, index_name="symbol"
        ),
        "top_growth_companies": dataframe_to_records(top_growth, index_name="symbol"),
    }


# Market keys accepted by yfinance's ``Market``. There is no upstream constant to
# import, so this mirrors the list its own validation reports. Probed live: only
# "US" serves a market status — the other keys raise upstream when asked for one,
# while the index summary works for all eight.
MARKET_KEYS: tuple[str, ...] = (
    "US",
    "GB",
    "ASIA",
    "EUROPE",
    "RATES",
    "COMMODITIES",
    "CURRENCIES",
    "CRYPTOCURRENCIES",
)

# Curated subsets. The raw payloads carry a lot of noise (language, region,
# triggerable, esgPopulated and so on) that costs tokens without informing.
_MARKET_STATUS_FIELDS = ("id", "name", "status", "open", "close", "tz", "message")
_MARKET_INDEX_FIELDS = (
    "symbol",
    "shortName",
    "fullExchangeName",
    "marketState",
    "regularMarketPrice",
    "regularMarketPreviousClose",
    "regularMarketChange",
    "regularMarketChangePercent",
)


@cache.cached("market")
def get_market(key: str = "US") -> dict[str, Any]:
    """Return the trading status and index summary for a market.

    ``key`` is one of Yahoo's fixed market keys (see :data:`MARKET_KEYS`).
    ``status`` is only served for ``US`` and comes back ``None`` elsewhere, which
    is an upstream limitation rather than an error. The index summary is
    available for every key.
    """
    key = (key or "").strip().upper()
    if not key:
        raise ToolError("A non-empty market key is required.")
    if key not in MARKET_KEYS:
        raise ToolError(
            f"Unknown market key {key!r}. Valid keys: {', '.join(MARKET_KEYS)}."
        )

    with tickers.upstream(f"Failed to load market {key!r}"):
        market = yf.Market(key)

    # Yahoo only serves the markettime endpoint for "US". Every other key raises
    # here instead of returning nothing, so treat a failure as "unavailable".
    status: dict[str, Any] | None = None
    try:
        raw = market.status or {}
        # Normalize an empty selection to None. Upstream is inconsistent about
        # how it reports "no status": it raises for some keys and returns None
        # for others, and an empty dict would be a third, ambiguous answer.
        status = {
            f: to_jsonable(raw.get(f)) for f in _MARKET_STATUS_FIELDS if f in raw
        } or None
    except YFRateLimitError as exc:
        raise RateLimitError() from exc
    except Exception:  # noqa: BLE001 - status is optional, the summary is not
        status = None

    with tickers.upstream(f"Failed to load market summary for {key!r}"):
        summary = market.summary or {}

    indices: list[dict[str, Any]] = []
    for entry in summary.values():
        if not isinstance(entry, dict):
            continue
        indices.append({f: to_jsonable(entry.get(f)) for f in _MARKET_INDEX_FIELDS})

    if not indices and not status:
        raise SymbolNotFoundError(key)

    return {"key": key, "status": status, "count": len(indices), "indices": indices}
