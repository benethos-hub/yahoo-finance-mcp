# syntax=docker/dockerfile:1

# ---- builder: install locked deps + package into /opt/venv via uv ----
FROM python:3.12-slim AS builder

# Bring in the uv binary (pinned image tag for reproducibility).
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

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
FROM python:3.12-slim AS runtime

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

# Basic liveness check: the configured HTTP port is accepting connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('YF_MCP_PORT', '8000'))), 3).close()" || exit 1

# No CMD: configuration comes from the environment above. Extra CLI flags can
# still be appended (they override the env), e.g.:
#   docker run -e YF_MCP_PORT=9000 -p 9000:9000 IMAGE
#   docker run IMAGE --log-level DEBUG
ENTRYPOINT ["yahoo-finance-mcp"]
