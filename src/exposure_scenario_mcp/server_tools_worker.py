"""Registrar for worker-routing, adapter, and bounded execution tools."""

from __future__ import annotations

from typing import Annotated, cast

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import WorkerTaskRoutingDecision, WorkerTaskRoutingInput
from exposure_scenario_mcp.server_context import (
    ServerContextProvider,
    ToolErrorResult,
    ToolSuccessResult,
    read_only_tool_annotations,
)
from exposure_scenario_mcp.server_errors import unexpected_tool_error
from exposure_scenario_mcp.worker_dermal import (
    ExecuteWorkerDermalAbsorbedDoseRequest,
    ExportWorkerDermalAbsorbedDoseBridgeRequest,
    WorkerDermalAbsorbedDoseAdapterIngestResult,
    WorkerDermalAbsorbedDoseAdapterRequest,
    WorkerDermalAbsorbedDoseBridgePackage,
    WorkerDermalAbsorbedDoseExecutionResult,
    build_worker_dermal_absorbed_dose_bridge,
    execute_worker_dermal_absorbed_dose_task,
    ingest_worker_dermal_absorbed_dose_task,
)
from exposure_scenario_mcp.worker_routing import route_worker_task
from exposure_scenario_mcp.worker_tier2 import (
    ExecuteWorkerInhalationTier2Request,
    ExportWorkerArtExecutionPackageRequest,
    ExportWorkerInhalationTier2BridgeRequest,
    ImportWorkerArtExecutionResultRequest,
    WorkerArtExternalExecutionPackage,
    WorkerInhalationTier2AdapterIngestResult,
    WorkerInhalationTier2AdapterRequest,
    WorkerInhalationTier2BridgePackage,
    WorkerInhalationTier2ExecutionResult,
    build_worker_inhalation_tier2_bridge,
    execute_worker_inhalation_tier2_task,
    export_worker_inhalation_art_execution_package,
    import_worker_inhalation_art_execution_result,
    ingest_worker_inhalation_tier2_task,
)


def register_worker_tools(
    mcp: FastMCP,
    context_provider: ServerContextProvider,
    success_result: ToolSuccessResult,
    error_result: ToolErrorResult,
) -> None:
    """Register worker routing, bridge, ingest, execute, and exchange tools."""

    @mcp.tool(
        name="worker_route_task",
        annotations=read_only_tool_annotations("Route Worker Task"),
    )
    def worker_route_task(
        params: WorkerTaskRoutingInput,
    ) -> Annotated[CallToolResult, WorkerTaskRoutingDecision]:
        """Route a worker-tagged task to the best current MCP path or future adapter hook."""

        try:
            context = context_provider()
            decision = route_worker_task(params, context.defaults_registry)
            return success_result(
                f"Routed worker task for route {decision.route.value}.",
                decision,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(unexpected_tool_error("worker_route_task", error))

    @mcp.tool(
        name="exposure_route_worker_task",
        annotations=read_only_tool_annotations("Route Worker Task (Legacy Alias)"),
    )
    def exposure_route_worker_task(
        params: WorkerTaskRoutingInput,
    ) -> Annotated[CallToolResult, WorkerTaskRoutingDecision]:
        """Legacy compatibility alias for worker_route_task."""

        try:
            return cast(CallToolResult, worker_route_task(params))
        except Exception as error:
            return error_result(unexpected_tool_error("exposure_route_worker_task", error))

    @mcp.tool(
        name="worker_export_inhalation_tier2_bridge",
        annotations=read_only_tool_annotations("Export Worker Inhalation Tier 2 Bridge"),
    )
    def worker_export_inhalation_tier2_bridge(
        params: ExportWorkerInhalationTier2BridgeRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2BridgePackage]:
        """Export a normalized worker inhalation Tier 2 handoff package for a future adapter."""

        try:
            context = context_provider()
            package = build_worker_inhalation_tier2_bridge(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Exported worker inhalation Tier 2 bridge package.",
                package,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_export_inhalation_tier2_bridge", error)
            )

    @mcp.tool(
        name="exposure_export_worker_inhalation_tier2_bridge",
        annotations=read_only_tool_annotations(
            "Export Worker Inhalation Tier 2 Bridge (Legacy Alias)"
        ),
    )
    def exposure_export_worker_inhalation_tier2_bridge(
        params: ExportWorkerInhalationTier2BridgeRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2BridgePackage]:
        """Legacy compatibility alias for worker_export_inhalation_tier2_bridge."""

        try:
            return cast(CallToolResult, worker_export_inhalation_tier2_bridge(params))
        except Exception as error:
            return error_result(
                unexpected_tool_error("exposure_export_worker_inhalation_tier2_bridge", error)
            )

    @mcp.tool(
        name="worker_ingest_inhalation_tier2_task",
        annotations=read_only_tool_annotations("Ingest Worker Inhalation Tier 2 Task"),
    )
    def worker_ingest_inhalation_tier2_task(
        params: WorkerInhalationTier2AdapterRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2AdapterIngestResult]:
        """Ingest a worker Tier 2 bridge payload and normalize it into an ART-side intake."""

        try:
            context = context_provider()
            result = ingest_worker_inhalation_tier2_task(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Ingested worker inhalation Tier 2 task into an ART-side adapter envelope.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_ingest_inhalation_tier2_task", error)
            )

    @mcp.tool(
        name="worker_execute_inhalation_tier2_task",
        annotations=read_only_tool_annotations("Execute Worker Inhalation Tier 2 Task"),
    )
    def worker_execute_inhalation_tier2_task_tool(
        params: ExecuteWorkerInhalationTier2Request,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2ExecutionResult]:
        """Execute a bounded ART-aligned worker inhalation screening estimate."""

        try:
            context = context_provider()
            result = execute_worker_inhalation_tier2_task(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Executed worker inhalation Tier 2 task with the ART-aligned surrogate kernel.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_execute_inhalation_tier2_task", error)
            )

    @mcp.tool(
        name="worker_export_inhalation_art_execution_package",
        annotations=read_only_tool_annotations("Export Inhalation ART Execution Package"),
    )
    def worker_export_inhalation_art_execution_package_tool(
        params: ExportWorkerArtExecutionPackageRequest,
    ) -> Annotated[CallToolResult, WorkerArtExternalExecutionPackage]:
        """Export an ART-ready external execution package plus a result-import template."""

        try:
            context = context_provider()
            result = export_worker_inhalation_art_execution_package(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Exported worker inhalation ART external execution package.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_export_inhalation_art_execution_package", error)
            )

    @mcp.tool(
        name="worker_import_inhalation_art_execution_result",
        annotations=read_only_tool_annotations("Import Inhalation ART Execution Result"),
    )
    def worker_import_inhalation_art_execution_result_tool(
        params: ImportWorkerArtExecutionResultRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2ExecutionResult]:
        """Import a normalized external ART result into the governed worker execution schema."""

        try:
            context = context_provider()
            result = import_worker_inhalation_art_execution_result(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Imported external worker inhalation ART execution result.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_import_inhalation_art_execution_result", error)
            )

    @mcp.tool(
        name="worker_export_dermal_absorbed_dose_bridge",
        annotations=read_only_tool_annotations("Export Worker Dermal Absorbed-Dose Bridge"),
    )
    def worker_export_dermal_absorbed_dose_bridge(
        params: ExportWorkerDermalAbsorbedDoseBridgeRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseBridgePackage]:
        """Export a normalized worker dermal absorbed-dose and PPE handoff package."""

        try:
            context = context_provider()
            package = build_worker_dermal_absorbed_dose_bridge(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Exported worker dermal absorbed-dose bridge package.",
                package,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_export_dermal_absorbed_dose_bridge", error)
            )

    @mcp.tool(
        name="exposure_export_worker_dermal_absorbed_dose_bridge",
        annotations=read_only_tool_annotations(
            "Export Worker Dermal Absorbed-Dose Bridge (Legacy Alias)"
        ),
    )
    def exposure_export_worker_dermal_absorbed_dose_bridge(
        params: ExportWorkerDermalAbsorbedDoseBridgeRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseBridgePackage]:
        """Legacy compatibility alias for worker_export_dermal_absorbed_dose_bridge."""

        try:
            return cast(CallToolResult, worker_export_dermal_absorbed_dose_bridge(params))
        except Exception as error:
            return error_result(
                unexpected_tool_error("exposure_export_worker_dermal_absorbed_dose_bridge", error)
            )

    @mcp.tool(
        name="worker_ingest_dermal_absorbed_dose_task",
        annotations=read_only_tool_annotations("Ingest Worker Dermal Absorbed-Dose Task"),
    )
    def worker_ingest_dermal_absorbed_dose_task(
        params: WorkerDermalAbsorbedDoseAdapterRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseAdapterIngestResult]:
        """Ingest a dermal absorbed-dose bridge payload into a PPE-aware adapter envelope."""

        try:
            context = context_provider()
            result = ingest_worker_dermal_absorbed_dose_task(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Ingested worker dermal absorbed-dose task into a PPE-aware adapter envelope.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_ingest_dermal_absorbed_dose_task", error)
            )

    @mcp.tool(
        name="worker_execute_dermal_absorbed_dose_task",
        annotations=read_only_tool_annotations("Execute Worker Dermal Absorbed-Dose Task"),
    )
    def worker_execute_dermal_absorbed_dose_task_tool(
        params: ExecuteWorkerDermalAbsorbedDoseRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseExecutionResult]:
        """Execute a bounded PPE-aware worker dermal absorbed-dose estimate."""

        try:
            context = context_provider()
            result = execute_worker_dermal_absorbed_dose_task(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                "Executed worker dermal absorbed-dose task with the PPE-aware screening kernel.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
        except Exception as error:
            return error_result(
                unexpected_tool_error("worker_execute_dermal_absorbed_dose_task", error)
            )
