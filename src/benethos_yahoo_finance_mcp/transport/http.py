"""Serving the tools over HTTP, and the two guards in front of them.

stdio needs none of this. The client starts the server as its own child process
and nothing else can talk to it. A port is different: anything that can route to
it can call every tool. Two independent checks sit at that port. The SDK's
DNS-rebinding guard compares the ``Host`` and ``Origin`` headers against an
allow-list, see :func:`transport_security_for`, and the optional bearer guard
here asks the caller for a token.

The bearer guard is a **single shared secret** compared in constant time, not
an OAuth flow. This server speaks for nobody and has no user to authorize — the
question is only whether the caller is expected. It is **optional**, because the
ordinary case is a server bound to the loopback address on the machine that uses
it, where a token protects against nothing. Set ``YF_MCP_BEARER_TOKEN`` and
every HTTP request has to carry it.

A token does not make a port safe to publish on a network. The data here is
public and read-only, so the realistic threat is somebody spending your rate
limit at Yahoo, not reading something private. For anything beyond a trusted
network, put a reverse proxy with real authentication in front.
"""

from __future__ import annotations

import hmac
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from mcp.server.transport_security import TransportSecuritySettings

from ..logbook import access

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer
    from starlette.types import ASGIApp, Receive, Scope, Send

    from ..settings import Settings

__all__ = [
    "bearer_middleware",
    "http_app",
    "run_http",
    "serve",
    "transport_security_for",
]

# Host values for which we keep DNS-rebinding protection on by default.
_LOCALHOST_BINDS = frozenset({"127.0.0.1", "localhost", "::1", ""})


def _hosts_from_origins(origins: Sequence[str]) -> list[str]:
    """The Host header values the given origins imply, in order, deduplicated.

    An origin's authority is exactly what a browser at that origin sends as
    ``Host``, including a ``:*`` port wildcard, which the SDK understands in
    both lists.
    """
    hosts: list[str] = []
    for origin in origins:
        netloc = urlsplit(origin).netloc
        if netloc and netloc not in hosts:
            hosts.append(netloc)
    return hosts


def transport_security_for(
    host: str, allowed_hosts: Sequence[str], allowed_origins: Sequence[str]
) -> TransportSecuritySettings:
    """Compute the transport security policy for the host the server binds.

    The SDK defaults this to a localhost-only allow-list. Left alone, an HTTP
    transport bound to a non-localhost host would reject every remote client
    with HTTP 421 ("Invalid Host header"), which is exactly what containers and
    gateways run into. Derive it from the host actually being bound:

    - An explicit allow-list always wins: enable protection with those values.
      Either list is derived from the other when only one is given.
    - A localhost bind keeps the protective localhost defaults.
    - A deliberately exposed bind (e.g. 0.0.0.0) with no allow-list turns
      DNS-rebinding protection off, mirroring the SDK's own default for a
      non-localhost bind.

    The hosts have to be derived, not left empty. With protection on, the SDK
    checks the Host header of every request against the list, and an empty
    list matches nothing: origins alone used to lock out every client with
    HTTP 421, the browser the origins were meant for included.
    """
    if allowed_hosts or allowed_origins:
        origins = list(allowed_origins) or [
            f"{scheme}://{h}" for h in allowed_hosts for scheme in ("http", "https")
        ]
        hosts = list(allowed_hosts) or _hosts_from_origins(allowed_origins)
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )
    if host in _LOCALHOST_BINDS:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def bearer_middleware(app: ASGIApp, token: str) -> ASGIApp:
    """Wrap an ASGI app so every HTTP request must carry the bearer token.

    The lifespan scope passes through untouched, because swallowing it would
    leave the session manager unstarted and the server answering nothing at
    all. It is the only scope that does. The SDK serves no WebSocket route
    today, but a guard that waves through every scope it was not written for
    would open the door the day one appears, so anything else is refused: a
    WebSocket handshake is closed with 1008 (policy violation) before it is
    accepted, and an unknown scope type gets no answer at all.
    """
    expected = token.encode()

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            return

        headers = dict(scope.get("headers") or [])
        scheme, _, provided = headers.get(b"authorization", b"").partition(b" ")
        # The scheme is case-insensitive per RFC 7235 and is not a secret, so
        # only the token itself needs the constant-time comparison.
        if scheme.lower() != b"bearer" or not hmac.compare_digest(
            provided.strip(), expected
        ):
            await _unauthorized(send)
            return

        await app(scope, receive, send)

    return guarded


async def _unauthorized(send: Send) -> None:
    """A 401 that says how to authenticate and nothing else.

    No hint about whether a token was sent, whether it was close, or what this
    server is. An unauthenticated caller learns only that it needs a token.
    """
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})


def http_app(
    server: MCPServer,
    *,
    transport: str,
    path: str,
    host: str,
    transport_security: Any,
    token: str | None,
) -> ASGIApp:
    """The ASGI app to serve, with the bearer guard in front when there is one.

    Both transports are built the same way and the wrapper is the only
    difference, so the guarded path is not a second, less-travelled variant of
    the unguarded one.
    """
    if transport == "sse":
        app: ASGIApp = server.sse_app(
            sse_path=path,
            transport_security=transport_security,
            host=host,
        )
    else:
        app = server.streamable_http_app(
            streamable_http_path=path,
            transport_security=transport_security,
            host=host,
        )
    if token is None:
        return app
    return bearer_middleware(app, token)


def run_http(server: MCPServer, settings: Settings) -> None:
    """Build the app the settings describe and serve it until interrupted."""
    app = http_app(
        server,
        transport=settings.transport,
        path=settings.http_path,
        host=settings.host,
        transport_security=transport_security_for(
            settings.host, settings.allowed_hosts, settings.allowed_origins
        ),
        token=settings.bearer_token,
    )
    serve(app, host=settings.host, port=settings.port)


def serve(app: ASGIApp, *, host: str, port: int) -> None:
    """Serve the app over HTTP until interrupted.

    The SDK's own runner builds the app and starts uvicorn in one step, which
    leaves nowhere to put the guard. This does the same two things with the
    wrapper in between. uvicorn's log goes where the logbook sends it.
    """
    import uvicorn  # imported here so stdio never pays for it

    uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, **access.uvicorn_options())
    ).run()
