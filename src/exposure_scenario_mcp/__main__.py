"""CLI entry point for Direct-Use Exposure MCP."""

from __future__ import annotations

import argparse

from exposure_scenario_mcp.server import create_mcp_server


def main() -> None:
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
    args = parser.parse_args()

    server = create_mcp_server()
    server.settings.host = args.host
    server.settings.port = args.port
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
