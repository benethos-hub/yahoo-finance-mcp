"""Unit tests for the command-line interface / transport selection."""

from __future__ import annotations

import pytest
from mcp.server.mcpserver import MCPServer

from benethos_yahoo_finance_mcp import cli, settings
from benethos_yahoo_finance_mcp.server import build_server
from benethos_yahoo_finance_mcp.transport import http as http_transport


def _settings(argv):
    """What a command line resolves to, against the test's environment."""
    return cli.parse_settings(argv)


def test_defaults_to_stdio():
    args = _settings([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path is None
    assert args.log_level == "INFO"


def test_default_log_level_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "debug")  # case-insensitive
    assert _settings([]).log_level == "DEBUG"
    # The parser picks up the env-derived default.
    args = _settings([])
    assert args.log_level == "DEBUG"


def test_default_log_level_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "bogus")
    assert _settings([]).log_level == "INFO"


def test_explicit_log_level_overrides_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_LOG_LEVEL", "DEBUG")
    args = _settings(["--log-level", "ERROR"])
    assert args.log_level == "ERROR"


def test_transport_host_port_path_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("YF_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("YF_MCP_PORT", "9000")
    monkeypatch.setenv("YF_MCP_PATH", "/yf")
    args = _settings([])
    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/yf"


def test_invalid_env_transport_and_port_fall_back(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "carrier-pigeon")
    monkeypatch.setenv("YF_MCP_PORT", "not-a-number")
    resolved = _settings([])
    assert resolved.transport == "stdio"
    assert resolved.port == 8000


def test_explicit_flags_override_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_TRANSPORT", "sse")
    monkeypatch.setenv("YF_MCP_PORT", "9000")
    args = _settings(["--transport", "streamable-http", "--port", "8123"])
    assert args.transport == "streamable-http"
    assert args.port == 8123


def test_parses_http_options():
    args = _settings(
        ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"]
    )
    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_parses_the_cache_limit():
    assert _settings(["--cache-max-entries", "250"]).cache_max_entries == 250
    assert _settings([]).cache_max_entries == settings.CACHE_MAX_ENTRIES


@pytest.mark.parametrize("value", ["0", "-3", "many"])
def test_rejects_a_cache_limit_below_one(capsys, value):
    with pytest.raises(SystemExit) as info:
        _settings(["--cache-max-entries", value])
    assert info.value.code == 2
    assert "--cache-max-entries" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv,env", [(["--path", "mcp"], None), ([], "mcp")], ids=["flag", "env"]
)
def test_a_path_without_a_leading_slash_is_a_usage_error(
    monkeypatch, capsys, argv, env
):
    """Starlette asserted on it after the start line had already been logged."""
    if env:
        monkeypatch.setenv("YF_MCP_PATH", env)
    with pytest.raises(SystemExit) as info:
        _settings(["--transport", "streamable-http", *argv])
    assert info.value.code == 2
    assert "--path must start with '/'" in capsys.readouterr().err


def test_rejects_unknown_transport():
    with pytest.raises(SystemExit):
        _settings(["--transport", "carrier-pigeon"])


def _capture_run(monkeypatch):
    """Replace ``server.run`` with a spy and return the dict it records into.

    Only stdio still goes through ``run``. The HTTP transports are built and
    served here so that the bearer guard has somewhere to sit, and are captured
    by ``_capture_http`` instead.
    """
    called: dict = {}

    def fake_run(self, transport, **kwargs):
        called["transport"] = transport
        called["kwargs"] = kwargs

    monkeypatch.setattr(MCPServer, "run", fake_run)
    return called


def _capture_http(monkeypatch):
    """Replace the HTTP app builder and the server loop with spies.

    Without this a test would build a real app and hand it to uvicorn, which
    binds a port and never returns.
    """
    monkeypatch.delenv(settings.TOKEN_VAR, raising=False)
    called: dict = {}

    def fake_http_app(mcp_server, **kwargs):
        called["app_kwargs"] = kwargs
        return "the-app"

    def fake_run_http(app, **kwargs):
        called["app"] = app
        called["run_kwargs"] = kwargs

    monkeypatch.setattr(http_transport, "http_app", fake_http_app)
    monkeypatch.setattr(http_transport, "serve", fake_run_http)
    return called


@pytest.mark.parametrize("port", ["0", "65536", "-1"])
def test_http_rejects_a_port_out_of_range(monkeypatch, capsys, port):
    """A bad port is a usage error, not a uvicorn traceback."""
    called = _capture_http(monkeypatch)
    with pytest.raises(SystemExit) as info:
        cli.main(["--transport", "streamable-http", "--port", port])
    assert info.value.code == 2
    assert "--port must be between 1 and 65535" in capsys.readouterr().err
    assert "app" not in called


def test_http_rejects_an_env_port_out_of_range(monkeypatch):
    _capture_http(monkeypatch)
    monkeypatch.setenv("YF_MCP_PORT", "99999")
    with pytest.raises(SystemExit):
        cli.main(["--transport", "streamable-http"])


def test_stdio_ignores_the_port(monkeypatch):
    called = _capture_run(monkeypatch)
    cli.main(["--port", "0"])
    assert called["transport"] == "stdio"


def test_main_runs_stdio_by_default(monkeypatch):
    called = _capture_run(monkeypatch)
    cli.main([])
    assert called["transport"] == "stdio"
    # stdio takes no host, port or path.
    assert called["kwargs"] == {}


def test_main_applies_http_settings(monkeypatch):
    called = _capture_http(monkeypatch)
    cli.main(
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
    assert called["app_kwargs"]["transport"] == "streamable-http"
    assert called["app_kwargs"]["host"] == "0.0.0.0"
    assert called["app_kwargs"]["path"] == "/yf"
    assert called["run_kwargs"]["host"] == "0.0.0.0"
    assert called["run_kwargs"]["port"] == 9001
    assert called["app"] == "the-app"


def test_main_applies_sse_path(monkeypatch):
    called = _capture_http(monkeypatch)
    cli.main(["--transport", "sse", "--path", "/events"])
    assert called["app_kwargs"]["path"] == "/events"


def test_http_transports_get_their_default_path(monkeypatch):
    called = _capture_http(monkeypatch)
    cli.main(["--transport", "streamable-http"])
    assert called["app_kwargs"]["path"] == "/mcp"

    called = _capture_http(monkeypatch)
    cli.main(["--transport", "sse"])
    assert called["app_kwargs"]["path"] == "/sse"


# --- DNS-rebinding guard / allowed hosts ------------------------------------


def test_allowed_host_options_default_to_empty():
    args = _settings([])
    assert args.allowed_hosts == ()
    assert args.allowed_origins == ()


def test_allowed_hosts_from_env(monkeypatch):
    monkeypatch.setenv("YF_MCP_ALLOWED_HOSTS", "a:8000, b:8000")
    monkeypatch.setenv("YF_MCP_ALLOWED_ORIGINS", "http://a:8000")
    args = _settings([])
    assert args.allowed_hosts == ("a:8000", "b:8000")
    assert args.allowed_origins == ("http://a:8000",)


def test_split_csv():
    assert settings.split_csv(None) == ()
    assert settings.split_csv("") == ()
    assert settings.split_csv(" a , b ,,c ") == ("a", "b", "c")


def test_the_host_from_the_environment_is_trimmed(monkeypatch):
    monkeypatch.setenv("YF_MCP_HOST", " 127.0.0.1 ")
    assert _settings([]).host == "127.0.0.1"
    monkeypatch.setenv("YF_MCP_HOST", "  ")
    assert _settings([]).host == "127.0.0.1"


def test_main_exposed_bind_disables_rebinding_guard(monkeypatch):
    called = _capture_http(monkeypatch)
    cli.main(["--transport", "streamable-http", "--host", "0.0.0.0"])
    ts = called["app_kwargs"]["transport_security"]
    assert ts.enable_dns_rebinding_protection is False


def test_stdio_gets_no_transport_security(monkeypatch):
    """stdio has no HTTP surface, so it must not be handed a guard at all."""
    called = _capture_run(monkeypatch)
    cli.main([])
    assert "transport_security" not in called["kwargs"]


def test_main_allowed_hosts_enables_guard_with_list(monkeypatch):
    called = _capture_http(monkeypatch)
    cli.main(
        [
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--allowed-hosts",
            "benethos-yahoo-finance-mcp:8000",
        ]
    )
    ts = called["app_kwargs"]["transport_security"]
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
        cli.build_parser().parse_args(["--version"])

    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"benethos-yahoo-finance-mcp {__version__}"


def test_version_flag_agrees_with_the_handshake():
    """The two places a version is published must not drift apart."""
    from benethos_yahoo_finance_mcp import __version__

    assert build_server().version == __version__


# --- optional bearer token ---------------------------------------------------


def test_http_without_a_token_serves_unguarded(monkeypatch):
    """The default stays what it was: no token, no guard, nothing to configure."""
    called = _capture_http(monkeypatch)
    cli.main(["--transport", "streamable-http"])
    assert called["app_kwargs"]["token"] is None


def test_http_picks_the_token_up_from_the_environment(monkeypatch):
    called = _capture_http(monkeypatch)
    monkeypatch.setenv(settings.TOKEN_VAR, "s3cret")
    cli.main(["--transport", "streamable-http"])
    assert called["app_kwargs"]["token"] == "s3cret"


def test_serving_http_unguarded_says_so(monkeypatch, caplog):
    """An open port is worth a line in the log, since nothing else shows it."""
    _capture_http(monkeypatch)
    with caplog.at_level("WARNING"):
        cli.main(["--transport", "streamable-http", "--host", "0.0.0.0"])
    assert any(
        settings.TOKEN_VAR in record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING"
    )


def test_a_token_under_stdio_is_ignored_and_reported(monkeypatch, caplog):
    """stdio has no port, so a token there is a misunderstanding worth naming."""
    called = _capture_run(monkeypatch)
    monkeypatch.setenv(settings.TOKEN_VAR, "s3cret")
    with caplog.at_level("WARNING"):
        cli.main([])
    assert called["transport"] == "stdio"
    assert any(record.levelname == "WARNING" for record in caplog.records)
