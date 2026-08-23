"""Serving the tools over HTTP, and the optional guard in front of them.

stdio needs none of this. The client starts the server as its own child process
and nothing else can talk to it. A port is different: anything that can route to
it can call every tool.

The guard is a **single shared secret** compared in constant time, not an OAuth
flow. This server speaks for nobody and has no user to authorize — the question
is only whether the caller is expected. It is **optional**, because the ordinary
case is a server bound to the loopback address on the machine that uses it,
where a token protects against nothing. Set ``YF_MCP_BEARER_TOKEN`` and every
HTTP request has to carry it.

There is deliberately no command-line flag for the token. An argument is visible
in the process list to every other user on the machine and lands in shell
history, and neither is where a secret belongs.

A token does not make a port safe to publish on a network. The data here is
public and read-only, so the realistic threat is somebody spending your rate
limit at Yahoo, not reading something private. For anything beyond a trusted
network, put a reverse proxy with real authentication in front.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mcp.server.mcpserver import MCPServer
    from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = ["bearer_middleware", "http_app", "run_http", "token_from_env"]

logger = logging.getLogger(__name__)

ENV_VAR = "YF_MCP_BEARER_TOKEN"


def token_from_env() -> str | None:
    """The configured token, or ``None`` when the port is left unguarded.

    An empty or blank value counts as unset rather than as a token nobody can
    guess, because ``YF_MCP_BEARER_TOKEN=`` in a Compose file or a shell profile
    reads as "off" to everyone who writes it.
    """
    return (os.environ.get(ENV_VAR) or "").strip() or None


def bearer_middleware(app: ASGIApp, token: str) -> ASGIApp:
    """Wrap an ASGI app so every HTTP request must carry the bearer token.

    Non-HTTP scopes pass through untouched. The lifespan scope is one of them,
    and swallowing it would leave the session manager unstarted and the server
    answering nothing at all.
    """
    expected = token.encode()

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await app(scope, receive, send)
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


def run_http(app: ASGIApp, *, host: str, port: int, log_level: str) -> None:
    """Serve the app over HTTP until interrupted.

    The SDK's own runner builds the app and starts uvicorn in one step, which
    leaves nowhere to put the guard. This does the same two things with the
    wrapper in between.
    """
    import uvicorn  # imported here so stdio never pays for it

    uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level=log_level.lower())
    ).run()
