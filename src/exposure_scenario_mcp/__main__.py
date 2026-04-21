"""CLI entry point for Direct-Use Exposure MCP."""

from __future__ import annotations

import argparse
import logging

from exposure_scenario_mcp.healthcheck import run_startup_healthcheck
from exposure_scenario_mcp.http_security import (
    DEFAULT_HTTP_MAX_CONCURRENCY,
    DEFAULT_HTTP_MAX_REQUEST_BYTES,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    build_http_boundary_security_config,
    describe_http_boundary_security,
)
from exposure_scenario_mcp.logging_config import configure_logging
from exposure_scenario_mcp.package_metadata import __version__
from exposure_scenario_mcp.server import create_mcp_server, run_streamable_http


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
    parser.add_argument(
        "--http-bearer-token",
        default=None,
        help=(
            "Shared bearer token for streamable-http access. Prefer the "
            "`EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN` environment variable for "
            "long-lived deployments."
        ),
    )
    parser.add_argument(
        "--http-allowed-origin",
        action="append",
        default=None,
        help=(
            "Trusted Origin allowed to access streamable-http from browser-based clients. "
            "Repeat to allow multiple origins."
        ),
    )
    parser.add_argument(
        "--http-max-request-bytes",
        type=int,
        default=None,
        help=(
            "Maximum streamable-http request size in bytes. Defaults to "
            f"{DEFAULT_HTTP_MAX_REQUEST_BYTES}. Set to 0 to disable the in-process limit."
        ),
    )
    parser.add_argument(
        "--http-audit-log-path",
        default=None,
        help=(
            "Append one JSONL audit record per streamable-http request to this path. Prefer "
            "the `EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH` environment variable for "
            "long-lived deployments."
        ),
    )
    parser.add_argument(
        "--http-request-timeout-seconds",
        type=float,
        default=None,
        help=(
            "Maximum end-to-end streamable-http request duration in seconds. Defaults to "
            f"{DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS}. Set to 0 to disable the in-process timeout."
        ),
    )
    parser.add_argument(
        "--http-max-concurrency",
        type=int,
        default=None,
        help=(
            "Maximum number of concurrent in-process streamable-http requests. Defaults to "
            f"{DEFAULT_HTTP_MAX_CONCURRENCY}. Set to 0 to disable the in-process limit."
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
    if args.transport == "streamable-http":
        security_config = build_http_boundary_security_config(
            bearer_token=args.http_bearer_token,
            allowed_origins=args.http_allowed_origin,
            max_request_bytes=args.http_max_request_bytes,
            audit_log_path=args.http_audit_log_path,
            request_timeout_seconds=args.http_request_timeout_seconds,
            max_concurrency=args.http_max_concurrency,
        )
        logger.info(
            "Streamable-http boundary controls: %s",
            describe_http_boundary_security(security_config),
        )
        run_streamable_http(server, security_config)
        return

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
