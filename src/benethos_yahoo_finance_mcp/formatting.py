"""Helpers that turn pandas/yfinance output into compact, JSON-safe values.

yfinance returns rich ``pandas`` objects whose default serialization is large
and not JSON-safe (``NaN``, ``Timestamp``, numpy scalars). These helpers
produce small, deterministic structures suitable for an LLM context window.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd

# Hard cap on rows returned for any tabular result. Keeps responses within a
# reasonable token budget; tools may apply a tighter, purpose-specific limit.
MAX_ROWS = 250


def to_jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serializable form.

    Handles the types yfinance commonly emits: numpy scalars, pandas
    ``Timestamp``/``NaT``, ``NaN``/``inf`` floats, datetimes, and nested
    containers. Unknown objects fall back to ``str``.
    """
    # None / NaN / NaT -> null
    if value is None:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None

    # pandas missing-value sentinels (NaT, NA) — guarded because pd.isna on
    # arrays/containers raises or returns arrays.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]

    # numpy scalars expose .item()
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_jsonable(item())
        except (ValueError, TypeError):
            pass

    return str(value)


def _column_key(col: Any) -> str:
    """A column label as a JSON object key.

    Financial statements label their columns with the period end as a
    midnight ``Timestamp``, which ``str()`` renders as ``2025-09-30 00:00:00``.
    A plain ISO date says the same in ten characters, and every row repeats
    every key. Anything else goes through :func:`to_jsonable` first, so a
    timestamp with a time or a zone keeps its ISO form.
    """
    if (
        isinstance(col, datetime)
        and col.tzinfo is None
        and col.time() == datetime.min.time()
    ):
        return col.date().isoformat()
    key = to_jsonable(col)
    return key if isinstance(key, str) else str(key)


def dataframe_to_records(
    df: pd.DataFrame | None,
    *,
    max_rows: int = MAX_ROWS,
    index_name: str | None = None,
    head: bool = False,
) -> list[dict[str, Any]]:
    """Convert a DataFrame to a list of JSON-safe row dicts.

    The index is preserved as a column named ``index_name`` (or the frame's own
    index name, defaulting to ``"index"``). At most ``max_rows`` rows are kept.
    By default those are the tail, the most recent rows of a time series. Pass
    ``head=True`` for a frame ranked from the top, a holder list or a statement
    whose headline items come first. ``None`` and an empty frame both give an
    empty list, so callers need no guard of their own.
    """
    if df is None or df.empty:
        return []

    if len(df) > max_rows:
        frame = df.head(max_rows) if head else df.tail(max_rows)
    else:
        frame = df
    key = index_name or frame.index.name or "index"

    records: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        record: dict[str, Any] = {key: to_jsonable(idx)}
        for col, val in row.items():
            record[_column_key(col)] = to_jsonable(val)
        records.append(record)
    return records
