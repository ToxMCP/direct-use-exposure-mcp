"""Shared server composition types for the MCP registrar modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp.types import CallToolResult

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.runtime import ScenarioEngine
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry

ToolSuccessResult = Callable[[str, Any], CallToolResult]
ToolErrorResult = Callable[[ExposureScenarioError], CallToolResult]


def read_only_tool_annotations(title: str) -> dict[str, bool | str]:
    """Return the standard MCP annotation bundle for read-only deterministic tools."""

    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


@dataclass(frozen=True)
class ServerContext:
    """Typed dependencies shared across the MCP registrar modules."""

    defaults_registry: DefaultsRegistry
    archetype_library: ArchetypeLibraryRegistry
    probability_profiles: ProbabilityBoundsProfileRegistry
    scenario_probability_packages: ScenarioProbabilityPackageRegistry
    tier1_inhalation_profiles: Tier1InhalationProfileRegistry
    engine: ScenarioEngine
