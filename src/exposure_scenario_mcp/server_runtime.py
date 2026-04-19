"""Provider-backed runtime state for FastMCP lifecycle and direct-call usage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine
from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)
from exposure_scenario_mcp.server_context import ServerContext
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry


@dataclass(frozen=True)
class ServerRuntimeState:
    """Full initialized runtime state shared across tool and resource handlers."""

    defaults_registry: DefaultsRegistry
    archetype_library: ArchetypeLibraryRegistry
    probability_profiles: ProbabilityBoundsProfileRegistry
    scenario_probability_packages: ScenarioProbabilityPackageRegistry
    tier1_inhalation_profiles: Tier1InhalationProfileRegistry
    plugin_registry: PluginRegistry
    engine: ScenarioEngine
    server_context: ServerContext


def build_server_runtime_state() -> ServerRuntimeState:
    """Build the shared runtime state used by the FastMCP server."""

    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    probability_profiles = ProbabilityBoundsProfileRegistry.load()
    scenario_probability_packages = ScenarioProbabilityPackageRegistry.load()
    tier1_inhalation_profiles = Tier1InhalationProfileRegistry.load()

    plugin_registry = PluginRegistry()
    plugin_registry.register(ScreeningScenarioPlugin())
    plugin_registry.register(InhalationScreeningPlugin())

    engine = ScenarioEngine(registry=plugin_registry, defaults_registry=defaults_registry)
    server_context = ServerContext(
        defaults_registry=defaults_registry,
        archetype_library=archetype_library,
        probability_profiles=probability_profiles,
        scenario_probability_packages=scenario_probability_packages,
        tier1_inhalation_profiles=tier1_inhalation_profiles,
        engine=engine,
    )
    return ServerRuntimeState(
        defaults_registry=defaults_registry,
        archetype_library=archetype_library,
        probability_profiles=probability_profiles,
        scenario_probability_packages=scenario_probability_packages,
        tier1_inhalation_profiles=tier1_inhalation_profiles,
        plugin_registry=plugin_registry,
        engine=engine,
        server_context=server_context,
    )


class ServerRuntimeProvider:
    """Cache and expose runtime state for lifespan-managed and direct-call use."""

    def __init__(self, factory: Callable[[], ServerRuntimeState]) -> None:
        self._factory = factory
        self._runtime_state: ServerRuntimeState | None = None

    def _lifespan_runtime_state(self, mcp: FastMCP | None) -> ServerRuntimeState | None:
        if mcp is None:
            return None
        try:
            request_context = mcp.get_context().request_context
        except ValueError:
            return None
        if request_context is None:
            return None
        runtime_state = request_context.lifespan_context
        return runtime_state if isinstance(runtime_state, ServerRuntimeState) else None

    def get_runtime_state(self, mcp: FastMCP | None = None) -> ServerRuntimeState:
        runtime_state = self._lifespan_runtime_state(mcp)
        if runtime_state is not None:
            return runtime_state
        if self._runtime_state is None:
            self._runtime_state = self._factory()
        return self._runtime_state

    def get_context(self, mcp: FastMCP | None = None) -> ServerContext:
        return self.get_runtime_state(mcp).server_context

    def clear(self) -> None:
        self._runtime_state = None
