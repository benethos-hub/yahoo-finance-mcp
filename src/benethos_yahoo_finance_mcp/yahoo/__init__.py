"""Everything this server asks Yahoo, through yfinance, grouped by subject.

Each module here has a twin of the same name in ``tools``, which exposes its
functions to the client. Only this package imports yfinance. The functions
return plain, JSON-safe values and raise ``ToolError`` subclasses, so a tool
has nothing left to do but hand the result on.
"""

from __future__ import annotations

from . import tickers
from .analysts import (
    get_earnings,
    get_estimates,
    get_recommendations,
    get_upgrades_downgrades,
)
from .browse import (
    INDUSTRY_KEYS,
    MARKET_KEYS,
    SECTOR_KEYS,
    get_industry,
    get_market,
    get_sector,
)
from .company import (
    get_calendar,
    get_company_info,
    get_dividends,
    get_financials,
    get_news,
    get_shares,
)
from .funds import get_fund_data
from .options import get_options
from .ownership import get_holders, get_insider_activity, get_sec_filings
from .quotes import INTERVALS, PERIODS, get_history, get_quote, get_quotes, search
from .screener import SCREEN_ALIASES, SCREEN_OPERATORS, screen

__all__ = [
    "INDUSTRY_KEYS",
    "INTERVALS",
    "MARKET_KEYS",
    "PERIODS",
    "SCREEN_ALIASES",
    "SCREEN_OPERATORS",
    "SECTOR_KEYS",
    "get_calendar",
    "get_company_info",
    "get_dividends",
    "get_earnings",
    "get_estimates",
    "get_financials",
    "get_fund_data",
    "get_history",
    "get_holders",
    "get_industry",
    "get_insider_activity",
    "get_market",
    "get_news",
    "get_options",
    "get_quote",
    "get_quotes",
    "get_recommendations",
    "get_sec_filings",
    "get_sector",
    "get_shares",
    "get_upgrades_downgrades",
    "screen",
    "search",
    "tickers",
]
