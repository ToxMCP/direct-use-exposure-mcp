"""Registrar for evidence-normalization and integrated workflow tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    ApplyProductUseEvidenceInput,
    AssessProductUseEvidenceFitInput,
    BuildProductUseEvidenceFromConsExpoInput,
    IntegratedExposureWorkflowResult,
    ProductUseEvidenceFitReport,
    ProductUseEvidenceReconciliationReport,
    ProductUseEvidenceRecord,
    ReconcileProductUseEvidenceInput,
    RunIntegratedExposureWorkflowInput,
    apply_product_use_evidence,
    assess_product_use_evidence_fit,
    build_product_use_evidence_from_consexpo,
    reconcile_product_use_evidence,
    run_integrated_exposure_workflow,
)
from exposure_scenario_mcp.models import ExposureScenarioRequest
from exposure_scenario_mcp.server_context import (
    ServerContext,
    ToolErrorResult,
    ToolSuccessResult,
    read_only_tool_annotations,
)


def register_integration_tools(
    mcp: FastMCP,
    context: ServerContext,
    success_result: ToolSuccessResult,
    error_result: ToolErrorResult,
) -> None:
    """Register evidence-fit, reconciliation, and integrated workflow tools."""

    @mcp.tool(
        name="exposure_assess_product_use_evidence_fit",
        annotations=read_only_tool_annotations("Assess Product Use Evidence Fit"),
    )
    def exposure_assess_product_use_evidence_fit(
        params: AssessProductUseEvidenceFitInput,
    ) -> Annotated[CallToolResult, ProductUseEvidenceFitReport]:
        """Assess whether external product-use evidence fits the current request."""

        try:
            report = assess_product_use_evidence_fit(params.request, params.evidence)
            return success_result(
                f"Assessed product-use evidence fit for {report.chemical_id}.",
                report,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_apply_product_use_evidence",
        annotations=read_only_tool_annotations("Apply Product Use Evidence"),
    )
    def exposure_apply_product_use_evidence(
        params: ApplyProductUseEvidenceInput,
    ) -> Annotated[CallToolResult, ExposureScenarioRequest]:
        """Apply external product-use evidence to a scenario request when it fits."""

        try:
            request = apply_product_use_evidence(
                params.request,
                params.evidence,
                require_auto_apply_safe=params.require_auto_apply_safe,
            )
            return success_result(
                f"Applied product-use evidence to request for {request.chemical_id}.",
                request,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_product_use_evidence_from_consexpo",
        annotations=read_only_tool_annotations("Build Product Use Evidence From ConsExpo"),
    )
    def exposure_build_product_use_evidence_from_consexpo(
        params: BuildProductUseEvidenceFromConsExpoInput,
    ) -> Annotated[CallToolResult, ProductUseEvidenceRecord]:
        """Map a ConsExpo fact-sheet record into the generic evidence contract."""

        try:
            evidence = build_product_use_evidence_from_consexpo(params.evidence)
            return success_result(
                f"Built product-use evidence from ConsExpo for {evidence.chemical_id}.",
                evidence,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_reconcile_product_use_evidence",
        annotations=read_only_tool_annotations("Reconcile Product Use Evidence"),
    )
    def exposure_reconcile_product_use_evidence(
        params: ReconcileProductUseEvidenceInput,
    ) -> Annotated[CallToolResult, ProductUseEvidenceReconciliationReport]:
        """Compare multiple evidence sources and build a merged request preview."""

        try:
            report = reconcile_product_use_evidence(
                params.request,
                params.evidence_records,
                require_auto_apply_safe=params.require_auto_apply_safe,
            )
            return success_result(
                f"Reconciled product-use evidence for {report.chemical_id}.",
                report,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_run_integrated_workflow",
        annotations=read_only_tool_annotations("Run Integrated Exposure Workflow"),
    )
    def exposure_run_integrated_workflow(
        params: RunIntegratedExposureWorkflowInput,
    ) -> Annotated[CallToolResult, IntegratedExposureWorkflowResult]:
        """Run the local evidence-to-scenario-to-PBPK workflow in one audited response."""

        try:
            result = run_integrated_exposure_workflow(
                params,
                registry=context.defaults_registry,
            )
            return success_result(
                f"Ran integrated workflow for {result.chemical_id}.",
                result,
            )
        except ExposureScenarioError as error:
            return error_result(error)
