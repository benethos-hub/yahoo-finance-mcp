"""Unit tests for the command-line interface / transport selection."""

from __future__ import annotations

import pytest

from benethos_yahoo_finance_mcp import server


def test_defaults_to_stdio():
    args = server._build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path is None
    assert args.log_level == "INFO"


def test_default_log_level_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "debug")  # case-insensitive
    assert server._default_log_level() == "DEBUG"
    # The parser picks up the env-derived default.
    args = server._build_parser().parse_args([])
    assert args.log_level == "DEBUG"


def test_default_log_level_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "bogus")
    assert server._default_log_level() == "INFO"


def test_explicit_log_level_overrides_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "DEBUG")
    args = server._build_parser().parse_args(["--log-level", "ERROR"])
    assert args.log_level == "ERROR"


def test_transport_host_port_path_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("YF_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("YF_MCP_PORT", "9000")
    monkeypatch.setenv("YF_MCP_PATH", "/yf")
    args = server._build_parser().parse_args([])
    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/yf"


def test_invalid_env_transport_and_port_fall_back(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "carrier-pigeon")
    monkeypatch.setenv("YF_MCP_PORT", "not-a-number")
    assert server._default_transport() == "stdio"
    assert server._default_port() == 8000


def test_explicit_flags_override_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "sse")
    monkeypatch.setenv("YF_MCP_PORT", "9000")
    args = server._build_parser().parse_args(
        ["--transport", "streamable-http", "--port", "8123"]
    )
    assert args.transport == "streamable-http"
    assert args.port == 8123


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


def _capture_run(monkeypatch):
    """Replace ``mcp.run`` with a spy and return the dict it records into.

    The server passes every transport option to ``run`` as a keyword argument,
    so capturing the call is what verifies the wiring.
    """
    called: dict = {}

    def fake_run(transport, **kwargs):
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(server.mcp, "run", fake_run)
    return called


def test_main_runs_stdio_by_default(monkeypatch):
    called = _capture_run(monkeypatch)
    server.main([])
    assert called["transport"] == "stdio"
    # stdio takes no host, port or path.
    assert called["kwargs"] == {}


def test_main_applies_http_settings(monkeypatch):
    called = _capture_run(monkeypatch)
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
    assert called["transport"] == "streamable-http"
    assert called["kwargs"]["host"] == "0.0.0.0"
    assert called["kwargs"]["port"] == 9001
    assert called["kwargs"]["streamable_http_path"] == "/yf"


def test_main_applies_sse_path(monkeypatch):
    called = _capture_run(monkeypatch)
    server.main(["--transport", "sse", "--path", "/events"])
    assert called["kwargs"]["sse_path"] == "/events"


def test_http_transports_get_their_default_path(monkeypatch):
    called = _capture_run(monkeypatch)
    server.main(["--transport", "streamable-http"])
    assert called["kwargs"]["streamable_http_path"] == "/mcp"

    called = _capture_run(monkeypatch)
    server.main(["--transport", "sse"])
    assert called["kwargs"]["sse_path"] == "/sse"


# --- DNS-rebinding guard / allowed hosts ------------------------------------


def test_allowed_host_options_default_to_none():
    args = server._build_parser().parse_args([])
    assert args.allowed_hosts is None
    assert args.allowed_origins is None


def test_allowed_hosts_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_ALLOWED_HOSTS", "a:8000, b:8000")
    monkeypatch.setenv("YF_MCP_ALLOWED_ORIGINS", "http://a:8000")
    args = server._build_parser().parse_args([])
    assert args.allowed_hosts == "a:8000, b:8000"
    assert args.allowed_origins == "http://a:8000"


def test_split_csv():
    assert server._split_csv(None) == []
    assert server._split_csv("") == []
    assert server._split_csv(" a , b ,,c ") == ["a", "b", "c"]


def test_transport_security_localhost_keeps_protection():
    ts = server._transport_security_for("127.0.0.1", [], [])
    assert ts.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in ts.allowed_hosts


def test_transport_security_exposed_bind_disables_protection():
    ts = server._transport_security_for("0.0.0.0", [], [])
    assert ts.enable_dns_rebinding_protection is False


def test_transport_security_explicit_allow_list_wins_even_when_exposed():
    ts = server._transport_security_for("0.0.0.0", ["mcp:8000"], [])
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["mcp:8000"]
    # Origins are derived from the hosts when not given explicitly.
    assert ts.allowed_origins == ["http://mcp:8000", "https://mcp:8000"]


def test_transport_security_explicit_origins_are_kept():
    ts = server._transport_security_for("0.0.0.0", ["mcp:8000"], ["http://mcp:8000"])
    assert ts.allowed_origins == ["http://mcp:8000"]


def test_main_exposed_bind_disables_rebinding_guard(monkeypatch):
    called = _capture_run(monkeypatch)
    server.main(["--transport", "streamable-http", "--host", "0.0.0.0"])
    ts = called["kwargs"]["transport_security"]
    assert ts.enable_dns_rebinding_protection is False


def test_stdio_gets_no_transport_security(monkeypatch):
    """stdio has no HTTP surface, so it must not be handed a guard at all."""
    called = _capture_run(monkeypatch)
    server.main([])
    assert "transport_security" not in called["kwargs"]


def test_main_allowed_hosts_enables_guard_with_list(monkeypatch):
    called = _capture_run(monkeypatch)
    server.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--allowed-hosts",
            "benethos-yahoo-finance-mcp:8000",
        ]
    )
    ts = called["kwargs"]["transport_security"]
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["benethos-yahoo-finance-mcp:8000"]


def test_version_flag_prints_the_package_version(capsys):
    """`--version` exits straight away and reports the installed version.

    The same value the server reports in the MCP handshake, which otherwise
    needs a session to reach. Anyone running this from a container has no
    `pip show` to fall back on.
    """
    from benethos_yahoo_finance_mcp import __version__

    with pytest.raises(SystemExit) as exit_info:
        server._build_parser().parse_args(["--version"])

    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"benethos-yahoo-finance-mcp {__version__}"


def test_version_flag_agrees_with_the_handshake():
    """The two places a version is published must not drift apart."""
    from benethos_yahoo_finance_mcp import __version__

    assert server.mcp.version == __version__
