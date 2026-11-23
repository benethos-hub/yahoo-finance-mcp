"""The two ways to serve the tools: stdio for a local client, HTTP for a port.

The CLI hands the server to :func:`run_stdio` or :func:`run_http` and does not
branch any further itself.
"""

from __future__ import annotations

from .http import (
    bearer_middleware,
    http_app,
    run_http,
    single_response,
    transport_security_for,
)
from .stdio import run_stdio

__all__ = [
    "bearer_middleware",
    "http_app",
    "run_http",
    "run_stdio",
    "single_response",
    "transport_security_for",
]
