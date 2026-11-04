"""What the smoke run counts as an empty answer. The run itself needs Yahoo."""

from __future__ import annotations

import pytest

from smoke import empty_fields


@pytest.mark.parametrize("value", [None, [], {}])
def test_an_empty_section_is_named(value):
    assert empty_fields(value) == [""]


def test_an_empty_field_is_named():
    section = {"symbol": "AAPL", "rows": [], "extra": {}, "price": 1.0}
    assert empty_fields(section) == ["rows", "extra"]


def test_a_null_figure_is_not_a_missing_section():
    """Yahoo leaves single figures out, as a market's status outside the US."""
    assert empty_fields({"key": "EUROPE", "status": None, "indices": [1]}) == []
