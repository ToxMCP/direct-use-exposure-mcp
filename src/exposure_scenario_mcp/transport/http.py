"""Streamable-HTTP transport entrypoint for Direct-Use Exposure MCP.

This module exposes the same MCP tool surface as the stdio entrypoint, but
served over MCPServer's streamable-HTTP transport so the server can be reached
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

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from exposure_scenario_mcp.logging_config import configure_logging
from exposure_scenario_mcp.package_metadata import __version__
from exposure_scenario_mcp.server import create_mcp_server


def _allowlist(name: str, default: str) -> list[str]:
    values = [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]
    if not values:
        raise ValueError(f"{name} must contain at least one allowlisted value.")
    return values


def create_http_app(server: MCPServer | None = None, *, host: str | None = None) -> Starlette:
    """Serve both protocol generations with bounded bodies and explicit origin controls."""
    limit = int(os.environ.get("DIRECT_USE_MCP_MAX_REQUEST_BYTES", "4194304"))
    if limit <= 0:
        raise ValueError("DIRECT_USE_MCP_MAX_REQUEST_BYTES must be a positive integer.")
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowlist("DIRECT_USE_MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,[::1]:*"),
        allowed_origins=_allowlist(
            "DIRECT_USE_MCP_ALLOWED_ORIGINS",
            "http://localhost:*,http://127.0.0.1:*,http://[::1]:*",
        ),
    )
    server = server or create_mcp_server()
    return server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        max_request_body_size=limit,
        transport_security=security,
        host=host or os.environ.get("HOST", "0.0.0.0"),  # noqa: S104
    )


def run_http_server(
    server: MCPServer | None = None, *, host: str, port: int, log_level: str = "info"
) -> None:
    uvicorn.run(create_http_app(server, host=host), host=host, port=port, log_level=log_level)


def main() -> None:
    """Start Direct-Use Exposure MCP on the streamable-HTTP transport."""
    host = os.environ.get("HOST", "0.0.0.0")  # noqa: S104
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

    run_http_server(host=host, port=port, log_level=log_level_name.lower())


if __name__ == "__main__":
    main()
