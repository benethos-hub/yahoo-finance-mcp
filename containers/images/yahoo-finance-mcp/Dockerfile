# Both base images are pinned by digest as well as tag. A tag is a pointer the
# publisher can move, and the digest is the content itself, so a rebuild of the
# same commit gets the same bytes. The tag stays for the reader and for
# Dependabot, which proposes a newer tag of the same precision: `3.14-slim`
# moves on to `3.15-slim`, and uv, pinned to its patch, to each patch release.
# A rebuild under an unchanged tag is not reliably proposed, so a release
# refreshes both digests (CLAUDE.md, Releasing).
#
# Dependabot reads FROM lines only. An image named inside `COPY --from=` is
# invisible to it, which is why uv has a stage of its own below: written
# inline, it fell three patch releases behind without a pull request.
#
# There is no `# syntax=` line on purpose. It pulls a frontend image by a
# moving tag on every build, which is the one pull the rule above did not
# cover, and nothing here needs more than the frontend built into BuildKit.

# ---- uv: only the source of the binary, a stage so Dependabot sees it ----
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

# ---- builder: install locked deps + package into /opt/venv via uv ----
FROM python:3.14-slim@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151 AS builder

# Bring in the uv binary.
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install dependencies first (without the project) for better layer caching:
# this layer only changes when pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Now install the project itself as a regular (non-editable) wheel, so the
# resulting /opt/venv is self-contained and can be copied to the runtime stage.
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime: minimal image that just runs the server ----
FROM python:3.14-slim@sha256:c3e521df8b2b498a7a682e7e18676771cb80c6b75b8699af886b2d554ce40151 AS runtime

# All runtime configuration is via environment variables, so the container
# needs no CMD args and stays fully configurable with `docker run -e ...`.
# Defaults: serve streamable-HTTP on all interfaces. The result cache is
# opt-in (off by default); enable it with `-e YF_MCP_CACHE=1`, in which case it
# is written to the mounted /cache volume. Override anything with -e.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    YF_MCP_TRANSPORT=streamable-http \
    YF_MCP_HOST=0.0.0.0 \
    YF_MCP_PORT=8000 \
    YF_MCP_PATH=/mcp \
    YF_MCP_LOG_LEVEL=INFO \
    YF_MCP_CACHE=0 \
    YF_MCP_CACHE_DIR=/cache

# Run as a non-root user; create the cache dir it owns.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /cache \
    && chown appuser:appuser /cache

COPY --from=builder /opt/venv /opt/venv

USER appuser
WORKDIR /home/appuser

EXPOSE 8000

# Persist the result cache across container restarts.
VOLUME ["/cache"]

# Basic liveness check: the configured HTTP port is accepting connections. It
# reads the port from YF_MCP_PORT, since a healthcheck cannot see the
# command line: set the port through the variable, never with --port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('YF_MCP_PORT', '8000'))), 3).close()" || exit 1

# No CMD: configuration comes from the environment above. Extra CLI flags can
# still be appended (they override the env), e.g.:
#   docker run -e YF_MCP_PORT=9000 -p 9000:9000 IMAGE
#   docker run IMAGE --log-level DEBUG
# The port is the exception: an appended --port 9000 leaves the healthcheck
# knocking on 8000, and the container stays unhealthy for good.
ENTRYPOINT ["benethos-yahoo-finance-mcp"]
