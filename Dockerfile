# Dockerfile for Direct-Use Exposure MCP
# Supports both stdio and streamable-http transports.

FROM python:3.12-slim

WORKDIR /app

# Install uv for fast Python dependency management.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files.
COPY pyproject.toml README.md LICENSE CITATION.cff ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY defaults/ ./defaults/
COPY archetypes/ ./archetypes/
COPY probability_bounds/ ./probability_bounds/
COPY tier1_inhalation/ ./tier1_inhalation/
COPY validation/ ./validation/
COPY tests/fixtures/ ./tests/fixtures/

# Sync dependencies and build the wheel.
RUN uv sync --no-dev && uv build

# Install the built wheel into the system environment.
RUN pip install dist/exposure_scenario_mcp-0.1.0-py3-none-any.whl

# Expose the default HTTP port.
EXPOSE 8000

# Health check for HTTP deployments.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import exposure_scenario_mcp" || exit 1

# Default entry point runs stdio transport.
# Override with: docker run ... exposure-scenario-mcp --transport streamable-http --host 0.0.0.0
ENTRYPOINT ["exposure-scenario-mcp"]
CMD ["--transport", "stdio"]
