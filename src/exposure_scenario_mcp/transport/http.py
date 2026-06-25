"""Streamable-HTTP transport entrypoint for Direct-Use Exposure MCP.

This module exposes the same MCP tool surface as the stdio entrypoint, but
served over FastMCP's streamable-HTTP transport so the server can be reached
by hosted MCP clients and the ToxMCP Gateway.

Configuration (all optional, with defaults suitable for Docker):
    HOST   - bind address  (default: 0.0.0.0)
    PORT   - TCP port      (default: 8000)
    LOG_LEVEL - logging level (default: INFO)

Usage:
    exposure-scenario-mcp-http          # via installed console script
    python -m exposure_scenario_mcp.transport.http
"""

from __future__ import annotations

import logging
import os

from exposure_scenario_mcp.logging_config import configure_logging
from exposure_scenario_mcp.package_metadata import __version__
from exposure_scenario_mcp.server import create_mcp_server


def main() -> None:
    """Start Direct-Use Exposure MCP on the streamable-HTTP transport."""
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()

    configure_logging(level=getattr(logging, log_level_name, logging.INFO))
    logger = logging.getLogger("exposure_scenario_mcp.transport.http")

    logger.info(
        "Starting Direct-Use Exposure MCP v%s (streamable-http) on %s:%s",
        __version__,
        host,
        port,
    )

    server = create_mcp_server()
    server.settings.host = host
    server.settings.port = port
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
