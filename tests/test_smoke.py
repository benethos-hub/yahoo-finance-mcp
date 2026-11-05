"""What the smoke run's exit code says. The run itself needs Yahoo."""

from __future__ import annotations

import pytest

import smoke
from benethos_yahoo_finance_mcp.errors import RateLimitError


@pytest.mark.parametrize("value", [None, [], {}])
def test_an_empty_section_is_named(value):
    assert smoke.empty_fields(value) == [""]


def test_an_empty_field_is_named():
    section = {"symbol": "AAPL", "rows": [], "extra": {}, "price": 1.0}
    assert smoke.empty_fields(section) == ["rows", "extra"]


def test_a_null_figure_is_not_a_missing_section():
    """Yahoo leaves single figures out, as a market's status outside the US."""
    assert smoke.empty_fields({"key": "EUROPE", "status": None, "indices": [1]}) == []


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


def _fine():
    pass


def _limited():
    raise RateLimitError()


def test_a_run_with_data_exits_with_0(monkeypatch):
    monkeypatch.setattr(smoke, "_empty", [])
    assert smoke.verdict(_fine) == 0


def test_a_run_with_an_empty_section_exits_with_1(monkeypatch):
    monkeypatch.setattr(smoke, "_empty", ["get_quote: everything"])
    assert smoke.verdict(_fine) == 1


def test_a_rate_limit_has_a_code_of_its_own(monkeypatch):
    """It says nothing about the versions under test, so it must not read as a break."""
    monkeypatch.setattr(smoke, "_empty", [])
    assert smoke.verdict(_limited) == smoke.RATE_LIMITED
    assert smoke.RATE_LIMITED not in (0, 1, 2)  # 2 is argparse's own


def test_a_rate_limit_outweighs_what_came_back_empty_before_it(monkeypatch):
    monkeypatch.setattr(smoke, "_empty", ["get_quote: everything"])
    assert smoke.verdict(_limited) == smoke.RATE_LIMITED
