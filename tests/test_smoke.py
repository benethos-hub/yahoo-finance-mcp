"""What the smoke run counts as an empty answer. The run itself needs Yahoo."""

from __future__ import annotations

import pytest

import smoke
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


def test_a_pause_follows_every_section(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(smoke.time, "sleep", slept.append)
    monkeypatch.setattr(smoke, "_pause", 1.0)
    smoke.show("one", {"rows": [1]})
    smoke.show("two", {"rows": [1]})
    assert slept == [1.0, 1.0]


def test_no_pause_by_default(monkeypatch):
    def never(seconds):  # pragma: no cover - must not be reached
        raise AssertionError("slept")

    monkeypatch.setattr(smoke.time, "sleep", never)
    smoke.show("one", {"rows": [1]})


def test_the_pause_comes_from_the_command_line():
    assert smoke.pause_from(["--pause", "1"]) == 1.0
    assert smoke.pause_from([]) == 0.0
