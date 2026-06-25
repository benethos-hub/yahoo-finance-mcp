"""Unit tests for the formatting helpers (no network access)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from yahoo_finance_mcp import formatting


def test_to_jsonable_handles_missing_and_special_floats():
    assert formatting.to_jsonable(None) is None
    assert formatting.to_jsonable(float("nan")) is None
    assert formatting.to_jsonable(float("inf")) is None
    assert formatting.to_jsonable(pd.NaT) is None


def test_to_jsonable_passthrough_scalars():
    assert formatting.to_jsonable("x") == "x"
    assert formatting.to_jsonable(3) == 3
    assert formatting.to_jsonable(True) is True
    assert formatting.to_jsonable(1.5) == 1.5


def test_to_jsonable_timestamps_become_iso():
    ts = pd.Timestamp("2024-01-02T03:04:05")
    assert formatting.to_jsonable(ts) == ts.isoformat()
    dt = datetime(2024, 1, 2, 3, 4, 5)
    assert formatting.to_jsonable(dt) == dt.isoformat()


def test_to_jsonable_recurses_into_containers():
    out = formatting.to_jsonable({"a": [1, float("nan")], "b": (2, 3)})
    assert out == {"a": [1, None], "b": [2, 3]}


def test_to_jsonable_numpy_scalar():
    import numpy as np

    assert formatting.to_jsonable(np.int64(7)) == 7
    assert formatting.to_jsonable(np.float64(2.5)) == 2.5


def test_to_jsonable_falls_back_to_str_for_unknown_objects():
    class NoItem:
        def __str__(self):
            return "custom-repr"

    # An object without a usable ``.item()`` falls back to ``str``.
    assert formatting.to_jsonable(NoItem()) == "custom-repr"


def test_to_jsonable_str_fallback_when_item_raises():
    class BadItem:
        def item(self):
            raise TypeError("no scalar")

        def __str__(self):
            return "bad-item"

    # A failing ``.item()`` is swallowed and we fall back to ``str``.
    assert formatting.to_jsonable(BadItem()) == "bad-item"


def test_dataframe_to_records_empty():
    assert formatting.dataframe_to_records(pd.DataFrame()) == []


def test_dataframe_to_records_preserves_index_and_columns():
    df = pd.DataFrame(
        {"Close": [10.0, 11.0]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="date"),
    )
    records = formatting.dataframe_to_records(df)
    assert records[0]["date"].startswith("2024-01-01")
    assert records[1]["Close"] == 11.0


def test_dataframe_to_records_truncates_to_tail():
    df = pd.DataFrame({"v": list(range(10))})
    records = formatting.dataframe_to_records(df, max_rows=3)
    assert len(records) == 3
    # Tail is kept, so the last value (9) must be present.
    assert records[-1]["v"] == 9


def test_dataframe_to_records_custom_index_name():
    df = pd.DataFrame({"v": [1]}, index=["Revenue"])
    records = formatting.dataframe_to_records(df, index_name="item")
    assert records[0]["item"] == "Revenue"
