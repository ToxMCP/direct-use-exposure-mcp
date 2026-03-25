"""FastMCP server definition for Exposure Scenario MCP."""

from __future__ import annotations

import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.contracts import (
    algorithm_notes,
    build_contract_manifest,
    build_examples,
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
    schema_payloads,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry, defaults_evidence_map
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.guidance import (
    conformance_report_markdown,
    operator_guide,
    provenance_policy,
    release_notes_markdown,
    release_readiness_markdown,
    result_status_semantics,
    security_provenance_review_markdown,
    troubleshooting_guide,
    uncertainty_framework,
    validation_framework,
)
from exposure_scenario_mcp.integrations import (
    PbpkExternalImportPackage,
    ToxClawEvidenceBundle,
    ToxClawExposureRefinementBundle,
    build_pbpk_external_import_package,
    build_toxclaw_evidence_bundle,
    build_toxclaw_refinement_bundle,
    suite_integration_guide,
)
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    BuildAggregateExposureScenarioInput,
    BuildExposureEnvelopeInput,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureEnvelopeSummary,
    ExposureScenario,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    PbpkScenarioInput,
    ScenarioComparisonRecord,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.result_meta import build_tool_result_meta
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.uncertainty import build_exposure_envelope
from exposure_scenario_mcp.validation import validation_manifest


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
            (
                "Exported PBPK external-import template for "
                f"scenario {params.scenario.scenario_id}."
            ),
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
            (
                "Exported ToxClaw evidence bundle for "
                f"scenario {params.scenario.scenario_id}."
            ),
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

    @mcp.resource("docs://algorithm-notes")
    def docs_algorithm_notes() -> str:
        """Deterministic algorithm notes for the public engines."""

        return algorithm_notes()

    @mcp.resource("docs://defaults-evidence-map")
    def docs_defaults_evidence_map() -> str:
        """Source register and interpretation notes for defaults and benchmarks."""

        return defaults_evidence_map(defaults_registry)

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

    @mcp.resource("docs://validation-framework")
    def docs_validation_framework() -> str:
        """Validation and benchmark posture for route and mechanism domains."""

        return validation_framework()

    @mcp.resource("docs://suite-integration-guide")
    def docs_suite_integration_guide() -> str:
        """Boundary and integration guide for the ToxMCP suite."""

        return suite_integration_guide()

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

    @mcp.resource("validation://manifest")
    def validation_manifest_resource() -> str:
        """Machine-readable validation and benchmark-domain metadata."""

        return json.dumps(validation_manifest(), indent=2)

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
