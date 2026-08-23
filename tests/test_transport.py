"""Unit tests for the optional bearer guard in front of the HTTP transports.

A guard that lets the wrong caller through is worse than none, because it is
believed. Every rejection path is asserted here, not only the happy one.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from benethos_yahoo_finance_mcp import transport


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


def test_non_http_scopes_pass_through(guarded):
    """The lifespan scope must reach the app or the session manager never starts."""
    app, reached = guarded
    _call(app, [], scope_type="lifespan")
    assert reached == ["lifespan"]


class TestTokenFromEnv:
    def test_unset_is_none(self, monkeypatch):
        monkeypatch.delenv(transport.ENV_VAR, raising=False)
        assert transport.token_from_env() is None

    def test_blank_counts_as_unset(self, monkeypatch):
        """`YF_MCP_BEARER_TOKEN=` reads as "off" to everyone who writes it."""
        monkeypatch.setenv(transport.ENV_VAR, "   ")
        assert transport.token_from_env() is None

    def test_value_is_stripped(self, monkeypatch):
        monkeypatch.setenv(transport.ENV_VAR, "  s3cret\n")
        assert transport.token_from_env() == "s3cret"


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
