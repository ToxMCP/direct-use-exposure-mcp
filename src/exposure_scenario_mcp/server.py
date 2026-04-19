"""FastMCP server definition for Direct-Use Exposure MCP."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.package_metadata import package_version
from exposure_scenario_mcp.result_meta import build_tool_result_meta
from exposure_scenario_mcp.server_resources import register_prompts, register_resources
from exposure_scenario_mcp.server_runtime import (
    ServerRuntimeProvider,
    ServerRuntimeState,
    build_server_runtime_state,
)
from exposure_scenario_mcp.server_tools_core import register_core_tools
from exposure_scenario_mcp.server_tools_integration import register_integration_tools
from exposure_scenario_mcp.server_tools_worker import register_worker_tools

_logger = logging.getLogger("exposure_scenario_mcp.server")


def _success_result(message: str, payload_model) -> CallToolResult:
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="completed", payload_model=payload_model),
        content=[TextContent(type="text", text=message)],
        structuredContent=payload_model.model_dump(mode="json", by_alias=True),
    )


def _error_result(error: ExposureScenarioError) -> CallToolResult:
    _logger.warning("Tool error: %s - %s", error.code, error.message)
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="failed", error=error),
        isError=True,
        content=[TextContent(type="text", text=error.as_text())],
    )


def create_mcp_server() -> FastMCP:
    """Create the FastMCP server and register the published domain surfaces."""

    runtime_provider = ServerRuntimeProvider(build_server_runtime_state)

    @asynccontextmanager
    async def lifespan(_mcp: FastMCP) -> AsyncIterator[ServerRuntimeState]:
        runtime_state = runtime_provider.get_runtime_state()
        _logger.info(
            "MCP startup: server=%s defaults=%s archetypes=%s profiles=%s packages=%s tier1=%s",
            package_version(),
            runtime_state.defaults_registry.version,
            runtime_state.archetype_library.version,
            runtime_state.probability_profiles.version,
            runtime_state.scenario_probability_packages.version,
            runtime_state.tier1_inhalation_profiles.version,
        )
        try:
            yield runtime_state
        finally:
            runtime_provider.clear()
            _logger.info("MCP server shutdown complete")

    mcp = FastMCP("exposure_scenario_mcp", lifespan=lifespan)
    mcp._server_runtime_provider = runtime_provider  # type: ignore[attr-defined]

    def context_provider():
        return runtime_provider.get_context(mcp)

    register_core_tools(mcp, context_provider, _success_result, _error_result)
    register_integration_tools(mcp, context_provider, _success_result, _error_result)
    register_worker_tools(mcp, context_provider, _success_result, _error_result)
    register_resources(mcp, context_provider)
    register_prompts(mcp)
    _logger.info("MCP server initialized")
    return mcp
