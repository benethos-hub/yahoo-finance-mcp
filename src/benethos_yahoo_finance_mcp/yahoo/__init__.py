"""Everything this server asks Yahoo, through yfinance, grouped by subject.

Each module here has a twin of the same name in ``tools``, which exposes its
functions to the client. Only this package imports yfinance. The functions
return plain, JSON-safe values and raise ``ToolError`` subclasses, so a tool
has nothing left to do but hand the result on.
"""

from __future__ import annotations

from . import tickers
from .analysts import (
    CHANGES_MAX,
    EARNINGS_MAX,
    EPS_METHODOLOGIES,
    get_earnings,
    get_estimates,
    get_recommendations,
    get_upgrades_downgrades,
)
from .browse import (
    COMPANIES_MAX,
    MARKET_KEYS,
    SECTOR_KEYS,
    get_industry,
    get_market,
    get_sector,
)
from .company import (
    NEWS_MAX,
    SHARES_MAX,
    get_calendar,
    get_company_info,
    get_dividends,
    get_financials,
    get_news,
    get_shares,
)
from .funds import HOLDINGS_MAX, get_fund_data
from .options import STRIKES_MAX, get_options
from .ownership import (
    FILINGS_MAX,
    HOLDERS_MAX,
    INSIDER_MAX,
    get_holders,
    get_insider_activity,
    get_sec_filings,
)
from .quotes import (
    INTERVALS,
    PERIODS,
    QUERY_MAX,
    QUOTES_MAX,
    SEARCH_MAX,
    get_history,
    get_quote,
    get_quotes,
    search,
)
from .screener import (
    OFFSET_MAX,
    SCREEN_ALIASES,
    SCREEN_MAX,
    SCREEN_OPERATORS,
    screen,
)
from .tickers import SYMBOL_MAX, last_answer

__all__ = [
    "CHANGES_MAX",
    "COMPANIES_MAX",
    "EARNINGS_MAX",
    "EPS_METHODOLOGIES",
    "FILINGS_MAX",
    "HOLDERS_MAX",
    "HOLDINGS_MAX",
    "INSIDER_MAX",
    "INTERVALS",
    "MARKET_KEYS",
    "NEWS_MAX",
    "OFFSET_MAX",
    "PERIODS",
    "QUERY_MAX",
    "QUOTES_MAX",
    "SCREEN_ALIASES",
    "SCREEN_MAX",
    "SCREEN_OPERATORS",
    "SEARCH_MAX",
    "SECTOR_KEYS",
    "SHARES_MAX",
    "STRIKES_MAX",
    "SYMBOL_MAX",
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
    "last_answer",
    "screen",
    "search",
    "tickers",
]
