"""Option chains, cut to the strikes around the money."""

from __future__ import annotations

from typing import Any

from .. import cache
from ..errors import SymbolNotFoundError, ToolError
from ..formatting import dataframe_to_records
from . import tickers

# Yahoo carries option chains for US-listed instruments only, so an empty
# result is the norm for the rest of the world rather than a sign of a bad
# symbol. Probed 2026-08-16: SAP.DE, NESN.SW and 7203.T all come back empty.
_NO_OPTIONS_REASON = (
    "Yahoo lists option chains for US-listed instruments only, so a non-US "
    "symbol is expected to have none."
)


@cache.cached("options")
def get_options(
    symbol: str,
    *,
    expiration: str | None = None,
    limit: int = 60,
) -> dict[str, Any]:
    """Return the option chain for ``symbol``.

    Without ``expiration`` the available expiration dates are returned. With an
    ``expiration`` (``YYYY-MM-DD``, one of the listed dates) the calls and puts
    for that date are returned, at most ``limit`` each, centred on the money.
    """
    # Checked as start and end are everywhere else: a stray space or a date
    # that is no date gets its own message, not "not available" and a list.
    if expiration:
        expiration = tickers.checked_date("expiration", expiration)
    ticker = tickers.get_ticker(symbol)
    with tickers.upstream(f"Failed to load options for {symbol!r}"):
        expirations = list(ticker.options or ())

    if not expirations:
        raise SymbolNotFoundError(symbol, reason=_NO_OPTIONS_REASON)

    if not expiration:
        return {"symbol": tickers.normalize(symbol), "expirations": expirations}

    if expiration not in expirations:
        raise ToolError(
            f"Expiration {expiration!r} is not available for {symbol!r}. "
            f"Available: {', '.join(expirations[:10])}"
            + (" ..." if len(expirations) > 10 else "")
        )

    with tickers.upstream(f"Failed to load option chain for {symbol!r} {expiration}"):
        chain = ticker.option_chain(expiration)

    calls, calls_cut = around_the_money(chain.calls, limit, itm_below=True)
    puts, puts_cut = around_the_money(chain.puts, limit, itm_below=False)
    return {
        "symbol": tickers.normalize(symbol),
        "expiration": expiration,
        "truncated": calls_cut or puts_cut,
        "calls": calls,
        "puts": puts,
    }


def around_the_money(
    df: Any, limit: int, *, itm_below: bool
) -> tuple[list[dict[str, Any]], bool]:
    """The ``limit`` contracts nearest the money, and whether any were cut.

    A chain comes sorted by strike, and a wide one (SPY has 300 strikes per
    expiry) used to be cut to its highest 60 strikes, which left out the
    region around the current price that most questions are about. The
    window is now centred where the contracts switch between in and out of
    the money. That needs no price: the chain says it per row. Calls are in
    the money below the price and puts above it, so for either side the
    number of strikes below the price is a count of ``inTheMoney``.
    """
    if df is None or df.empty:
        return [], False
    if "contractSymbol" in df.columns:
        # The frame's own index is a row counter. The contract symbol is what
        # names a row, so it takes the counter's place.
        df = df.set_index("contractSymbol")
    total = len(df)
    if total <= limit:
        return dataframe_to_records(df, max_rows=total), False
    if "inTheMoney" in df.columns:
        itm = int(df["inTheMoney"].fillna(False).astype(bool).sum())
        pivot = itm if itm_below else total - itm
    else:
        pivot = total // 2
    start = max(0, min(pivot - limit // 2, total - limit))
    window = df.iloc[start : start + limit]
    return dataframe_to_records(window, max_rows=limit), True
