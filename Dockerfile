# syntax=docker/dockerfile:1

# ---- builder: install the package (and deps) into an isolated venv ----
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build into a dedicated venv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what the build needs (better layer caching). README.md is required
# because pyproject.toml references it as the package readme.
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

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
