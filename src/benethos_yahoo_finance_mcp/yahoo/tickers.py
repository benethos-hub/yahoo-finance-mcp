"""The one door to yfinance's ``Ticker``, and what every group shares.

:func:`get_ticker` builds a fresh ``Ticker`` for every call, and
:func:`upstream` turns whatever yfinance raises into a ``ToolError``. The
group modules call both through this module, ``tickers.get_ticker(...)``,
never as a name imported from it, so a test that patches
``tickers.get_ticker`` reaches every group.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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
