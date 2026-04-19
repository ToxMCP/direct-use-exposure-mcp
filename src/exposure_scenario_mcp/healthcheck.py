"""Startup health checks for container and operator validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from mcp.server.fastmcp import FastMCP

from exposure_scenario_mcp.server import create_mcp_server
from exposure_scenario_mcp.server_runtime import ServerRuntimeProvider

REQUIRED_TOOL_NAMES = frozenset(
    {
        "exposure_build_screening_exposure_scenario",
        "exposure_build_product_use_evidence_from_nanomaterial",
        "exposure_run_verification_checks",
        "worker_route_task",
    }
)
REQUIRED_RESOURCE_URIS = frozenset(
    {
        "contracts://manifest",
        "verification://summary",
        "release://metadata-report",
    }
)
REQUIRED_PROMPT_NAMES = frozenset(
    {
        "exposure_refinement_playbook",
        "exposure_pbpk_handoff_checklist",
    }
)


@dataclass(frozen=True)
class StartupHealthSummary:
    """Compact startup validation summary for operators and CI."""

    defaults_version: str
    defaults_hash_sha256: str
    tool_count: int
    resource_count: int
    prompt_count: int


def _missing_items(observed: set[str], required: frozenset[str]) -> list[str]:
    return sorted(required.difference(observed))


def validate_server_startup(server: FastMCP) -> StartupHealthSummary:
    """Validate that the packaged runtime and published MCP surface are available."""

    provider_candidate = getattr(server, "_server_runtime_provider", None)
    if not isinstance(provider_candidate, ServerRuntimeProvider):
        raise RuntimeError("Server runtime provider is missing.")

    runtime_state = provider_candidate.get_runtime_state()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}
    resource_uris = {str(resource.uri) for resource in server._resource_manager.list_resources()}
    prompt_names = {prompt.name for prompt in server._prompt_manager.list_prompts()}

    missing_tools = _missing_items(tool_names, REQUIRED_TOOL_NAMES)
    if missing_tools:
        raise RuntimeError(f"Missing required tools: {', '.join(missing_tools)}")

    missing_resources = _missing_items(resource_uris, REQUIRED_RESOURCE_URIS)
    if missing_resources:
        raise RuntimeError(f"Missing required resources: {', '.join(missing_resources)}")

    missing_prompts = _missing_items(prompt_names, REQUIRED_PROMPT_NAMES)
    if missing_prompts:
        raise RuntimeError(f"Missing required prompts: {', '.join(missing_prompts)}")

    return StartupHealthSummary(
        defaults_version=runtime_state.defaults_registry.version,
        defaults_hash_sha256=runtime_state.defaults_registry.sha256,
        tool_count=len(tool_names),
        resource_count=len(resource_uris),
        prompt_count=len(prompt_names),
    )


def run_startup_healthcheck() -> StartupHealthSummary:
    """Build the server and validate startup health in one call."""

    server = create_mcp_server()
    return validate_server_startup(cast(FastMCP, server))
