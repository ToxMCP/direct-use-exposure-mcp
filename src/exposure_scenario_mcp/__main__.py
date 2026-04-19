"""CLI entry point for Direct-Use Exposure MCP."""

from __future__ import annotations

import argparse
import logging

from exposure_scenario_mcp.healthcheck import run_startup_healthcheck
from exposure_scenario_mcp.logging_config import configure_logging
from exposure_scenario_mcp.package_metadata import __version__
from exposure_scenario_mcp.server import create_mcp_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Direct-Use Exposure MCP.")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Transport to use for the MCP server.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for HTTP transports.",
    )
    parser.add_argument(
        "--port",
        default=8000,
        type=int,
        help="Port to bind for HTTP transports.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help=(
            "Validate packaged registries and published MCP surface, then exit without "
            "starting a transport."
        ),
    )
    args = parser.parse_args(argv)

    configure_logging(level=getattr(logging, args.log_level))
    logger = logging.getLogger("exposure_scenario_mcp")

    if args.healthcheck:
        try:
            summary = run_startup_healthcheck()
        except Exception as error:
            logger.error("Startup healthcheck failed: %s", error)
            raise SystemExit(1) from error
        logger.info(
            "Startup healthcheck passed: defaults=%s tools=%s resources=%s prompts=%s",
            summary.defaults_version,
            summary.tool_count,
            summary.resource_count,
            summary.prompt_count,
        )
        return

    logger.info(
        "Starting Direct-Use Exposure MCP v%s on %s (%s:%s)",
        __version__,
        args.transport,
        args.host,
        args.port,
    )

    server = create_mcp_server()
    server.settings.host = args.host
    server.settings.port = args.port
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
