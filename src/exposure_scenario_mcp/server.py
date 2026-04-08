"""FastMCP server definition for Exposure Scenario MCP."""

from __future__ import annotations

import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest
from exposure_scenario_mcp.contracts import (
    algorithm_notes,
    archetype_library_manifest,
    build_contract_manifest,
    build_examples,
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
    probability_bounds_profile_manifest,
    scenario_probability_package_manifest,
    schema_payloads,
    tier1_inhalation_parameter_manifest,
)
from exposure_scenario_mcp.defaults import (
    DefaultsRegistry,
    build_defaults_curation_report,
    defaults_evidence_map,
)
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.guidance import (
    archetype_library_guide,
    conformance_report_markdown,
    defaults_curation_report_markdown,
    exposure_platform_architecture_guide,
    goldset_benchmark_guide,
    inhalation_residual_air_reentry_guide,
    inhalation_tier_upgrade_guide,
    integrated_exposure_workflow_guide,
    operator_guide,
    probability_bounds_guide,
    provenance_policy,
    release_notes_markdown,
    release_readiness_markdown,
    result_status_semantics,
    security_provenance_review_markdown,
    tier1_inhalation_parameter_guide,
    troubleshooting_guide,
    uncertainty_framework,
    validation_coverage_report_markdown,
    validation_dossier_markdown,
    validation_framework,
    validation_reference_bands_guide,
    validation_time_series_packs_guide,
    worker_art_adapter_guide,
    worker_art_execution_guide,
    worker_art_external_exchange_guide,
    worker_dermal_adapter_guide,
    worker_dermal_bridge_guide,
    worker_dermal_execution_guide,
    worker_routing_guide,
    worker_tier2_bridge_guide,
)
from exposure_scenario_mcp.integrations import (
    ApplyProductUseEvidenceInput,
    AssessProductUseEvidenceFitInput,
    BuildProductUseEvidenceFromConsExpoInput,
    IntegratedExposureWorkflowResult,
    PbpkExternalImportPackage,
    ProductUseEvidenceFitReport,
    ProductUseEvidenceReconciliationReport,
    ProductUseEvidenceRecord,
    ReconcileProductUseEvidenceInput,
    RunIntegratedExposureWorkflowInput,
    ToxClawEvidenceBundle,
    ToxClawExposureRefinementBundle,
    apply_product_use_evidence,
    assess_product_use_evidence_fit,
    build_pbpk_external_import_package,
    build_product_use_evidence_from_consexpo,
    build_toxclaw_evidence_bundle,
    build_toxclaw_refinement_bundle,
    reconcile_product_use_evidence,
    run_integrated_exposure_workflow,
    suite_integration_guide,
)
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    BuildAggregateExposureScenarioInput,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    BuildParameterBoundsInput,
    BuildProbabilityBoundsFromProfileInput,
    BuildProbabilityBoundsFromScenarioPackageInput,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureEnvelopeSummary,
    ExposureScenario,
    ExposureScenarioRequest,
    InhalationResidualAirReentryScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParameterBoundsSummary,
    PbpkScenarioInput,
    ProbabilityBoundsProfileSummary,
    ScenarioComparisonRecord,
    ScenarioPackageProbabilitySummary,
    WorkerTaskRoutingDecision,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import (
    build_inhalation_residual_air_reentry_scenario,
    build_inhalation_tier_1_screening_scenario,
)
from exposure_scenario_mcp.probability_bounds import (
    build_probability_bounds_from_profile,
    build_probability_bounds_from_scenario_package,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.result_meta import build_tool_result_meta
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.uncertainty import (
    build_exposure_envelope,
    build_exposure_envelope_from_library,
    build_parameter_bounds_summary,
    enrich_scenario_uncertainty,
)
from exposure_scenario_mcp.validation import (
    build_validation_coverage_report,
    build_validation_dossier_report,
    validation_manifest,
    validation_reference_band_manifest,
    validation_time_series_reference_manifest,
)
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


def _success_result(message: str, payload_model) -> CallToolResult:
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="completed", payload_model=payload_model),
        content=[TextContent(type="text", text=message)],
        structuredContent=payload_model.model_dump(mode="json", by_alias=True),
    )


def _error_result(error: ExposureScenarioError) -> CallToolResult:
    return CallToolResult(
        _meta=build_tool_result_meta(result_status="failed", error=error),
        isError=True,
        content=[TextContent(type="text", text=error.as_text())],
    )


def create_mcp_server() -> FastMCP:
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    probability_profiles = ProbabilityBoundsProfileRegistry.load()
    scenario_probability_packages = ScenarioProbabilityPackageRegistry.load()
    tier1_inhalation_profiles = Tier1InhalationProfileRegistry.load()
    plugin_registry = PluginRegistry()
    plugin_registry.register(ScreeningScenarioPlugin())
    plugin_registry.register(InhalationScreeningPlugin())
    engine = ScenarioEngine(registry=plugin_registry, defaults_registry=defaults_registry)

    mcp = FastMCP("exposure_scenario_mcp")

    @mcp.tool(
        name="exposure_build_screening_exposure_scenario",
        annotations={
            "title": "Build Screening Exposure Scenario",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_screening_exposure_scenario(
        params: ExposureScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic dermal or oral screening scenario."""

        try:
            scenario = engine.build(params)
            return _success_result(
                f"Built {scenario.route.value} screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_screening_scenario",
        annotations={
            "title": "Build Inhalation Screening Scenario",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_inhalation_screening_scenario(
        params: InhalationScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic inhalation screening scenario."""

        try:
            scenario = engine.build(params)
            return _success_result(
                f"Built inhalation screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_residual_air_reentry_scenario",
        annotations={
            "title": "Build Inhalation Residual-Air Reentry Scenario",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_inhalation_residual_air_reentry_scenario(
        params: InhalationResidualAirReentryScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic residual-air reentry inhalation scenario."""

        try:
            scenario = build_inhalation_residual_air_reentry_scenario(
                params,
                defaults_registry,
            )
            scenario = enrich_scenario_uncertainty(engine, scenario)
            return _success_result(
                f"Built residual-air reentry inhalation scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_tier1_screening_scenario",
        annotations={
            "title": "Build Inhalation Tier 1 Screening Scenario",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_inhalation_tier1_screening_scenario(
        params: InhalationTier1ScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic Tier 1 inhalation scenario using NF/FF screening semantics."""

        try:
            scenario = build_inhalation_tier_1_screening_scenario(
                params,
                defaults_registry,
                profile_registry=tier1_inhalation_profiles,
            )
            scenario = enrich_scenario_uncertainty(engine, scenario)
            return _success_result(
                f"Built Tier 1 inhalation screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_exposure_envelope",
        annotations={
            "title": "Build Exposure Envelope",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_exposure_envelope(
        params: BuildExposureEnvelopeInput,
    ) -> Annotated[CallToolResult, ExposureEnvelopeSummary]:
        """Build a deterministic Tier B envelope from named scenario archetypes."""

        try:
            envelope = build_exposure_envelope(params, engine, defaults_registry)
            return _success_result(
                f"Built deterministic envelope {envelope.envelope_id}.",
                envelope,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_exposure_envelope_from_library",
        annotations={
            "title": "Build Exposure Envelope From Library",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_exposure_envelope_from_library(
        params: BuildExposureEnvelopeFromLibraryInput,
    ) -> Annotated[CallToolResult, ExposureEnvelopeSummary]:
        """Build a deterministic Tier B envelope from a packaged archetype-library set."""

        try:
            envelope = build_exposure_envelope_from_library(
                params,
                engine,
                defaults_registry,
                archetype_library,
            )
            return _success_result(
                f"Built library-backed envelope {envelope.envelope_id}.",
                envelope,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_parameter_bounds_summary",
        annotations={
            "title": "Build Parameter Bounds Summary",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_parameter_bounds_summary(
        params: BuildParameterBoundsInput,
    ) -> Annotated[CallToolResult, ParameterBoundsSummary]:
        """Build a deterministic Tier B bounds summary from explicit parameter ranges."""

        try:
            summary = build_parameter_bounds_summary(params, engine, defaults_registry)
            return _success_result(
                f"Built parameter bounds summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_probability_bounds_from_profile",
        annotations={
            "title": "Build Probability Bounds From Profile",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_probability_bounds_from_profile(
        params: BuildProbabilityBoundsFromProfileInput,
    ) -> Annotated[CallToolResult, ProbabilityBoundsProfileSummary]:
        """Build a Tier C single-driver probability-bounds summary from a packaged profile."""

        try:
            summary = build_probability_bounds_from_profile(
                params,
                engine,
                defaults_registry,
                probability_profiles,
            )
            return _success_result(
                f"Built probability-bounds summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_probability_bounds_from_scenario_package",
        annotations={
            "title": "Build Probability Bounds From Scenario Package",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_probability_bounds_from_scenario_package(
        params: BuildProbabilityBoundsFromScenarioPackageInput,
    ) -> Annotated[CallToolResult, ScenarioPackageProbabilitySummary]:
        """Build a Tier C coupled-driver probability-bounds summary from a packaged profile."""

        try:
            summary = build_probability_bounds_from_scenario_package(
                params,
                engine,
                defaults_registry,
                archetype_library,
                scenario_probability_packages,
            )
            return _success_result(
                f"Built scenario-package probability summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_aggregate_exposure_scenario",
        annotations={
            "title": "Build Aggregate Exposure Scenario",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_aggregate_exposure_scenario(
        params: BuildAggregateExposureScenarioInput,
    ) -> Annotated[CallToolResult, AggregateExposureSummary]:
        """Combine component scenarios into a simple additive aggregate exposure summary."""

        try:
            summary = aggregate_scenarios(params, defaults_registry)
            return _success_result(
                f"Built aggregate exposure summary {summary.scenario_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_assess_product_use_evidence_fit",
        annotations={
            "title": "Assess Product Use Evidence Fit",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_assess_product_use_evidence_fit(
        params: AssessProductUseEvidenceFitInput,
    ) -> Annotated[CallToolResult, ProductUseEvidenceFitReport]:
        """Assess whether external product-use evidence fits the current request."""

        try:
            report = assess_product_use_evidence_fit(params.request, params.evidence)
            return _success_result(
                f"Assessed product-use evidence fit for {report.chemical_id}.",
                report,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_apply_product_use_evidence",
        annotations={
            "title": "Apply Product Use Evidence",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
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
            return _success_result(
                f"Applied product-use evidence to request for {request.chemical_id}.",
                request,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_build_product_use_evidence_from_consexpo",
        annotations={
            "title": "Build Product Use Evidence From ConsExpo",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_build_product_use_evidence_from_consexpo(
        params: BuildProductUseEvidenceFromConsExpoInput,
    ) -> Annotated[CallToolResult, ProductUseEvidenceRecord]:
        """Map a ConsExpo fact-sheet record into the generic evidence contract."""

        try:
            evidence = build_product_use_evidence_from_consexpo(params.evidence)
            return _success_result(
                f"Built product-use evidence from ConsExpo for {evidence.chemical_id}.",
                evidence,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_reconcile_product_use_evidence",
        annotations={
            "title": "Reconcile Product Use Evidence",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
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
            return _success_result(
                f"Reconciled product-use evidence for {report.chemical_id}.",
                report,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_run_integrated_workflow",
        annotations={
            "title": "Run Integrated Exposure Workflow",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_run_integrated_workflow(
        params: RunIntegratedExposureWorkflowInput,
    ) -> Annotated[CallToolResult, IntegratedExposureWorkflowResult]:
        """Run the local evidence-to-scenario-to-PBPK workflow in one audited response."""

        try:
            result = run_integrated_exposure_workflow(params, registry=defaults_registry)
            return _success_result(
                f"Ran integrated workflow for {result.chemical_id}.",
                result,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_route_worker_task",
        annotations={
            "title": "Route Worker Task",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_route_worker_task(
        params: WorkerTaskRoutingInput,
    ) -> Annotated[CallToolResult, WorkerTaskRoutingDecision]:
        """Route a worker-tagged task to the best current MCP path or future adapter hook."""

        decision = route_worker_task(params, defaults_registry)
        return _success_result(
            f"Routed worker task for route {decision.route.value}.",
            decision,
        )

    @mcp.tool(
        name="exposure_export_worker_inhalation_tier2_bridge",
        annotations={
            "title": "Export Worker Inhalation Tier 2 Bridge",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_worker_inhalation_tier2_bridge(
        params: ExportWorkerInhalationTier2BridgeRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2BridgePackage]:
        """Export a normalized worker inhalation Tier 2 handoff package for a future adapter."""

        package = build_worker_inhalation_tier2_bridge(params, registry=defaults_registry)
        return _success_result(
            "Exported worker inhalation Tier 2 bridge package.",
            package,
        )

    @mcp.tool(
        name="worker_ingest_inhalation_tier2_task",
        annotations={
            "title": "Ingest Worker Inhalation Tier 2 Task",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_ingest_inhalation_tier2_task(
        params: WorkerInhalationTier2AdapterRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2AdapterIngestResult]:
        """Ingest a worker Tier 2 bridge payload and normalize it into an ART-side intake."""

        result = ingest_worker_inhalation_tier2_task(params, registry=defaults_registry)
        return _success_result(
            "Ingested worker inhalation Tier 2 task into an ART-side adapter envelope.",
            result,
        )

    @mcp.tool(
        name="worker_execute_inhalation_tier2_task",
        annotations={
            "title": "Execute Worker Inhalation Tier 2 Task",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_execute_inhalation_tier2_task_tool(
        params: ExecuteWorkerInhalationTier2Request,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2ExecutionResult]:
        """Execute a bounded ART-aligned worker inhalation screening estimate."""

        result = execute_worker_inhalation_tier2_task(params, registry=defaults_registry)
        return _success_result(
            "Executed worker inhalation Tier 2 task with the ART-aligned surrogate kernel.",
            result,
        )

    @mcp.tool(
        name="worker_export_inhalation_art_execution_package",
        annotations={
            "title": "Export Inhalation ART Execution Package",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_export_inhalation_art_execution_package_tool(
        params: ExportWorkerArtExecutionPackageRequest,
    ) -> Annotated[CallToolResult, WorkerArtExternalExecutionPackage]:
        """Export an ART-ready external execution package plus a result-import template."""

        result = export_worker_inhalation_art_execution_package(
            params,
            registry=defaults_registry,
        )
        return _success_result(
            "Exported worker inhalation ART external execution package.",
            result,
        )

    @mcp.tool(
        name="worker_import_inhalation_art_execution_result",
        annotations={
            "title": "Import Inhalation ART Execution Result",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_import_inhalation_art_execution_result_tool(
        params: ImportWorkerArtExecutionResultRequest,
    ) -> Annotated[CallToolResult, WorkerInhalationTier2ExecutionResult]:
        """Import a normalized external ART result into the governed worker execution schema."""

        result = import_worker_inhalation_art_execution_result(
            params,
            registry=defaults_registry,
        )
        return _success_result(
            "Imported external worker inhalation ART execution result.",
            result,
        )

    @mcp.tool(
        name="exposure_export_worker_dermal_absorbed_dose_bridge",
        annotations={
            "title": "Export Worker Dermal Absorbed-Dose Bridge",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_worker_dermal_absorbed_dose_bridge(
        params: ExportWorkerDermalAbsorbedDoseBridgeRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseBridgePackage]:
        """Export a normalized worker dermal absorbed-dose and PPE handoff package."""

        package = build_worker_dermal_absorbed_dose_bridge(params, registry=defaults_registry)
        return _success_result(
            "Exported worker dermal absorbed-dose bridge package.",
            package,
        )

    @mcp.tool(
        name="worker_ingest_dermal_absorbed_dose_task",
        annotations={
            "title": "Ingest Worker Dermal Absorbed-Dose Task",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_ingest_dermal_absorbed_dose_task(
        params: WorkerDermalAbsorbedDoseAdapterRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseAdapterIngestResult]:
        """Ingest a dermal absorbed-dose bridge payload into a PPE-aware adapter envelope."""

        result = ingest_worker_dermal_absorbed_dose_task(params, registry=defaults_registry)
        return _success_result(
            "Ingested worker dermal absorbed-dose task into a PPE-aware adapter envelope.",
            result,
        )

    @mcp.tool(
        name="worker_execute_dermal_absorbed_dose_task",
        annotations={
            "title": "Execute Worker Dermal Absorbed-Dose Task",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def worker_execute_dermal_absorbed_dose_task_tool(
        params: ExecuteWorkerDermalAbsorbedDoseRequest,
    ) -> Annotated[CallToolResult, WorkerDermalAbsorbedDoseExecutionResult]:
        """Execute a bounded PPE-aware worker dermal absorbed-dose estimate."""

        result = execute_worker_dermal_absorbed_dose_task(params, registry=defaults_registry)
        return _success_result(
            "Executed worker dermal absorbed-dose task with the PPE-aware screening kernel.",
            result,
        )

    @mcp.tool(
        name="exposure_export_pbpk_scenario_input",
        annotations={
            "title": "Export PBPK Scenario Input",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_pbpk_scenario_input(
        params: ExportPbpkScenarioInputRequest,
    ) -> Annotated[CallToolResult, PbpkScenarioInput]:
        """Export a PBPK-ready handoff object containing normalized dosing semantics."""

        try:
            pbpk_input = export_pbpk_input(params, defaults_registry)
            return _success_result(
                f"Exported PBPK handoff from scenario {pbpk_input.source_scenario_id}.",
                pbpk_input,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.tool(
        name="exposure_export_pbpk_external_import_bundle",
        annotations={
            "title": "Export PBPK External Import Bundle",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_pbpk_external_import_bundle(
        params: ExportPbpkExternalImportBundleRequest,
    ) -> Annotated[CallToolResult, PbpkExternalImportPackage]:
        """Export a PBPK MCP external-import payload template plus readiness report."""

        package = build_pbpk_external_import_package(params)
        return _success_result(
            (f"Exported PBPK external-import template for scenario {params.scenario.scenario_id}."),
            package,
        )

    @mcp.tool(
        name="exposure_export_toxclaw_evidence_bundle",
        annotations={
            "title": "Export ToxClaw Evidence Bundle",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_toxclaw_evidence_bundle(
        params: ExportToxClawEvidenceBundleRequest,
    ) -> Annotated[CallToolResult, ToxClawEvidenceBundle]:
        """Export deterministic ToxClaw evidence and report-section primitives."""

        bundle = build_toxclaw_evidence_bundle(params)
        return _success_result(
            (f"Exported ToxClaw evidence bundle for scenario {params.scenario.scenario_id}."),
            bundle,
        )

    @mcp.tool(
        name="exposure_export_toxclaw_refinement_bundle",
        annotations={
            "title": "Export ToxClaw Refinement Bundle",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_export_toxclaw_refinement_bundle(
        params: ExportToxClawRefinementBundleRequest,
    ) -> Annotated[CallToolResult, ToxClawExposureRefinementBundle]:
        """Export a ToxClaw-facing exposure refinement delta with workflow hooks."""

        bundle = build_toxclaw_refinement_bundle(params)
        return _success_result(
            (
                "Exported ToxClaw refinement bundle for baseline "
                f"{params.baseline.scenario_id} and comparison {params.comparison.scenario_id}."
            ),
            bundle,
        )

    @mcp.tool(
        name="exposure_compare_exposure_scenarios",
        annotations={
            "title": "Compare Exposure Scenarios",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def exposure_compare_exposure_scenarios(
        params: CompareExposureScenariosInput,
    ) -> Annotated[CallToolResult, ScenarioComparisonRecord]:
        """Compare two scenarios and return dose deltas plus assumption-level change records."""

        try:
            comparison = compare_scenarios(params, defaults_registry)
            return _success_result(
                (
                    f"Compared {comparison.baseline_scenario_id} against "
                    f"{comparison.comparison_scenario_id}."
                ),
                comparison,
            )
        except ExposureScenarioError as error:
            return _error_result(error)

    @mcp.resource("contracts://manifest")
    def contract_manifest() -> str:
        """Machine-readable contract manifest."""

        payload = build_contract_manifest(defaults_registry).model_dump(mode="json")
        return json.dumps(payload, indent=2)

    @mcp.resource("defaults://manifest")
    def defaults_manifest() -> str:
        """Versioned defaults manifest including hashes and source counts."""

        return json.dumps(defaults_registry.manifest(), indent=2)

    @mcp.resource("defaults://curation-report")
    def defaults_curation_report_resource() -> str:
        """Machine-readable parameter-branch curation report for defaults."""

        payload = build_defaults_curation_report(defaults_registry).model_dump(
            mode="json", by_alias=True
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("tier1-inhalation://manifest")
    def tier1_inhalation_manifest() -> str:
        """Machine-readable Tier 1 inhalation parameter and product-profile manifest."""

        return json.dumps(tier1_inhalation_parameter_manifest(), indent=2)

    @mcp.resource("archetypes://manifest")
    def packaged_archetypes_manifest() -> str:
        """Machine-readable packaged archetype-library manifest."""

        return json.dumps(archetype_library_manifest(), indent=2)

    @mcp.resource("probability-bounds://manifest")
    def packaged_probability_bounds_manifest() -> str:
        """Machine-readable packaged single-driver probability-bounds profile manifest."""

        return json.dumps(probability_bounds_profile_manifest(), indent=2)

    @mcp.resource("scenario-probability://manifest")
    def packaged_scenario_probability_manifest() -> str:
        """Machine-readable packaged coupled-driver scenario-package profile manifest."""

        return json.dumps(scenario_probability_package_manifest(), indent=2)

    @mcp.resource("docs://algorithm-notes")
    def docs_algorithm_notes() -> str:
        """Deterministic algorithm notes for the public engines."""

        return algorithm_notes()

    @mcp.resource("docs://archetype-library-guide")
    def docs_archetype_library_guide() -> str:
        """Guide to the packaged Tier B archetype library and its guardrails."""

        return archetype_library_guide()

    @mcp.resource("docs://probability-bounds-guide")
    def docs_probability_bounds_guide() -> str:
        """Guide to the packaged Tier C probability-bounds profiles."""

        return probability_bounds_guide()

    @mcp.resource("docs://tier1-inhalation-parameter-guide")
    def docs_tier1_inhalation_parameter_guide() -> str:
        """Guide to the packaged Tier 1 inhalation parameter and profile packs."""

        return tier1_inhalation_parameter_guide()

    @mcp.resource("docs://defaults-evidence-map")
    def docs_defaults_evidence_map() -> str:
        """Source register and interpretation notes for defaults and benchmarks."""

        return defaults_evidence_map(defaults_registry)

    @mcp.resource("docs://defaults-curation-report")
    def docs_defaults_curation_report() -> str:
        """Human-readable summary of curated and heuristic defaults branches."""

        return defaults_curation_report_markdown()

    @mcp.resource("docs://operator-guide")
    def docs_operator_guide() -> str:
        """Operator guide for transports, validation, and interpretation boundaries."""

        return operator_guide()

    @mcp.resource("docs://provenance-policy")
    def docs_provenance_policy() -> str:
        """Provenance and assumption-emission policy."""

        return provenance_policy()

    @mcp.resource("docs://result-status-semantics")
    def docs_result_status_semantics() -> str:
        """Non-breaking result-status conventions for tool-result metadata."""

        return result_status_semantics()

    @mcp.resource("docs://uncertainty-framework")
    def docs_uncertainty_framework() -> str:
        """Tier A/B uncertainty design and interpretation guide."""

        return uncertainty_framework()

    @mcp.resource("docs://inhalation-tier-upgrade-guide")
    def docs_inhalation_tier_upgrade_guide() -> str:
        """Guide to Tier 1 inhalation upgrade hooks and current boundaries."""

        return inhalation_tier_upgrade_guide()

    @mcp.resource("docs://inhalation-residual-air-reentry-guide")
    def docs_inhalation_residual_air_reentry_guide() -> str:
        """Guide to the residual-air reentry inhalation screening mode."""

        return inhalation_residual_air_reentry_guide()

    @mcp.resource("docs://validation-framework")
    def docs_validation_framework() -> str:
        """Validation and benchmark posture for route and mechanism domains."""

        return validation_framework()

    @mcp.resource("docs://goldset-benchmark-guide")
    def docs_goldset_benchmark_guide() -> str:
        """Human-readable guide to the externally anchored showcase goldset."""

        return goldset_benchmark_guide()

    @mcp.resource("docs://suite-integration-guide")
    def docs_suite_integration_guide() -> str:
        """Boundary and integration guide for the ToxMCP suite."""

        return suite_integration_guide()

    @mcp.resource("docs://integrated-exposure-workflow-guide")
    def docs_integrated_exposure_workflow_guide() -> str:
        """Guide to the evidence-to-scenario-to-PBPK workflow tool."""

        return integrated_exposure_workflow_guide()

    @mcp.resource("docs://exposure-platform-architecture")
    def docs_exposure_platform_architecture() -> str:
        """Architecture guide for splitting exposure, fate, dietary, and worker concerns."""

        return exposure_platform_architecture_guide()

    @mcp.resource("docs://worker-routing-guide")
    def docs_worker_routing_guide() -> str:
        """Guide to the current worker-task router and occupational escalation boundaries."""

        return worker_routing_guide()

    @mcp.resource("docs://worker-tier2-bridge-guide")
    def docs_worker_tier2_bridge_guide() -> str:
        """Guide to the worker inhalation Tier 2 bridge export and its current boundaries."""

        return worker_tier2_bridge_guide()

    @mcp.resource("docs://worker-art-adapter-guide")
    def docs_worker_art_adapter_guide() -> str:
        """Guide to the ART-side worker inhalation adapter ingest boundary."""

        return worker_art_adapter_guide()

    @mcp.resource("docs://worker-art-execution-guide")
    def docs_worker_art_execution_guide() -> str:
        """Guide to the executable ART-aligned worker inhalation screening kernel."""

        return worker_art_execution_guide()

    @mcp.resource("docs://worker-art-external-exchange-guide")
    def docs_worker_art_external_exchange_guide() -> str:
        """Guide to exporting ART execution packages and importing external ART results."""

        return worker_art_external_exchange_guide()

    @mcp.resource("docs://worker-dermal-bridge-guide")
    def docs_worker_dermal_bridge_guide() -> str:
        """Guide to the worker dermal absorbed-dose bridge export."""

        return worker_dermal_bridge_guide()

    @mcp.resource("docs://worker-dermal-adapter-guide")
    def docs_worker_dermal_adapter_guide() -> str:
        """Guide to the dermal absorbed-dose and PPE adapter ingest boundary."""

        return worker_dermal_adapter_guide()

    @mcp.resource("docs://worker-dermal-execution-guide")
    def docs_worker_dermal_execution_guide() -> str:
        """Guide to the executable worker dermal absorbed-dose screening kernel."""

        return worker_dermal_execution_guide()

    @mcp.resource("docs://troubleshooting")
    def docs_troubleshooting() -> str:
        """Troubleshooting guide for common request and export failures."""

        return troubleshooting_guide()

    @mcp.resource("docs://release-readiness")
    def docs_release_readiness() -> str:
        """Human-readable release-readiness guidance derived from the current surface."""

        report = build_release_readiness_report(defaults_registry)
        return release_readiness_markdown(report)

    @mcp.resource("docs://release-notes")
    def docs_release_notes() -> str:
        """Human-readable release notes for the current published candidate."""

        report = build_release_metadata_report(defaults_registry)
        return release_notes_markdown(report)

    @mcp.resource("docs://conformance-report")
    def docs_conformance_report() -> str:
        """Human-readable conformance summary for the current release candidate."""

        metadata = build_release_metadata_report(defaults_registry)
        readiness = build_release_readiness_report(defaults_registry)
        security_review = build_security_provenance_review_report(defaults_registry)
        return conformance_report_markdown(metadata, readiness, security_review)

    @mcp.resource("docs://security-provenance-review")
    def docs_security_provenance_review() -> str:
        """Human-readable security and provenance review derived from the current surface."""

        report = build_security_provenance_review_report(defaults_registry)
        return security_provenance_review_markdown(report)

    @mcp.resource("benchmarks://manifest")
    def benchmarks_manifest() -> str:
        """Benchmark corpus manifest used for deterministic regression checks."""

        return json.dumps(load_benchmark_manifest(), indent=2)

    @mcp.resource("benchmarks://goldset")
    def benchmarks_goldset_manifest() -> str:
        """Machine-readable showcase goldset with external source anchors and challenge tags."""

        return json.dumps(load_goldset_manifest(), indent=2)

    @mcp.resource("validation://manifest")
    def validation_manifest_resource() -> str:
        """Machine-readable validation and benchmark-domain metadata."""

        return json.dumps(validation_manifest(), indent=2)

    @mcp.resource("validation://dossier-report")
    def validation_dossier_report_resource() -> str:
        """Machine-readable validation dossier with coverage, references, and gaps."""

        payload = build_validation_dossier_report(defaults_registry).model_dump(
            mode="json", by_alias=True
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("validation://coverage-report")
    def validation_coverage_report_resource() -> str:
        """Machine-readable validation coverage and trust report by route mechanism."""

        payload = build_validation_coverage_report().model_dump(mode="json", by_alias=True)
        return json.dumps(payload, indent=2)

    @mcp.resource("validation://reference-bands")
    def validation_reference_bands_resource() -> str:
        """Machine-readable executable validation reference-band manifest."""

        return json.dumps(validation_reference_band_manifest(), indent=2)

    @mcp.resource("validation://time-series-packs")
    def validation_time_series_packs_resource() -> str:
        """Machine-readable executable validation time-series reference-pack manifest."""

        return json.dumps(validation_time_series_reference_manifest(), indent=2)

    @mcp.resource("docs://validation-dossier")
    def docs_validation_dossier() -> str:
        """Human-readable validation dossier with open evidence gaps and priorities."""

        return validation_dossier_markdown()

    @mcp.resource("docs://validation-coverage-report")
    def docs_validation_coverage_report() -> str:
        """Human-readable validation coverage and trust report."""

        return validation_coverage_report_markdown()

    @mcp.resource("docs://validation-reference-bands")
    def docs_validation_reference_bands() -> str:
        """Human-readable executable validation reference-band guide."""

        return validation_reference_bands_guide()

    @mcp.resource("docs://validation-time-series-packs")
    def docs_validation_time_series_packs() -> str:
        """Human-readable executable validation time-series reference-pack guide."""

        return validation_time_series_packs_guide()

    @mcp.resource("release://readiness-report")
    def release_readiness_report() -> str:
        """Machine-readable release-readiness report."""

        payload = build_release_readiness_report(defaults_registry).model_dump(
            mode="json", by_alias=True
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://metadata-report")
    def release_metadata_report() -> str:
        """Machine-readable release metadata report."""

        payload = build_release_metadata_report(defaults_registry).model_dump(
            mode="json", by_alias=True
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://security-provenance-review-report")
    def security_provenance_review_report() -> str:
        """Machine-readable security and provenance review report."""

        payload = build_security_provenance_review_report(defaults_registry).model_dump(
            mode="json", by_alias=True
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("schemas://{schema_name}")
    def schema_resource(schema_name: str) -> str:
        """JSON Schema for a public request or response model."""

        payload = schema_payloads()
        return json.dumps(payload[schema_name], indent=2)

    @mcp.resource("examples://{example_name}")
    def example_resource(example_name: str) -> str:
        """Generated example request or output payload."""

        payload = build_examples()
        return json.dumps(payload[example_name], indent=2)

    @mcp.prompt(name="exposure_refinement_playbook")
    def exposure_refinement_playbook(
        route: str, refinement_goal: str = "reduce uncertainty"
    ) -> str:
        """Prompt template for refining a screening scenario without losing provenance."""

        return (
            f"Review the {route} screening scenario and refine it to {refinement_goal}. "
            "Keep every changed assumption explicit, use scenario comparison and route-specific "
            "recalculation only as audit traces, consider aggregate variants when co-use matters, "
            "preserve route-specific units, avoid hidden defaults, "
            "and do not claim internal exposure or risk conclusions."
        )

    @mcp.prompt(name="exposure_pbpk_handoff_checklist")
    def exposure_pbpk_handoff_checklist(route: str) -> str:
        """Prompt template for validating a PBPK handoff."""

        return (
            f"Validate that the {route} exposure scenario has a PBPK-ready "
            "handoff: canonical dose units, explicit timing semantics, "
            "resolved population context, and a machine-readable "
            "assumption ledger."
        )

    return mcp
