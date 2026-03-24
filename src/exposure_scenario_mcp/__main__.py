"""CLI entry point for Exposure Scenario MCP."""

from __future__ import annotations

import argparse

from exposure_scenario_mcp.server import create_mcp_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Exposure Scenario MCP.")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Transport to use for the MCP server.",
    )
    args = parser.parse_args()

    server = create_mcp_server()
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
