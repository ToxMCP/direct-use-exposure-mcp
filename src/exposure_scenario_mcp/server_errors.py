"""Server-boundary error helpers for tool and transport normalization."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS, CallToolResult

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


class _ErrorResultPassthroughMetadata(FuncMetadata):
    """Tool metadata that returns failed results without success-schema validation.

    FastMCP validates the `structuredContent` of every returned `CallToolResult` against the
    tool's output model, even when `isError` is set. Failed results carry no success payload,
    so that check replaced the structured domain error with a pydantic validation message and
    dropped the failed-result `_meta`. MCP clients likewise skip output validation for errors.
    """

    def convert_result(self, result: Any) -> Any:
        if isinstance(result, CallToolResult) and result.isError:
            return result
        return super().convert_result(result)


def preserve_tool_error_results(mcp: FastMCP) -> None:
    """Deliver failed tool results to clients exactly as the registered tools built them."""

    for tool in mcp._tool_manager.list_tools():
        if not isinstance(tool.fn_metadata, _ErrorResultPassthroughMetadata):
            tool.fn_metadata = _ErrorResultPassthroughMetadata.model_construct(
                **dict(tool.fn_metadata)
            )
