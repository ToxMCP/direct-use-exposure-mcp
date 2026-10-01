"""Exercise the CLI's real JSON-RPC stream through startup and shutdown."""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from exposure_scenario_mcp.package_metadata import package_version


def test_stdio_cli_preserves_jsonrpc_through_shutdown() -> None:
    async def exercise_transport() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "exposure_scenario_mcp"],
        )
        async with (
            stdio_client(parameters) as (read, write),
            ClientSession(read, write) as session,
        ):
            initialized = await session.initialize()
            assert initialized.serverInfo.version == package_version()
            tools = await session.list_tools()
            assert "exposure_run_verification_checks" in {tool.name for tool in tools.tools}

    asyncio.run(exercise_transport())
