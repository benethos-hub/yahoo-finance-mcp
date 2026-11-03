"""Unit tests for the guards in front of the HTTP transports: the optional bearer
token, the DNS-rebinding check, and how the images and compose files set them.

A guard that lets the wrong caller through is worse than none, because it is
believed. Every rejection path is asserted here, not only the happy one.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from benethos_yahoo_finance_mcp import settings, transport
from benethos_yahoo_finance_mcp.transport import http as http_transport


def _call(app, headers: list[tuple[bytes, bytes]], scope_type: str = "http") -> dict:
    """Drive an ASGI app once and collect what it sent back.

    ``reached`` records whether the wrapped app ran at all, which is the
    difference between a request that was refused and one that was served.
    """
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    async def receive() -> dict[str, Any]:  # pragma: no cover - never awaited
        return {"type": "http.request"}

    scope = {"type": scope_type, "headers": headers}
    asyncio.run(app(scope, receive, send))

    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    return {
        "status": start["status"] if start else None,
        "headers": dict(start["headers"]) if start else {},
        "body": b"".join(m.get("body", b"") for m in sent),
    }


@pytest.fixture
def guarded():
    """The middleware around an app that records having been reached."""
    reached: list[str] = []

    async def inner(scope, receive, send) -> None:
        reached.append(scope["type"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"served"})

    return transport.bearer_middleware(inner, "s3cret"), reached


def test_correct_token_is_served(guarded):
    app, reached = guarded
    result = _call(app, [(b"authorization", b"Bearer s3cret")])
    assert result["status"] == 200
    assert result["body"] == b"served"
    assert reached == ["http"]


def test_scheme_is_case_insensitive(guarded):
    """RFC 7235 makes the scheme case-insensitive, and clients differ."""
    app, reached = guarded
    assert _call(app, [(b"authorization", b"bearer s3cret")])["status"] == 200
    assert reached == ["http"]


def test_missing_header_is_refused(guarded):
    app, reached = guarded
    result = _call(app, [])
    assert result["status"] == 401
    assert result["headers"][b"www-authenticate"] == b"Bearer"
    assert reached == [], "the wrapped app must not run for a refused request"


def test_wrong_token_is_refused(guarded):
    app, reached = guarded
    assert _call(app, [(b"authorization", b"Bearer wrong")])["status"] == 401
    assert reached == []


def test_token_prefix_is_refused(guarded):
    """A comparison on a prefix would accept every guess that starts right."""
    app, reached = guarded
    assert _call(app, [(b"authorization", b"Bearer s3c")])["status"] == 401
    assert reached == []


def test_other_scheme_is_refused(guarded):
    app, reached = guarded
    assert _call(app, [(b"authorization", b"Basic s3cret")])["status"] == 401
    assert reached == []


def test_bare_token_without_scheme_is_refused(guarded):
    app, reached = guarded
    assert _call(app, [(b"authorization", b"s3cret")])["status"] == 401
    assert reached == []


def test_refusal_says_nothing_about_the_token(guarded):
    """The body must not reveal whether a token was sent or how close it was."""
    app, _ = guarded
    close = _call(app, [(b"authorization", b"Bearer s3cres")])
    absent = _call(app, [])
    assert close["body"] == absent["body"] == b'{"error":"unauthorized"}'


def test_lifespan_passes_through(guarded):
    """The lifespan scope must reach the app or the session manager never starts."""
    app, reached = guarded
    _call(app, [], scope_type="lifespan")
    assert reached == ["lifespan"]


def test_websocket_is_refused_even_with_the_token(guarded):
    """No WebSocket route exists today, and none gets past the guard unchecked."""
    app, reached = guarded
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    async def receive() -> dict[str, Any]:  # pragma: no cover - never awaited
        return {"type": "websocket.connect"}

    scope = {"type": "websocket", "headers": [(b"authorization", b"Bearer s3cret")]}
    asyncio.run(app(scope, receive, send))
    assert reached == []
    assert sent == [{"type": "websocket.close", "code": 1008}]


def test_unknown_scope_never_reaches_the_app(guarded):
    app, reached = guarded
    out = _call(app, [(b"authorization", b"Bearer s3cret")], scope_type="future")
    assert reached == []
    assert out["status"] is None


class TestHttpApp:
    """Which app comes back, and whether the guard is in front of it."""

    def _built(self, monkeypatch, token):
        built: dict[str, Any] = {}

        class FakeServer:
            def streamable_http_app(self, **kwargs):
                built["kind"] = "streamable"
                built["kwargs"] = kwargs
                return "streamable-app"

            def sse_app(self, **kwargs):
                built["kind"] = "sse"
                built["kwargs"] = kwargs
                return "sse-app"

        app = transport.http_app(
            FakeServer(),
            transport="streamable-http",
            path="/mcp",
            host="127.0.0.1",
            transport_security="policy",
            token=token,
        )
        return app, built

    def test_without_a_token_the_app_is_unwrapped(self, monkeypatch):
        app, built = self._built(monkeypatch, None)
        assert app == "streamable-app"
        assert built["kwargs"]["streamable_http_path"] == "/mcp"
        assert built["kwargs"]["transport_security"] == "policy"

    def test_with_a_token_the_app_is_wrapped(self, monkeypatch):
        app, _ = self._built(monkeypatch, "s3cret")
        assert app != "streamable-app", "the guard has to be in front of the app"
        assert callable(app)

    def test_sse_uses_the_sse_app(self):
        class FakeServer:
            def sse_app(self, **kwargs):
                return ("sse", kwargs)

            def streamable_http_app(self, **kwargs):  # pragma: no cover
                raise AssertionError("sse must not build the streamable app")

        app = transport.http_app(
            FakeServer(),
            transport="sse",
            path="/events",
            host="127.0.0.1",
            transport_security="policy",
            token=None,
        )
        assert app[0] == "sse"
        assert app[1]["sse_path"] == "/events"


def test_the_server_believes_no_forwarded_header(monkeypatch):
    """uvicorn trusts ``X-Forwarded-For`` from a loopback peer unless told not to.

    On the default bind that is every peer, and the header would then choose
    the address in the one log line the printable filter leaves alone.
    """
    import uvicorn
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    configs: list[Any] = []

    class FakeServer:
        def __init__(self, config: Any) -> None:
            configs.append(config)

        def run(self) -> None:
            pass

    async def app(scope: Any, receive: Any, send: Any) -> None:
        pass  # pragma: no cover - never served

    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    transport.http.serve(app, host="127.0.0.1", port=8000)
    [config] = configs
    config.load()
    assert not isinstance(config.loaded_app, ProxyHeadersMiddleware)


# --- DNS-rebinding guard ----------------------------------------------------


def test_transport_security_localhost_keeps_protection():
    ts = http_transport.transport_security_for("127.0.0.1", [], [])
    assert ts.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in ts.allowed_hosts


@pytest.mark.parametrize(
    "host", ["LOCALHOST", "127.0.0.2", " 127.0.0.1", "[::1]", "::1", "localhost"]
)
def test_every_loopback_spelling_keeps_the_guard_on(host):
    """Decided by address, not by the exact string."""
    ts = http_transport.transport_security_for(host, [], [])
    assert ts.enable_dns_rebinding_protection is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "mcp.example"])
def test_a_bind_off_this_machine_is_exposed(host):
    ts = http_transport.transport_security_for(host, [], [])
    assert ts.enable_dns_rebinding_protection is False


def test_transport_security_exposed_bind_disables_protection():
    ts = http_transport.transport_security_for("0.0.0.0", [], [])
    assert ts.enable_dns_rebinding_protection is False


def test_transport_security_explicit_allow_list_wins_even_when_exposed():
    ts = http_transport.transport_security_for("0.0.0.0", ["mcp:8000"], [])
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["mcp:8000"]
    # Origins are derived from the hosts when not given explicitly.
    assert ts.allowed_origins == ["http://mcp:8000", "https://mcp:8000"]


@pytest.mark.parametrize("folder", ["development", "production"])
def test_compose_takes_the_log_level_from_env(folder):
    """A literal under environment: would quietly win over the operator's .env."""
    from pathlib import Path

    path = Path(__file__).parent.parent / "containers" / folder / "compose.yaml"
    compose = path.read_text("utf-8")
    levels = re.findall(r"^ +YF_MCP_LOG_LEVEL: (.+)$", compose, re.M)
    assert levels == ["${YF_MCP_LOG_LEVEL:-INFO}"]


def _compose_guard(folder: str, env: dict[str, str]):
    """The rebinding guard ``folder``'s compose file sets up, under ``env``.

    The allow-list is read from the file and its ``${NAME:+...}`` suffixes
    resolved the way compose does: what follows ``:+``, with ``${NAME}`` in it
    filled in, when NAME is set and not empty, nothing otherwise.
    """
    from pathlib import Path

    from mcp.server.transport_security import TransportSecurityMiddleware

    path = Path(__file__).parent.parent / "containers" / folder / "compose.yaml"
    compose = path.read_text("utf-8")
    [raw] = re.findall(r'^ +YF_MCP_ALLOWED_HOSTS: "([^"]+)"$', compose, re.M)
    raw = re.sub(
        r"\$\{(\w+):\+((?:[^${}]|\$\{\1\})*)\}",
        lambda m: m[2].replace(f"${{{m[1]}}}", env[m[1]]) if env.get(m[1]) else "",
        raw,
    )
    assert "$" not in raw, f"compose interpolates more than this test: {raw}"
    ts = http_transport.transport_security_for("0.0.0.0", settings.split_csv(raw), [])
    assert ts.enable_dns_rebinding_protection is True
    return TransportSecurityMiddleware(ts)


def _refused(guard, host: str, origin: str | None = None) -> int | None:
    """The status the SDK's own check answers a POST with, None when it passes."""
    from starlette.requests import Request

    headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    request = Request(
        {"type": "http", "method": "POST", "path": "/mcp", "headers": headers}
    )
    response = asyncio.run(guard.validate_request(request, is_post=True))
    return None if response is None else response.status_code


@pytest.mark.parametrize("folder", ["development", "production"])
def test_compose_keeps_the_rebinding_guard_on(folder):
    """The container binds 0.0.0.0, which alone turns the guard off.

    A page whose domain points at 127.0.0.1 could then call every tool from a
    browser on the host. Compose sets the allow-list, not as a comment, in
    both folders.
    """
    guard = _compose_guard(folder, {})
    for host in ("localhost:8000", "127.0.0.1:8000", "[::1]:8000"):
        assert _refused(guard, host) is None, host
    assert _refused(guard, "benethos-yahoo-finance-mcp:8000") is None
    assert _refused(guard, "attacker.example:8000") == 421
    assert _refused(guard, "localhost:8000", "http://localhost:8000") is None
    assert _refused(guard, "localhost:8000", "http://attacker.example:8000") == 403


def test_the_image_keeps_the_rebinding_guard_on():
    """A bare ``docker run`` binds 0.0.0.0 too, without compose's allow-list."""
    from pathlib import Path

    from mcp.server.transport_security import TransportSecurityMiddleware

    path = Path(__file__).parent.parent / "containers/images/yahoo-finance-mcp"
    dockerfile = (path / "Dockerfile").read_text("utf-8")
    [raw] = re.findall(r'^ +YF_MCP_ALLOWED_HOSTS="([^"]+)" \\$', dockerfile, re.M)
    hosts = settings.split_csv(raw)
    assert hosts == (
        "localhost:*",
        "127.0.0.1:*",
        "[::1]:*",
        "benethos-yahoo-finance-mcp:*",
    )
    guard = TransportSecurityMiddleware(
        http_transport.transport_security_for("0.0.0.0", hosts, [])
    )
    assert _refused(guard, "localhost:8000") is None
    assert _refused(guard, "attacker.example:8000") == 421


def test_compose_lets_the_https_domain_through():
    """Caddy keeps the client's Host, so without the domain every call gets 421."""
    guard = _compose_guard("production", {"YAHOO_FINANCE_MCP_DOMAIN": "mcp.test"})
    assert _refused(guard, "mcp.test", "https://mcp.test") is None
    # YAHOO_FINANCE_MCP_HTTPS_PORT moved Caddy, and the client's Host says so.
    assert _refused(guard, "mcp.test:8443", "https://mcp.test:8443") is None
    assert _refused(guard, "localhost:8000") is None
    assert _refused(guard, "attacker.example") == 421
    assert _refused(_compose_guard("production", {}), "mcp.test") == 421


def test_transport_security_explicit_origins_are_kept():
    ts = http_transport.transport_security_for(
        "0.0.0.0", ["mcp:8000"], ["http://mcp:8000"]
    )
    assert ts.allowed_origins == ["http://mcp:8000"]


def test_transport_security_origins_alone_derive_the_hosts():
    """Origins without hosts must not leave the Host allow-list empty.

    The SDK rejects every Host that is not on the list, so an empty list with
    protection on answered every request with HTTP 421.
    """
    ts = http_transport.transport_security_for(
        "0.0.0.0",
        [],
        ["https://mcp.example.com", "http://mcp.example.com", "http://localhost:*"],
    )
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["mcp.example.com", "localhost:*"]
    assert ts.allowed_origins == [
        "https://mcp.example.com",
        "http://mcp.example.com",
        "http://localhost:*",
    ]


def test_origins_alone_let_a_matching_request_through():
    """End to end through the SDK's own check, not just the settings object."""
    from mcp.server.transport_security import TransportSecurityMiddleware
    from starlette.requests import Request

    ts = http_transport.transport_security_for(
        "0.0.0.0", [], ["https://mcp.example.com"]
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "headers": [
                (b"host", b"mcp.example.com"),
                (b"origin", b"https://mcp.example.com"),
                (b"content-type", b"application/json"),
            ],
        }
    )
    response = asyncio.run(
        TransportSecurityMiddleware(ts).validate_request(request, is_post=True)
    )
    assert response is None
