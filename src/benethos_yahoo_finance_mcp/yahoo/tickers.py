"""The one door to yfinance's ``Ticker``, and what every group shares.

:func:`get_ticker` hands out ``Ticker`` objects from a short-lived, bounded
cache, so a burst of related calls asks Yahoo once. :func:`upstream` turns
whatever yfinance raises into a ``ToolError``. The group modules call both
through this module, ``tickers.get_ticker(...)``, never as a name imported
from it, so a test that patches ``tickers.get_ticker`` reaches every group.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from ..errors import RateLimitError, SymbolNotFoundError, ToolError
from ..formatting import to_jsonable


def wrap_upstream(exc: Exception, message: str) -> ToolError:
    """Normalize an upstream yfinance exception into a ``ToolError``.

    Rate limiting gets a dedicated, actionable message; any other failure keeps
    the operation-specific context so the client knows what was being attempted.
    """
    if isinstance(exc, YFRateLimitError):
        return RateLimitError()
    return ToolError(f"{message}: {exc}")


@contextmanager
def upstream(message: str) -> Iterator[None]:
    """Run a block of yfinance calls, normalising whatever it raises.

    ``message`` says what was being attempted and ends up in the error the
    client sees, see :func:`wrap_upstream`.
    """
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - normalize upstream errors
        raise wrap_upstream(exc, message) from exc


def normalize(symbol: str) -> str:
    """The form a symbol is cached under and echoed back in."""
    return (symbol or "").strip().upper()


# Time-to-live for cached Ticker objects, in seconds. Short enough that quotes
# stay fresh, long enough to coalesce bursts of related tool calls.
_TICKER_TTL = 60.0

# Upper bound on cached Ticker objects. Each one keeps whatever it has loaded,
# price history and statements included, so an unbounded cache grows with every
# distinct symbol ever asked for. Over HTTP that is a caller's choice, and one
# get_quotes call names 50 at a time. Least recently used goes first.
_TICKER_CACHE_MAX = 256

_ticker_cache: OrderedDict[str, tuple[float, yf.Ticker]] = OrderedDict()
_cache_lock = Lock()


def get_ticker(symbol: str) -> yf.Ticker:
    """Return a cached ``yf.Ticker`` for ``symbol`` (case-insensitive key)."""
    key = normalize(symbol)
    if not key:
        raise ToolError("A non-empty symbol is required.")

    now = time.monotonic()
    with _cache_lock:
        cached = _ticker_cache.get(key)
        if cached is not None and now - cached[0] < _TICKER_TTL:
            _ticker_cache.move_to_end(key)
            return cached[1]

    # Built outside the lock. For anything shaped like an ISIN the constructor
    # resolves it with a search request on the spot, and holding the lock
    # through that would stall every other tool call in the meantime. Two
    # threads may occasionally both build the same ticker, and the later one
    # simply wins the slot.
    #
    # The constructor is also the one yfinance call that sat outside every
    # try block. An ISIN-shaped string Yahoo cannot resolve raises ValueError
    # there, which reached the model as a bare "Error executing tool".
    try:
        ticker = yf.Ticker(key)
    except ValueError as exc:
        raise SymbolNotFoundError(key) from exc
    except Exception as exc:  # noqa: BLE001
        raise wrap_upstream(exc, f"Failed to resolve {key!r}") from exc

    with _cache_lock:
        _ticker_cache[key] = (now, ticker)
        _ticker_cache.move_to_end(key)
        _evict_tickers(now)
    return ticker


def _evict_tickers(now: float) -> None:
    """Drop expired entries, then the least recently used beyond the cap.

    Called with the lock held. Expired entries are not ordered by age, since a
    hit moves an entry to the end without renewing it, so they are found by a
    full pass. At a few hundred entries that costs nothing.
    """
    for key in [k for k, (t, _) in _ticker_cache.items() if now - t >= _TICKER_TTL]:
        del _ticker_cache[key]
    while len(_ticker_cache) > _TICKER_CACHE_MAX:
        _ticker_cache.popitem(last=False)


def fast_fields(fast: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Read ``fields`` from a ``fast_info``, JSON-safe, ``None`` where missing.

    Some fields raise instead of returning nothing when Yahoo lacks them, and
    one missing field must not cost the rest. A rate limit is the exception,
    since every further field would hit it too.
    """
    out: dict[str, Any] = {}
    for field in fields:
        try:
            value = fast.get(field)
        except YFRateLimitError as exc:
            raise RateLimitError() from exc
        except Exception:  # noqa: BLE001 - some fields raise when unavailable
            value = None
        out[field] = to_jsonable(value)
    return out
