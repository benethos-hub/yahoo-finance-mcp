"""Who owns a company, who inside it trades, and what it files."""

from __future__ import annotations

from typing import Any

from .. import cache
from ..errors import SymbolNotFoundError
from ..formatting import dataframe_to_records, to_jsonable
from . import tickers


@cache.cached("holders")
def get_holders(symbol: str, *, limit: int = 25) -> dict[str, Any]:
    """Return the ownership breakdown for ``symbol``.

    Combines the high-level holder summary (insider/institutional percentages)
    with the top institutional and mutual-fund holders. Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load holders for {symbol!r}"):
        major = ticker.major_holders
        institutional = ticker.institutional_holders
        mutualfund = ticker.mutualfund_holders

    major_rows = dataframe_to_records(major, max_rows=10, index_name="metric")
    # Both lists are sorted largest-holder-first, so the cap keeps the head.
    institutional_rows = dataframe_to_records(institutional, max_rows=limit, head=True)
    mutualfund_rows = dataframe_to_records(mutualfund, max_rows=limit, head=True)
    if not major_rows and not institutional_rows and not mutualfund_rows:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": tickers.normalize(symbol),
        "major_holders": major_rows,
        "institutional_holders": institutional_rows,
        "mutualfund_holders": mutualfund_rows,
    }


@cache.cached("insider_activity")
def get_insider_activity(symbol: str, *, limit: int = 50) -> dict[str, Any]:
    """Return insider trading activity for ``symbol``.

    Combines individual insider transactions, a 6-month purchases/sales summary,
    and the current insider roster (with shares owned). Equity-only; empty for
    ETFs/funds/crypto.
    """
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load insider activity for {symbol!r}"):
        transactions = ticker.insider_transactions
        purchases = ticker.insider_purchases
        roster = ticker.insider_roster_holders

    # Transactions are newest-first, so the cap keeps the head.
    transactions_rows = dataframe_to_records(transactions, max_rows=limit, head=True)
    purchases_rows = dataframe_to_records(purchases, max_rows=10)
    roster_rows = dataframe_to_records(roster, max_rows=limit, head=True)
    if not transactions_rows and not purchases_rows and not roster_rows:
        raise SymbolNotFoundError(symbol)

    return {
        "symbol": tickers.normalize(symbol),
        "transactions": transactions_rows,
        "purchases_summary": purchases_rows,
        "roster": roster_rows,
    }


# Only issuers registered with the U.S. SEC file there. A German, Swiss or
# Japanese listing has no filings by construction, and neither do most
# ETFs/funds/crypto — none of which says anything about the symbol.
_NO_SEC_FILINGS_REASON = (
    "Only issuers registered with the U.S. SEC file there, so a non-US symbol "
    "is expected to have no filings. ETFs, funds and crypto have none either."
)


@cache.cached("sec_filings")
def get_sec_filings(symbol: str, *, limit: int = 25) -> dict[str, Any]:
    """Return recent SEC filings for ``symbol``.

    Each entry has the filing date, type (e.g. ``10-K``, ``10-Q``, ``8-K``),
    title, the Yahoo EDGAR URL, and exhibit links. Equity-only; empty for
    ETFs/funds/crypto.
    """
    limit = max(1, min(int(limit), 100))
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load SEC filings for {symbol!r}"):
        filings = ticker.sec_filings

    items: list[dict[str, Any]] = []
    for filing in list(filings or [])[:limit]:
        if not isinstance(filing, dict):
            continue
        items.append(
            {
                "date": to_jsonable(filing.get("date")),
                "type": filing.get("type"),
                "title": filing.get("title"),
                "url": filing.get("edgarUrl"),
                "exhibits": to_jsonable(filing.get("exhibits")),
            }
        )
    if not items:
        raise SymbolNotFoundError(symbol, reason=_NO_SEC_FILINGS_REASON)

    return {"symbol": tickers.normalize(symbol), "count": len(items), "filings": items}
