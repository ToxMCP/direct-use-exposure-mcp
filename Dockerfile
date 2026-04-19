# Dockerfile for Direct-Use Exposure MCP
# Supports both stdio and streamable-http transports.

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

FROM python:3.12-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv

RUN chown -R app:app /opt/venv

USER app

# Expose the default HTTP port.
EXPOSE 8000

# Health check for containerized deployments.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["exposure-scenario-mcp", "--healthcheck"]

# Default entry point runs stdio transport.
# Override with: docker run ... exposure-scenario-mcp --transport streamable-http --host 0.0.0.0
ENTRYPOINT ["exposure-scenario-mcp"]
CMD ["--transport", "stdio"]
