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
        if pd.isna(value):  # type: ignore[arg-type]
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


def dataframe_to_records(
    df: pd.DataFrame,
    *,
    max_rows: int = MAX_ROWS,
    index_name: str | None = None,
) -> list[dict[str, Any]]:
    """Convert a DataFrame to a list of JSON-safe row dicts.

    The index is preserved as a column named ``index_name`` (or the frame's own
    index name, defaulting to ``"index"``). At most ``max_rows`` rows are kept;
    when truncated, the most recent rows (the tail) are returned.
    """
    if df is None or df.empty:
        return []

    frame = df.tail(max_rows) if len(df) > max_rows else df
    key = index_name or frame.index.name or "index"

    records: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        record: dict[str, Any] = {key: to_jsonable(idx)}
        for col, val in row.items():
            record[str(col)] = to_jsonable(val)
        records.append(record)
    return records
