"""The one door to yfinance's ``Ticker``, and what every group shares.

:func:`get_ticker` builds a fresh ``Ticker`` for every call, and
:func:`upstream` turns whatever yfinance raises into a ``ToolError``. The
group modules call both through this module, ``tickers.get_ticker(...)``,
never as a name imported from it, so a test that patches
``tickers.get_ticker`` reaches every group.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from ..errors import RateLimitError, SymbolNotFoundError, ToolError
from ..formatting import to_jsonable

# What a Yahoo symbol or an ISIN can look like once upper-cased: letters,
# digits and the few marks Yahoo uses, as in ^GSPC, EURUSD=X, BRK-B and
# M&M.NS. The symbol goes into the path of Yahoo's URLs, where a slash, a
# question mark or ".." has no business, and a name with a space is a case
# for the search tool anyway.
SYMBOL_MAX = 32
_SYMBOL_SHAPE = re.compile(rf"[A-Z0-9.\-^=&]{{1,{SYMBOL_MAX}}}")


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


_DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def checked_date(name: str, value: str) -> str:
    """``value`` if it is a real date written YYYY-MM-DD, else a ``ToolError``."""
    value = value.strip()
    try:
        if _DATE_SHAPE.fullmatch(value):
            date.fromisoformat(value)
            return value
    except ValueError:
        pass
    raise ToolError(f"Invalid {name} {value!r}, expected a date as YYYY-MM-DD.")


def checked_range(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    """``start`` and ``end`` as real dates, ``end`` after ``start`` when both are set.

    yfinance's ``end`` is exclusive: 2024-01-02 to 2024-01-02 is no day at all,
    and a range the wrong way round is none either. Yahoo answers both with no
    rows, which reads as an unknown symbol, so the order is checked first.
    """
    start = checked_date("start", start) if start else None
    end = checked_date("end", end) if end else None
    if start and end and end <= start:
        raise ToolError(
            f"end {end!r} must be after start {start!r}. end is exclusive: for "
            "one day, pass the day after it as end."
        )
    return start, end


def normalize(symbol: str) -> str:
    """The form a symbol is cached under and echoed back in."""
    return (symbol or "").strip().upper()


def get_ticker(symbol: str) -> yf.Ticker:
    """A new ``yf.Ticker`` for ``symbol``, upper-cased, never shared.

    The SDK runs the tools in worker threads, and a ``Ticker`` fills its
    lazily loaded fields without a lock, which yfinance promises nothing
    about. The objects used to be shared for 60 seconds, so two calls on one
    symbol could work on the same one at once. Building one sends no request
    for a ticker. An ISIN is looked up through Yahoo's search, and yfinance
    keeps that answer in a cache file of its own, so a repeat does not ask
    again.
    """
    key = normalize(symbol)
    if not key:
        raise ToolError("A non-empty symbol is required.")
    if not _SYMBOL_SHAPE.fullmatch(key):
        raise SymbolNotFoundError(key)

    # The constructor is the one yfinance call outside every upstream block.
    # An ISIN-shaped string Yahoo cannot resolve raises ValueError there,
    # which reached the model as a bare "Error executing tool".
    try:
        return yf.Ticker(key)
    except ValueError as exc:
        raise SymbolNotFoundError(key) from exc
    except Exception as exc:  # noqa: BLE001
        raise wrap_upstream(exc, f"Failed to resolve {key!r}") from exc


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
