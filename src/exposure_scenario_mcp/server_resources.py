"""Registrar for resources and prompts published by the MCP server."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

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
from exposure_scenario_mcp.defaults import build_defaults_curation_report, defaults_evidence_map
from exposure_scenario_mcp.guidance import (
    archetype_library_guide,
    capability_maturity_matrix_guide,
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
    repository_slug_decision_guide,
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
from exposure_scenario_mcp.integrations import suite_integration_guide
from exposure_scenario_mcp.server_context import ServerContext
from exposure_scenario_mcp.validation import (
    build_validation_coverage_report,
    build_validation_dossier_report,
    validation_manifest,
    validation_reference_band_manifest,
    validation_time_series_reference_manifest,
)


def register_resources(mcp: FastMCP, context: ServerContext) -> None:
    """Register machine-readable and human-readable resource endpoints."""

    @mcp.resource("contracts://manifest")
    def contract_manifest() -> str:
        """Machine-readable contract manifest."""

        payload = build_contract_manifest(context.defaults_registry).model_dump(mode="json")
        return json.dumps(payload, indent=2)

    @mcp.resource("defaults://manifest")
    def defaults_manifest() -> str:
        """Versioned defaults manifest including hashes and source counts."""

        return json.dumps(context.defaults_registry.manifest(), indent=2)

    @mcp.resource("defaults://curation-report")
    def defaults_curation_report_resource() -> str:
        """Machine-readable parameter-branch curation report for defaults."""

        payload = build_defaults_curation_report(context.defaults_registry).model_dump(
            mode="json",
            by_alias=True,
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

        return defaults_evidence_map(context.defaults_registry)

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

    @mcp.resource("docs://capability-maturity-matrix")
    def docs_capability_maturity_matrix() -> str:
        """One-page maturity framing for the released MCP surface."""

        return capability_maturity_matrix_guide()

    @mcp.resource("docs://repository-slug-decision")
    def docs_repository_slug_decision() -> str:
        """Decision note explaining why the current repository slug remains in use."""

        return repository_slug_decision_guide()

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

        report = build_release_readiness_report(context.defaults_registry)
        return release_readiness_markdown(report)

    @mcp.resource("docs://release-notes")
    def docs_release_notes() -> str:
        """Human-readable release notes for the current published candidate."""

        report = build_release_metadata_report(context.defaults_registry)
        return release_notes_markdown(report)

    @mcp.resource("docs://conformance-report")
    def docs_conformance_report() -> str:
        """Human-readable conformance summary for the current release candidate."""

        metadata = build_release_metadata_report(context.defaults_registry)
        readiness = build_release_readiness_report(context.defaults_registry)
        security_review = build_security_provenance_review_report(context.defaults_registry)
        return conformance_report_markdown(metadata, readiness, security_review)

    @mcp.resource("docs://security-provenance-review")
    def docs_security_provenance_review() -> str:
        """Human-readable security and provenance review derived from the current surface."""

        report = build_security_provenance_review_report(context.defaults_registry)
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

        payload = build_validation_dossier_report(context.defaults_registry).model_dump(
            mode="json",
            by_alias=True,
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

        payload = build_release_readiness_report(context.defaults_registry).model_dump(
            mode="json",
            by_alias=True,
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://metadata-report")
    def release_metadata_report() -> str:
        """Machine-readable release metadata report."""

        payload = build_release_metadata_report(context.defaults_registry).model_dump(
            mode="json",
            by_alias=True,
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://security-provenance-review-report")
    def security_provenance_review_report() -> str:
        """Machine-readable security and provenance review report."""

        payload = build_security_provenance_review_report(context.defaults_registry).model_dump(
            mode="json",
            by_alias=True,
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


def register_prompts(mcp: FastMCP) -> None:
    """Register prompt templates published by the MCP server."""

    @mcp.prompt(name="exposure_refinement_playbook")
    def exposure_refinement_playbook(
        route: str,
        refinement_goal: str = "reduce uncertainty",
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
