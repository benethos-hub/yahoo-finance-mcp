"""Screening the stock market by criteria."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, Field, StrictFloat

from .. import yahoo
from ._base import register_tool

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer

_Text = Annotated[str, Field(max_length=64)]
# Strict, so a JSON true is refused instead of passing as 1.0. Whole numbers
# still pass.
_Number = StrictFloat


class ScreenFilter(BaseModel):
    """One condition a stock has to meet."""

    field: _Text = Field(description="An alias or a raw Yahoo screener field.")
    op: Literal["eq", "gt", "gte", "lt", "lte", "btwn", "is-in"]
    value: _Number | _Text | Annotated[list[_Number | _Text], Field(max_length=50)] = (
        Field(description="A number, [low, high] for btwn, a list for is-in.")
    )


def screen(
    filters: Annotated[
        list[ScreenFilter],
        Field(
            description="Conditions that must all hold, e.g. "
            '[{"field": "dividend_yield", "op": "gt", "value": 3}].',
            max_length=10,
        ),
    ],
    sort_by: Annotated[
        str, Field(description="A numeric field or alias to sort by.", max_length=64)
    ] = "market_cap",
    sort_desc: Annotated[bool, Field(description="Largest first.")] = True,
    limit: Annotated[
        int, Field(description="Maximum number of matches to return.", ge=1, le=100)
    ] = 25,
    offset: Annotated[
        int, Field(description="Matches to skip, for the next page.", ge=0, le=9900)
    ] = 0,
) -> dict[str, Any]:
    """Find stocks by criteria, e.g. dividend payers in a region or cheap large caps.

    Fields are these aliases, or a raw Yahoo screener field name:
    - market: market_cap, price, change_percent, change_52w_percent, volume,
      avg_volume_3m, beta
    - valuation: pe_ratio, peg_ratio, price_to_book, price_to_sales, ev_to_ebitda
    - dividend: dividend_yield, forward_dividend_yield, dividend_growth_years
    - profitability and growth: return_on_equity, return_on_assets, net_margin,
      revenue, revenue_growth, eps_growth
    - balance sheet: debt_to_equity, current_ratio
    - ownership: insider_percent, institutional_percent, short_percent_of_float
    - esg_score
    - categories, eq or is-in only: region (country code, 'us', 'de'), exchange
      (Yahoo code, 'NMS', 'GER'), sector ('Technology'), industry (a key or
      name from get_sector)

    Percentages are in percent, 3 means 3 %. A loss makes pe_ratio negative,
    so pair lt with gt 0. region is where a stock is listed, not where the
    company sits, so 'de' includes foreign companies traded in Germany, and a
    company appears once per listing. Returns total (all matches) and one row
    per match with price, valuation and dividend figures. A row's
    dividend_yield can be missing or differ markedly from the filter, which
    holds for Yahoo's screener data, not for that column. The figures behind
    the other filters are in get_company_info.
    """
    return yahoo.screen(
        tuple(
            (f.field, f.op, tuple(f.value) if isinstance(f.value, list) else f.value)
            for f in filters
        ),
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=limit,
        offset=offset,
    )


def register(server: MCPServer) -> None:
    """Add this module's tools to ``server``, in listing order."""
    register_tool(server, screen)
