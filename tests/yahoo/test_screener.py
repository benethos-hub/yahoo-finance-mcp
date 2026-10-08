"""Unit tests for the stock screener.

yfinance's ``screen`` is mocked, nothing here reaches the network. Its
``EquityQuery`` is the real one, so a filter the checks let through is also
one yfinance accepts.
"""

from __future__ import annotations

import pytest
from yfinance.const import EQUITY_SCREENER_FIELDS
from yfinance.exceptions import YFRateLimitError

from benethos_yahoo_finance_mcp import cache, yahoo
from benethos_yahoo_finance_mcp.errors import RateLimitError, ToolError
from benethos_yahoo_finance_mcp.settings import Settings
from benethos_yahoo_finance_mcp.yahoo import screener, tickers

US = ("region", "eq", "us")

CHEVRON = {
    "symbol": "CVX",
    "longName": "Chevron Corporation",
    "shortName": "Chevron Corp",
    "fullExchangeName": "NYSE",
    "exchange": "NYQ",
    "currency": "USD",
    "regularMarketPrice": 205.15,
    "regularMarketChangePercent": -1.17,
    "marketCap": 402422923264,
    "trailingPE": 19.74,
    "priceToBook": 2.12,
    "epsTrailingTwelveMonths": 10.39,
    "dividendYield": 3.47,
    "fiftyTwoWeekChangePercent": 36.89,
    "averageDailyVolume3Month": 8294373,
    "bid": 0.0,
    "sector": None,
    "messageBoardId": "finmb_98506",
}


@pytest.fixture
def fake_screen(monkeypatch):
    """Patch ``yf.screen``, record each call, answer with ``answer``."""
    calls: list[dict] = []
    answer = {"start": 0, "count": 1, "total": 1140, "quotes": [CHEVRON]}

    def screen(query, **kwargs):
        calls.append({"query": query.to_dict(), **kwargs})
        return answer

    monkeypatch.setattr(tickers.yf, "screen", screen)
    return calls


# --- the tables -----------------------------------------------------------


def test_every_alias_names_a_field_yahoo_knows():
    """A yfinance bump that renames a field fails here, not in a model's call."""
    known = {f for group in EQUITY_SCREENER_FIELDS.values() for f in group}
    assert set(screener.SCREEN_ALIASES.values()) <= known


@pytest.mark.parametrize("field", ["region", "exchange", "sector", "industry"])
def test_no_two_values_of_a_category_share_a_slug(field):
    """The tolerant match would otherwise pick one of them silently."""
    from yfinance.const import EQUITY_SCREENER_EQ_MAP

    raw = EQUITY_SCREENER_EQ_MAP[field]
    values = (
        {v for group in raw.values() for v in group} if isinstance(raw, dict) else raw
    )
    assert len(screener._CATEGORIES[field]) == len(set(values))


# --- the query ------------------------------------------------------------


def test_one_filter_goes_without_an_and(fake_screen):
    yahoo.screen((US,))
    assert fake_screen[0]["query"] == {"operator": "EQ", "operands": ["region", "us"]}


def test_several_filters_must_all_hold(fake_screen):
    yahoo.screen((US, ("dividend_yield", "btwn", [3, 4]), ("pe_ratio", "lt", 15)))
    query = fake_screen[0]["query"]
    assert query["operator"] == "AND"
    assert query["operands"] == [
        {"operator": "EQ", "operands": ["region", "us"]},
        {"operator": "BTWN", "operands": ["dividendyield", 3, 4]},
        {"operator": "LT", "operands": ["peratio.lasttwelvemonths", 15]},
    ]


def test_a_raw_field_name_is_accepted(fake_screen):
    yahoo.screen((("ebitda.lasttwelvemonths", "gt", 1e9),))
    assert fake_screen[0]["query"]["operands"] == ["ebitda.lasttwelvemonths", 1e9]


@pytest.mark.parametrize(
    "field,given,sent",
    [
        ("region", "US", "us"),
        ("exchange", "nyq", "NYQ"),
        ("sector", "financial-services", "Financial Services"),
        # get_sector's key and name both reach the screener's em-dash spelling.
        ("industry", "software-infrastructure", "Software—Infrastructure"),
        ("industry", "Software - Infrastructure", "Software—Infrastructure"),
    ],
)
def test_category_values_are_matched_as_yahoo_spells_them(
    fake_screen, field, given, sent
):
    yahoo.screen(((field, "eq", given),))
    assert fake_screen[0]["query"]["operands"] == [field, sent]


def test_every_industry_key_get_sector_knows_reaches_the_screener():
    """yfinance's key list writes 'oil-gas-e&p' and 'software—application'."""
    from yfinance.const import SECTOR_INDUSTY_MAPPING_LC

    keys = {k for group in SECTOR_INDUSTY_MAPPING_LC.values() for k in group}
    assert {screener._slug(k) for k in keys} == set(screener._CATEGORIES["industry"])


def test_is_in_becomes_a_list_of_values(fake_screen):
    yahoo.screen((("region", "is-in", ["de", "AT", "ch"]),))
    query = fake_screen[0]["query"]
    assert query["operator"] == "OR"
    assert [q["operands"][1] for q in query["operands"]] == ["de", "at", "ch"]


def test_sort_limit_and_offset_reach_yahoo(fake_screen):
    yahoo.screen((US,), sort_by="dividend_yield", sort_desc=False, limit=7, offset=50)
    call = fake_screen[0]
    assert call["sortField"] == "dividendyield"
    assert call["sortAsc"] is True
    assert call["size"] == 7
    assert call["offset"] == 50


def test_the_default_sort_is_market_cap_descending(fake_screen):
    yahoo.screen((US,))
    assert fake_screen[0]["sortField"] == "intradaymarketcap"
    assert fake_screen[0]["sortAsc"] is False


# --- the checks, each with its own message --------------------------------


@pytest.mark.parametrize(
    "filters,message",
    [
        ((), "At least one filter"),
        ((("pe", "lt", 15),), "Unknown screen field 'pe'. Use one of the aliases"),
        ((("pe_ratio", "below", 15),), "Use one of eq, gt, gte, lt, lte, btwn, is-in"),
        ((("sector", "gt", 3),), "is a category, compare it with eq or is-in"),
        ((("pe_ratio", "btwn", [15]),), "takes a list of two numbers"),
        ((("pe_ratio", "btwn", [20, 10]),), "the low bound 20 is above the high"),
        ((("region", "is-in", "us"),), "takes a non-empty list"),
        ((("region", "is-in", []),), "takes a non-empty list"),
        ((("pe_ratio", "lt", [15]),), "takes a single value, not a list"),
        ((("pe_ratio", "lt", "15"),), "is numeric, lt on it takes numbers"),
        ((("pe_ratio", "lt", True),), "is numeric"),
        ((("pe_ratio", "lt", float("nan")),), "is numeric"),
        ((("region", "eq", "xx"),), "Valid values: ae, ar,"),
        ((("industry", "eq", "widgets"),), "as get_sector lists them"),
    ],
)
def test_a_bad_filter_is_refused_before_yahoo(fake_screen, filters, message):
    with pytest.raises(ToolError, match=message.replace("(", r"\(")):
        yahoo.screen(filters)
    assert fake_screen == []


def test_sorting_by_a_category_is_refused(fake_screen):
    with pytest.raises(ToolError, match="Cannot sort by the category"):
        yahoo.screen((US,), sort_by="sector")
    assert fake_screen == []


# --- the answer -----------------------------------------------------------


def test_a_match_is_one_curated_row(fake_screen):
    out = yahoo.screen((US,))
    assert out["total"] == 1140
    assert out["count"] == 1
    assert out["offset"] == 0
    assert out["matches"] == [
        {
            "symbol": "CVX",
            "name": "Chevron Corporation",
            "exchange": "NYSE",
            "currency": "USD",
            "price": 205.15,
            "change_percent": -1.17,
            "market_cap": 402422923264,
            "pe_ratio": 19.74,
            "price_to_book": 2.12,
            "eps": 10.39,
            "dividend_yield": 3.47,
            "change_52w_percent": 36.89,
            "avg_volume_3m": 8294373,
        }
    ]


def test_missing_columns_are_left_out_and_names_fall_back(monkeypatch):
    sparse = {"symbol": "XYZ", "shortName": "Xyz Inc", "exchange": "PNK"}
    monkeypatch.setattr(
        tickers.yf,
        "screen",
        lambda q, **k: {"start": 0, "total": 1, "quotes": [sparse]},
    )
    out = yahoo.screen((US,))
    assert out["matches"] == [{"symbol": "XYZ", "name": "Xyz Inc", "exchange": "PNK"}]


def test_no_match_is_an_answer_not_an_error(monkeypatch):
    monkeypatch.setattr(
        tickers.yf, "screen", lambda q, **k: {"start": 0, "total": 0, "quotes": []}
    )
    assert yahoo.screen((US,)) == {"total": 0, "count": 0, "offset": 0, "matches": []}


def test_a_rate_limit_stays_a_rate_limit(monkeypatch):
    def limited(q, **k):
        raise YFRateLimitError()

    monkeypatch.setattr(tickers.yf, "screen", limited)
    with pytest.raises(RateLimitError):
        yahoo.screen((US,))


def test_an_upstream_failure_says_what_failed(monkeypatch):
    def broken(q, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(tickers.yf, "screen", broken)
    with pytest.raises(ToolError, match="Screen failed"):
        yahoo.screen((US,))


def test_the_same_screen_is_served_from_the_cache(fake_screen, tmp_path):
    cache.configure(Settings(cache_enabled=True, cache_dir=tmp_path))
    try:
        yahoo.screen((US, ("pe_ratio", "lt", 15)))
        yahoo.screen((("REGION", "eq", "US"), ("pe_ratio", "lt", 15)))
        assert len(fake_screen) == 1
    finally:
        cache.configure(Settings())
