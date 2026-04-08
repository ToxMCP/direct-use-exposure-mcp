"""Registrar for core deterministic scenario and export tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    PbpkExternalImportPackage,
    ToxClawEvidenceBundle,
    ToxClawExposureRefinementBundle,
    build_pbpk_external_import_package,
    build_toxclaw_evidence_bundle,
    build_toxclaw_refinement_bundle,
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
)
from exposure_scenario_mcp.plugins.inhalation import (
    build_inhalation_residual_air_reentry_scenario,
    build_inhalation_tier_1_screening_scenario,
)
from exposure_scenario_mcp.probability_bounds import (
    build_probability_bounds_from_profile,
    build_probability_bounds_from_scenario_package,
)
from exposure_scenario_mcp.runtime import (
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.server_context import (
    ServerContext,
    ToolErrorResult,
    ToolSuccessResult,
    read_only_tool_annotations,
)
from exposure_scenario_mcp.uncertainty import (
    build_exposure_envelope,
    build_exposure_envelope_from_library,
    build_parameter_bounds_summary,
    enrich_scenario_uncertainty,
)


def register_core_tools(
    mcp: FastMCP,
    context: ServerContext,
    success_result: ToolSuccessResult,
    error_result: ToolErrorResult,
) -> None:
    """Register the core deterministic scenario, comparison, and export tools."""

    @mcp.tool(
        name="exposure_build_screening_exposure_scenario",
        annotations=read_only_tool_annotations("Build Screening Exposure Scenario"),
    )
    def exposure_build_screening_exposure_scenario(
        params: ExposureScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic dermal or oral screening scenario."""

        try:
            scenario = context.engine.build(params)
            return success_result(
                f"Built {scenario.route.value} screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_screening_scenario",
        annotations=read_only_tool_annotations("Build Inhalation Screening Scenario"),
    )
    def exposure_build_inhalation_screening_scenario(
        params: InhalationScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic inhalation screening scenario."""

        try:
            scenario = context.engine.build(params)
            return success_result(
                f"Built inhalation screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_residual_air_reentry_scenario",
        annotations=read_only_tool_annotations("Build Inhalation Residual-Air Reentry Scenario"),
    )
    def exposure_build_inhalation_residual_air_reentry_scenario(
        params: InhalationResidualAirReentryScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic residual-air reentry inhalation scenario."""

        try:
            scenario = build_inhalation_residual_air_reentry_scenario(
                params,
                context.defaults_registry,
            )
            scenario = enrich_scenario_uncertainty(context.engine, scenario)
            return success_result(
                f"Built residual-air reentry inhalation scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_inhalation_tier1_screening_scenario",
        annotations=read_only_tool_annotations("Build Inhalation Tier 1 Screening Scenario"),
    )
    def exposure_build_inhalation_tier1_screening_scenario(
        params: InhalationTier1ScenarioRequest,
    ) -> Annotated[CallToolResult, ExposureScenario]:
        """Build one deterministic Tier 1 inhalation scenario using NF/FF screening semantics."""

        try:
            scenario = build_inhalation_tier_1_screening_scenario(
                params,
                context.defaults_registry,
                profile_registry=context.tier1_inhalation_profiles,
            )
            scenario = enrich_scenario_uncertainty(context.engine, scenario)
            return success_result(
                f"Built Tier 1 inhalation screening scenario {scenario.scenario_id}.",
                scenario,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_exposure_envelope",
        annotations=read_only_tool_annotations("Build Exposure Envelope"),
    )
    def exposure_build_exposure_envelope(
        params: BuildExposureEnvelopeInput,
    ) -> Annotated[CallToolResult, ExposureEnvelopeSummary]:
        """Build a deterministic Tier B envelope from named scenario archetypes."""

        try:
            envelope = build_exposure_envelope(
                params,
                context.engine,
                context.defaults_registry,
            )
            return success_result(
                f"Built deterministic envelope {envelope.envelope_id}.",
                envelope,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_exposure_envelope_from_library",
        annotations=read_only_tool_annotations("Build Exposure Envelope From Library"),
    )
    def exposure_build_exposure_envelope_from_library(
        params: BuildExposureEnvelopeFromLibraryInput,
    ) -> Annotated[CallToolResult, ExposureEnvelopeSummary]:
        """Build a deterministic Tier B envelope from a packaged archetype-library set."""

        try:
            envelope = build_exposure_envelope_from_library(
                params,
                context.engine,
                context.defaults_registry,
                context.archetype_library,
            )
            return success_result(
                f"Built library-backed envelope {envelope.envelope_id}.",
                envelope,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_parameter_bounds_summary",
        annotations=read_only_tool_annotations("Build Parameter Bounds Summary"),
    )
    def exposure_build_parameter_bounds_summary(
        params: BuildParameterBoundsInput,
    ) -> Annotated[CallToolResult, ParameterBoundsSummary]:
        """Build a deterministic Tier B bounds summary from explicit parameter ranges."""

        try:
            summary = build_parameter_bounds_summary(
                params,
                context.engine,
                context.defaults_registry,
            )
            return success_result(
                f"Built parameter bounds summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_probability_bounds_from_profile",
        annotations=read_only_tool_annotations("Build Probability Bounds From Profile"),
    )
    def exposure_build_probability_bounds_from_profile(
        params: BuildProbabilityBoundsFromProfileInput,
    ) -> Annotated[CallToolResult, ProbabilityBoundsProfileSummary]:
        """Build a Tier C single-driver probability-bounds summary from a packaged profile."""

        try:
            summary = build_probability_bounds_from_profile(
                params,
                context.engine,
                context.defaults_registry,
                context.probability_profiles,
            )
            return success_result(
                f"Built probability-bounds summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_probability_bounds_from_scenario_package",
        annotations=read_only_tool_annotations("Build Probability Bounds From Scenario Package"),
    )
    def exposure_build_probability_bounds_from_scenario_package(
        params: BuildProbabilityBoundsFromScenarioPackageInput,
    ) -> Annotated[CallToolResult, ScenarioPackageProbabilitySummary]:
        """Build a Tier C coupled-driver probability-bounds summary from a packaged profile."""

        try:
            summary = build_probability_bounds_from_scenario_package(
                params,
                context.engine,
                context.defaults_registry,
                context.archetype_library,
                context.scenario_probability_packages,
            )
            return success_result(
                f"Built scenario-package probability summary {summary.summary_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_build_aggregate_exposure_scenario",
        annotations=read_only_tool_annotations("Build Aggregate Exposure Scenario"),
    )
    def exposure_build_aggregate_exposure_scenario(
        params: BuildAggregateExposureScenarioInput,
    ) -> Annotated[CallToolResult, AggregateExposureSummary]:
        """Combine component scenarios into a simple additive aggregate exposure summary."""

        try:
            summary = aggregate_scenarios(params, context.defaults_registry)
            return success_result(
                f"Built aggregate exposure summary {summary.scenario_id}.",
                summary,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_export_pbpk_scenario_input",
        annotations=read_only_tool_annotations("Export PBPK Scenario Input"),
    )
    def exposure_export_pbpk_scenario_input(
        params: ExportPbpkScenarioInputRequest,
    ) -> Annotated[CallToolResult, PbpkScenarioInput]:
        """Export a PBPK-ready handoff object containing normalized dosing semantics."""

        try:
            pbpk_input = export_pbpk_input(params, context.defaults_registry)
            return success_result(
                f"Exported PBPK handoff from scenario {pbpk_input.source_scenario_id}.",
                pbpk_input,
            )
        except ExposureScenarioError as error:
            return error_result(error)

    @mcp.tool(
        name="exposure_export_pbpk_external_import_bundle",
        annotations=read_only_tool_annotations("Export PBPK External Import Bundle"),
    )
    def exposure_export_pbpk_external_import_bundle(
        params: ExportPbpkExternalImportBundleRequest,
    ) -> Annotated[CallToolResult, PbpkExternalImportPackage]:
        """Export a PBPK MCP external-import payload template plus readiness report."""

        package = build_pbpk_external_import_package(params)
        return success_result(
            f"Exported PBPK external-import template for scenario {params.scenario.scenario_id}.",
            package,
        )

    @mcp.tool(
        name="exposure_export_toxclaw_evidence_bundle",
        annotations=read_only_tool_annotations("Export ToxClaw Evidence Bundle"),
    )
    def exposure_export_toxclaw_evidence_bundle(
        params: ExportToxClawEvidenceBundleRequest,
    ) -> Annotated[CallToolResult, ToxClawEvidenceBundle]:
        """Export deterministic ToxClaw evidence and report-section primitives."""

        bundle = build_toxclaw_evidence_bundle(params)
        return success_result(
            f"Exported ToxClaw evidence bundle for scenario {params.scenario.scenario_id}.",
            bundle,
        )

    @mcp.tool(
        name="exposure_export_toxclaw_refinement_bundle",
        annotations=read_only_tool_annotations("Export ToxClaw Refinement Bundle"),
    )
    def exposure_export_toxclaw_refinement_bundle(
        params: ExportToxClawRefinementBundleRequest,
    ) -> Annotated[CallToolResult, ToxClawExposureRefinementBundle]:
        """Export a ToxClaw-facing exposure refinement delta with workflow hooks."""

        bundle = build_toxclaw_refinement_bundle(params)
        return success_result(
            (
                "Exported ToxClaw refinement bundle for baseline "
                f"{params.baseline.scenario_id} and comparison {params.comparison.scenario_id}."
            ),
            bundle,
        )

    @mcp.tool(
        name="exposure_compare_exposure_scenarios",
        annotations=read_only_tool_annotations("Compare Exposure Scenarios"),
    )
    def exposure_compare_exposure_scenarios(
        params: CompareExposureScenariosInput,
    ) -> Annotated[CallToolResult, ScenarioComparisonRecord]:
        """Compare two scenarios and return dose deltas plus assumption-level change records."""

        try:
            comparison = compare_scenarios(params, context.defaults_registry)
            return success_result(
                (
                    f"Compared {comparison.baseline_scenario_id} against "
                    f"{comparison.comparison_scenario_id}."
                ),
                comparison,
            )
        except ExposureScenarioError as error:
            return error_result(error)
