"""FastMCP server definition for Direct-Use Exposure MCP."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.result_meta import build_tool_result_meta
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine
from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)
from exposure_scenario_mcp.server_context import ServerContext
from exposure_scenario_mcp.server_resources import register_prompts, register_resources
from exposure_scenario_mcp.server_tools_core import register_core_tools
from exposure_scenario_mcp.server_tools_integration import register_integration_tools
from exposure_scenario_mcp.server_tools_worker import register_worker_tools
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry


def _success_result(message: str, payload_model) -> CallToolResult:
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="completed", payload_model=payload_model),
        content=[TextContent(type="text", text=message)],
        structuredContent=payload_model.model_dump(mode="json", by_alias=True),
    )


def _error_result(error: ExposureScenarioError) -> CallToolResult:
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="failed", error=error),
        isError=True,
        content=[TextContent(type="text", text=error.as_text())],
    )


def create_mcp_server() -> FastMCP:
    """Create the FastMCP server and register the published domain surfaces."""

    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    probability_profiles = ProbabilityBoundsProfileRegistry.load()
    scenario_probability_packages = ScenarioProbabilityPackageRegistry.load()
    tier1_inhalation_profiles = Tier1InhalationProfileRegistry.load()

    plugin_registry = PluginRegistry()
    plugin_registry.register(ScreeningScenarioPlugin())
    plugin_registry.register(InhalationScreeningPlugin())
    engine = ScenarioEngine(registry=plugin_registry, defaults_registry=defaults_registry)

    context = ServerContext(
        defaults_registry=defaults_registry,
        archetype_library=archetype_library,
        probability_profiles=probability_profiles,
        scenario_probability_packages=scenario_probability_packages,
        tier1_inhalation_profiles=tier1_inhalation_profiles,
        engine=engine,
    )

    mcp = FastMCP("exposure_scenario_mcp")
    register_core_tools(mcp, context, _success_result, _error_result)
    register_integration_tools(mcp, context, _success_result, _error_result)
    register_worker_tools(mcp, context, _success_result)
    register_resources(mcp, context)
    register_prompts(mcp)
    return mcp
