"""Server-boundary error helpers for tool and transport normalization."""

from __future__ import annotations

from mcp.types import INTERNAL_ERROR, INVALID_PARAMS

from exposure_scenario_mcp.errors import ExposureScenarioError


def classify_mcp_error_code(error: ExposureScenarioError | None) -> int | None:
    """Map domain-facing tool errors onto generic MCP protocol error families."""

    if error is None:
        return None
    if error.code == "InternalError":
        return INTERNAL_ERROR
    return INVALID_PARAMS


def unexpected_tool_error(tool_name: str, error: Exception) -> ExposureScenarioError:
    """Wrap an unexpected tool exception in a transport-safe structured error."""

    return ExposureScenarioError(
        code="InternalError",
        message=f"Unexpected failure while executing `{tool_name}`.",
        suggestion="Retry the tool call. If the failure persists, inspect server logs.",
        details={
            "toolName": tool_name,
            "exceptionType": type(error).__name__,
        },
    )
