"""Unit tests for the command-line interface / transport selection."""

from __future__ import annotations

import pytest

from yahoo_finance_mcp import server


def test_defaults_to_stdio():
    args = server._build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path is None
    assert args.log_level == "INFO"


def test_parses_http_options():
    args = server._build_parser().parse_args(
        ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"]
    )
    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_rejects_unknown_transport():
    with pytest.raises(SystemExit):
        server._build_parser().parse_args(["--transport", "carrier-pigeon"])


def test_main_runs_stdio_by_default(monkeypatch):
    called = {}
    monkeypatch.setattr(
        server.mcp, "run", lambda transport: called.setdefault("t", transport)
    )
    server.main([])
    assert called["t"] == "stdio"


def test_main_applies_http_settings(monkeypatch):
    called = {}
    monkeypatch.setattr(
        server.mcp, "run", lambda transport: called.setdefault("t", transport)
    )
    server.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9001",
            "--path",
            "/yf",
        ]
    )
    assert called["t"] == "streamable-http"
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 9001
    assert server.mcp.settings.streamable_http_path == "/yf"


def test_main_applies_sse_path(monkeypatch):
    monkeypatch.setattr(server.mcp, "run", lambda transport: None)
    server.main(["--transport", "sse", "--path", "/events"])
    assert server.mcp.settings.sse_path == "/events"
