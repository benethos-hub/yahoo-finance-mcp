"""How a line looks: plain for a file or a container log, in colour at a terminal."""

from __future__ import annotations

import logging
import re
import sys

import pytest

from benethos_yahoo_finance_mcp.logbook import formats, output

PACKAGE = "benethos_yahoo_finance_mcp"


def _record(name: str, level: int, msg: str, args: tuple = ()) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, msg, args, None)


def _request(status: int) -> logging.LogRecord:
    return _record(
        "uvicorn.access",
        logging.INFO,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.7:5555", "POST", "/mcp", "1.1", status),
    )


class TestPlain:
    def test_the_time_has_a_point_before_the_milliseconds_and_an_offset(self):
        line = formats.Plain().format(_record(PACKAGE, logging.INFO, "Started"))
        assert re.match(
            r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}[+-]\d\d:\d\d INFO     "
            rf"{PACKAGE}: Started$",
            line,
        ), line

    def test_the_full_logger_name_and_no_colour(self):
        line = formats.Plain().format(_record("uvicorn.error", logging.INFO, "Up"))
        assert " INFO     uvicorn.error: Up" in line
        assert "\033[" not in line


class TestConsole:
    def test_a_line_in_colour_with_a_short_source(self):
        record = _record(f"{PACKAGE}.tools", logging.WARNING, "get_quote failed")
        line = formats.Console().format(record)
        assert re.match(
            r"\033\[2m\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}\033\[0m "
            r"\033\[33mWARNING \033\[0m \033\[36mtools   \033\[0m get_quote failed$",
            line,
        ), repr(line)

    def test_the_server_log_of_uvicorn_is_not_called_error(self):
        line = formats.Console().format(_record("uvicorn.error", logging.INFO, "Up"))
        assert "uvicorn " in line
        assert "error" not in line

    def test_a_request_names_method_path_and_status_in_colour(self):
        line = formats.Console().format(_request(401))
        assert line.endswith(
            "POST /mcp \033[31m401 Unauthorized\033[0m \033[2m10.0.0.7:5555\033[0m"
        )
        assert "\033[36mhttp    \033[0m" in line

    def test_a_traceback_is_kept(self):
        try:
            raise ValueError("boom")
        except ValueError:
            record = _record(PACKAGE, logging.ERROR, "failed")
            record.exc_info = sys.exc_info()
        line = formats.Console().format(record)
        assert "failed\nTraceback (most recent call last):" in line
        assert line.endswith("ValueError: boom")


@pytest.mark.parametrize(
    "name,short",
    [
        (PACKAGE, "server"),
        (f"{PACKAGE}.tools", "tools"),
        (f"{PACKAGE}.cache", "cache"),
        ("uvicorn.access", "http"),
        ("uvicorn.error", "uvicorn"),
        ("uvicorn", "uvicorn"),
        ("mcp.server", "mcp.server"),
    ],
)
def test_short_source(name, short):
    assert formats.short_source(name) == short


def test_every_source_of_this_server_fits_the_column():
    names = [PACKAGE, "uvicorn.access", "uvicorn.error"] + [
        f"{PACKAGE}.{sub}" for sub in ("tools", "yahoo", "cache")
    ]
    assert max(len(formats.short_source(n)) for n in names) <= formats.SOURCE_WIDTH


class _Stream:
    def __init__(self, tty: bool) -> None:
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


def test_colours_on_a_terminal_unless_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys, "stderr", _Stream(True))
    assert formats.colours_wanted()
    monkeypatch.setenv("NO_COLOR", "1")
    assert not formats.colours_wanted()
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(sys, "stderr", _Stream(False))
    assert not formats.colours_wanted()


@pytest.mark.parametrize("tty,kind", [(True, formats.Console), (False, formats.Plain)])
def test_the_handler_takes_the_format_for_where_stderr_goes(monkeypatch, tty, kind):
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(formats.sys.stderr, "isatty", lambda: tty, raising=False)
    output.configure("INFO")
    [handler] = root.handlers
    assert type(handler.formatter) is kind
