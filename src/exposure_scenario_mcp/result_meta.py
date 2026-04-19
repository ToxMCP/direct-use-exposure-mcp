"""Future-safe tool result metadata helpers."""

from __future__ import annotations

from typing import Literal

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import ToolResultMeta
from exposure_scenario_mcp.server_errors import classify_mcp_error_code


def response_schema_name(payload_model) -> str | None:
    schema_version = getattr(payload_model, "schema_version", None)
    return schema_version if isinstance(schema_version, str) else None


def build_tool_result_meta(
    *,
    result_status: Literal["accepted", "running", "completed", "failed"],
    payload_model=None,
    error: ExposureScenarioError | None = None,
) -> dict:
    is_terminal = result_status in {"completed", "failed"}
    return ToolResultMeta(
        executionMode="sync",
        resultStatus=result_status,
        terminal=is_terminal,
        futureAsyncCompatible=True,
        queueRequired=False,
        responseSchema=response_schema_name(payload_model) if payload_model is not None else None,
        jobId=None,
        statusCheckUri=None,
        retryable=False,
        errorCode=error.code if error is not None else None,
        mcpErrorCode=classify_mcp_error_code(error),
        notes=[
            (
                "Synchronous v0.1 response using a status vocabulary "
                "reserved for future async engines."
            ),
            ("No queue or polling step is required for the current deterministic implementation."),
        ],
    ).model_dump(mode="json", by_alias=True)
