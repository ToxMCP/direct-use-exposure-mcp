"""Future-safe tool result metadata helpers."""

from __future__ import annotations

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import ToolResultMeta


def response_schema_name(payload_model) -> str | None:
    schema_version = getattr(payload_model, "schema_version", None)
    return schema_version if isinstance(schema_version, str) else None


def build_tool_result_meta(
    *,
    result_status: str,
    payload_model=None,
    error: ExposureScenarioError | None = None,
) -> dict:
    is_terminal = result_status in {"completed", "failed"}
    return ToolResultMeta(
        execution_mode="sync",
        result_status=result_status,
        terminal=is_terminal,
        future_async_compatible=True,
        queue_required=False,
        response_schema=response_schema_name(payload_model) if payload_model is not None else None,
        job_id=None,
        status_check_uri=None,
        retryable=False,
        error_code=error.code if error is not None else None,
        notes=[
            (
                "Synchronous v0.1 response using a status vocabulary "
                "reserved for future async engines."
            ),
            ("No queue or polling step is required for the current deterministic implementation."),
        ],
    ).model_dump(mode="json", by_alias=True)
