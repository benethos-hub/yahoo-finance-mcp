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

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

USER appuser
WORKDIR /home/appuser

EXPOSE 8000

# Basic liveness check: the HTTP port is accepting connections.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), 3).close()" || exit 1

# Default to the streamable-HTTP transport, reachable from outside the
# container. Override the CMD to change transport/host/port/path, e.g.:
#   docker run -p 9000:9000 IMAGE --transport streamable-http --port 9000
ENTRYPOINT ["yahoo-finance-mcp"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
