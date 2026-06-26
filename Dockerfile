# syntax=docker/dockerfile:1.5
# Dockerfile for Direct-Use Exposure MCP
# Supports both stdio (local) and streamable-http (hosted) transports.
# The CMD here serves the streamable-HTTP transport so the image is ready
# for hosted / ToxMCP-Gateway deployments out of the box.
# For local stdio use: docker run --rm -i <image> exposure-scenario-mcp

FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install uv for locked dependency sync during the build.
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/

# Copy project files required to build a non-editable locked environment.
COPY pyproject.toml uv.lock README.md LICENSE CITATION.cff ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY defaults/ ./defaults/
COPY archetypes/ ./archetypes/
COPY probability_bounds/ ./probability_bounds/
COPY tier1_inhalation/ ./tier1_inhalation/
COPY validation/ ./validation/
COPY tests/fixtures/ ./tests/fixtures/

# Install the project and runtime dependencies from the lockfile.
RUN uv sync --frozen --no-dev --no-editable --compile-bytecode

# ── Runtime image ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Create a non-root user to run the service.
RUN groupadd --system app && \
    useradd --system --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv

RUN chown -R app:app /opt/venv

USER app

# Expose the default HTTP port.
EXPOSE 8000

# Health check: confirm the MCP endpoint is reachable and not returning 5xx.
# GET /mcp without Accept headers returns 406 (the server is up and speaking MCP).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, urllib.error, sys; \
try: urllib.request.urlopen('http://localhost:8000/mcp') \
except urllib.error.HTTPError as e: sys.exit(0 if e.code < 500 else 1) \
except Exception: sys.exit(1) \
else: sys.exit(0)"

# Default: serve the streamable-HTTP transport (hosted mode).
# For local stdio: docker run --rm -i <image> exposure-scenario-mcp
CMD ["exposure-scenario-mcp-http"]
