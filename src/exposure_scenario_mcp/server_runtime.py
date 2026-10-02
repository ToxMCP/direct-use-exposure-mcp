"""Provider-backed runtime state for MCPServer lifecycle and direct-call usage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock

from mcp.server import MCPServer

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
    """Build the shared runtime state used by the MCPServer server."""

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
        self._lock = RLock()

    def get_runtime_state(self, mcp: MCPServer | None = None) -> ServerRuntimeState:
        # The provider belongs to one server. Lifespan and direct calls share the
        # same immutable registries; SDK2 sync handlers can initialize concurrently.
        with self._lock:
            if self._runtime_state is None:
                self._runtime_state = self._factory()
            return self._runtime_state

    def get_context(self, mcp: MCPServer | None = None) -> ServerContext:
        return self.get_runtime_state(mcp).server_context

    def clear(self) -> None:
        with self._lock:
            self._runtime_state = None
