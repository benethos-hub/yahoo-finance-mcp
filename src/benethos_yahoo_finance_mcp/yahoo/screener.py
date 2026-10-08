"""Screening the stock market by criteria, without a symbol to start from.

Yahoo's screener knows 92 fields with names like
``lastclosepriceearnings.lasttwelvemonths``, which no model guesses. A short
table of aliases covers the questions people actually ask, and the raw names
stay accepted for the rest. Every filter is checked here before Yahoo sees it,
so a mistake comes back as a message saying what to change rather than as
yfinance's ``Invalid EQ value``.
"""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any

import yfinance as yf
from yfinance.const import EQUITY_SCREENER_EQ_MAP, EQUITY_SCREENER_FIELDS

from .. import cache
from ..errors import ToolError
from ..formatting import to_jsonable
from . import tickers

# Alias -> Yahoo field, grouped as the tool description lists them. Every
# percentage is given in percent, 3 meaning 3 %, checked live on 2026-10-08
# against the fractions the quote data carries for the same companies.
SCREEN_ALIASES: dict[str, str] = {
    # Market
    "market_cap": "intradaymarketcap",
    "price": "intradayprice",
    "change_percent": "percentchange",
    "change_52w_percent": "fiftytwowkpercentchange",
    "volume": "dayvolume",
    "avg_volume_3m": "avgdailyvol3m",
    "beta": "beta",
    # Valuation
    "pe_ratio": "peratio.lasttwelvemonths",
    "peg_ratio": "pegratio_5y",
    "price_to_book": "pricebookratio.quarterly",
    "price_to_sales": "lastclosemarketcaptotalrevenue.lasttwelvemonths",
    "ev_to_ebitda": "lastclosetevebitda.lasttwelvemonths",
    # Dividend
    "dividend_yield": "dividendyield",
    "forward_dividend_yield": "forward_dividend_yield",
    "dividend_growth_years": "consecutive_years_of_dividend_growth_count",
    # Profitability and growth
    "return_on_equity": "returnonequity.lasttwelvemonths",
    "return_on_assets": "returnonassets.lasttwelvemonths",
    "net_margin": "netincomemargin.lasttwelvemonths",
    "revenue": "totalrevenues.lasttwelvemonths",
    "revenue_growth": "totalrevenues1yrgrowth.lasttwelvemonths",
    "eps_growth": "epsgrowth.lasttwelvemonths",
    # Balance sheet
    "debt_to_equity": "totaldebtequity.lasttwelvemonths",
    "current_ratio": "currentratio.lasttwelvemonths",
    # Ownership
    "insider_percent": "pctheldinsider",
    "institutional_percent": "pctheldinst",
    "short_percent_of_float": "short_percentage_of_float.value",
    # ESG
    "esg_score": "esg_score",
    # Categorical
    "region": "region",
    "exchange": "exchange",
    "sector": "sector",
    "industry": "industry",
}

SCREEN_OPERATORS: tuple[str, ...] = ("eq", "gt", "gte", "lt", "lte", "btwn", "is-in")
_COMPARISONS = frozenset({"gt", "gte", "lt", "lte", "btwn"})

# Every field Yahoo's screener accepts, lower-cased as it spells them.
_FIELDS: frozenset[str] = frozenset(
    field for group in EQUITY_SCREENER_FIELDS.values() for field in group
)


def _slug(value: str) -> str:
    """``value`` lower-cased with every run of other characters as one hyphen.

    The screener spells an industry ``Software—Infrastructure``, with an em
    dash, while get_sector hands out ``software-infrastructure`` as its key
    and ``Software - Infrastructure`` as its name. All three meet here, and
    so do ``us`` and ``US``. No two values of one field share a slug.
    """
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _values(raw: Any) -> list[str]:
    """The values of one field, which the upstream map nests by region or sector."""
    if isinstance(raw, dict):
        return sorted({str(v) for group in raw.values() for v in group})
    return sorted(str(v) for v in raw)


# Categorical field -> {slug: the value as Yahoo spells it}.
_CATEGORIES: dict[str, dict[str, str]] = {
    field: {_slug(value): value for value in _values(raw)}
    for field, raw in EQUITY_SCREENER_EQ_MAP.items()
}

_HIT_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("symbol", ("symbol",)),
    ("name", ("longName", "shortName")),
    ("exchange", ("fullExchangeName", "exchange")),
    ("currency", ("currency",)),
    ("price", ("regularMarketPrice",)),
    ("change_percent", ("regularMarketChangePercent",)),
    ("market_cap", ("marketCap",)),
    ("pe_ratio", ("trailingPE",)),
    ("price_to_book", ("priceToBook",)),
    ("eps", ("epsTrailingTwelveMonths",)),
    ("dividend_yield", ("dividendYield",)),
    ("change_52w_percent", ("fiftyTwoWeekChangePercent",)),
    ("avg_volume_3m", ("averageDailyVolume3Month",)),
)

Filter = tuple[str, str, Any]


def _field(name: str) -> str:
    """The Yahoo field behind an alias or a raw name, else a ``ToolError``."""
    key = str(name).strip().lower()
    if key in SCREEN_ALIASES:
        return SCREEN_ALIASES[key]
    if key in _FIELDS:
        return key
    raise ToolError(
        f"Unknown screen field {name!r}. Use one of the aliases "
        f"{', '.join(SCREEN_ALIASES)}, or a raw Yahoo screener field name."
    )


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _category_value(field: str, value: Any) -> str:
    """``value`` as Yahoo spells it for the categorical ``field``."""
    known = _CATEGORIES[field]
    if isinstance(value, str) and _slug(value) in known:
        return known[_slug(value)]
    # 145 industries are too many to list, and get_sector names them by sector.
    if field == "industry":
        hint = (
            "Pass an industry key or name as get_sector lists them under "
            "'industries', e.g. 'semiconductors'."
        )
    else:
        hint = f"Valid values: {', '.join(known.values())}."
    raise ToolError(f"{value!r} is not a valid {field}. {hint}")


def _checked(raw: Filter) -> tuple[str, str, list[Any]]:
    """One filter as ``(operator, field, values)``, ready for an EquityQuery."""
    name, op, value = raw
    field = _field(name)
    op = str(op).strip().lower()
    if op not in SCREEN_OPERATORS:
        raise ToolError(
            f"Unknown operator {op!r} for {name!r}. Use one of "
            f"{', '.join(SCREEN_OPERATORS)}."
        )
    categorical = field in _CATEGORIES
    if categorical and op in _COMPARISONS:
        raise ToolError(
            f"{name!r} is a category, compare it with eq or is-in, not {op}."
        )

    values = list(value) if isinstance(value, (list, tuple)) else [value]
    if op == "btwn":
        if len(values) != 2 or not all(_is_number(v) for v in values):
            raise ToolError(
                f"btwn on {name!r} takes a list of two numbers, low and high."
            )
        if values[0] > values[1]:
            raise ToolError(
                f"btwn on {name!r}: the low bound {values[0]} is above the high "
                f"bound {values[1]}."
            )
    elif op == "is-in":
        if not isinstance(value, (list, tuple)) or not values:
            raise ToolError(f"is-in on {name!r} takes a non-empty list of values.")
    elif isinstance(value, (list, tuple)):
        raise ToolError(f"{op} on {name!r} takes a single value, not a list.")

    if categorical:
        return op, field, [_category_value(field, v) for v in values]
    if not all(_is_number(v) for v in values):
        raise ToolError(f"{name!r} is numeric, {op} on it takes numbers.")
    return op, field, values


def _query(filters: tuple[Filter, ...]) -> yf.EquityQuery:
    """The filters as one EquityQuery, all of them to hold at once."""
    if not filters:
        raise ToolError(
            "At least one filter is required, e.g. "
            "{'field': 'region', 'op': 'eq', 'value': 'us'}."
        )
    parts = [
        yf.EquityQuery(op, [field, *values])
        for op, field, values in (_checked(f) for f in filters)
    ]
    return parts[0] if len(parts) == 1 else yf.EquityQuery("and", parts)


def _hit(quote: dict[str, Any]) -> dict[str, Any]:
    """One match, curated, with the empty columns left out."""
    row: dict[str, Any] = {}
    for column, keys in _HIT_COLUMNS:
        value = next((quote[k] for k in keys if quote.get(k) not in (None, "")), None)
        if value is not None:
            row[column] = to_jsonable(value)
    return row


@cache.cached("screen")
def screen(
    filters: tuple[Filter, ...],
    *,
    sort_by: str = "market_cap",
    sort_desc: bool = True,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return the stocks matching every filter, one curated row each.

    ``filters`` is a tuple of ``(field, op, value)``, a tuple so the cache key
    is stable. ``total`` is how many stocks match in all, which says more
    than the rows do when it runs into the thousands.
    """
    query = _query(filters)
    sort_field = _field(sort_by)
    if sort_field in _CATEGORIES:
        raise ToolError(f"Cannot sort by the category {sort_by!r}, pick a number.")
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    with tickers.upstream("Screen failed"):
        result = yf.screen(
            query,
            offset=offset,
            size=limit,
            sortField=sort_field,
            sortAsc=not sort_desc,
        )

    quotes = (result or {}).get("quotes") or []
    matches = [_hit(q) for q in quotes[:limit] if isinstance(q, dict)]
    return {
        "total": (result or {}).get("total", len(matches)),
        "count": len(matches),
        "offset": (result or {}).get("start", offset),
        "matches": matches,
    }
