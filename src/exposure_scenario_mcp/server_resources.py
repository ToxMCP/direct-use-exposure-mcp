"""Registrar for resources and prompts published by the MCP server."""

from __future__ import annotations

import json
from types import MethodType

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS, ErrorData

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest
from exposure_scenario_mcp.contracts import (
    algorithm_notes,
    archetype_library_manifest,
    build_contract_manifest,
    build_examples,
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
    build_verification_summary_report,
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
    cross_mcp_contract_guide,
    defaults_curation_report_markdown,
    deployment_hardening_guide,
    exposure_platform_architecture_guide,
    goldset_benchmark_guide,
    herbal_medicinal_routing_guide,
    http_audit_operations_guide,
    inhalation_residual_air_reentry_guide,
    inhalation_tier_upgrade_guide,
    integrated_exposure_workflow_guide,
    operator_guide,
    probability_bounds_guide,
    provenance_policy,
    red_team_review_memo_guide,
    release_notes_markdown,
    release_readiness_markdown,
    release_trust_checklist_guide,
    repository_slug_decision_guide,
    result_status_semantics,
    security_provenance_review_markdown,
    service_selection_guide,
    test_evidence_summary_guide,
    tier1_inhalation_parameter_guide,
    toxmcp_suite_index_guide,
    troubleshooting_guide,
    uncertainty_framework,
    validation_coverage_report_markdown,
    validation_dossier_markdown,
    validation_framework,
    validation_reference_bands_guide,
    validation_time_series_packs_guide,
    verification_summary_guide,
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
from exposure_scenario_mcp.server_context import ServerContextProvider
from exposure_scenario_mcp.validation import (
    build_validation_coverage_report,
    build_validation_dossier_report,
    validation_manifest,
    validation_reference_band_manifest,
    validation_time_series_reference_manifest,
)


def _resource_error(
    *,
    code: int,
    message: str,
    uri: str,
    resource_type: str | None = None,
    resource_name: str | None = None,
    exception_type: str | None = None,
) -> McpError:
    data: dict[str, str] = {"resourceUri": uri}
    if resource_type is not None:
        data["resourceType"] = resource_type
    if resource_name is not None:
        data["resourceName"] = resource_name
    if exception_type is not None:
        data["exceptionType"] = exception_type
    return McpError(ErrorData(code=code, message=message, data=data))


def register_resources(mcp: FastMCP, context_provider: ServerContextProvider) -> None:
    """Register machine-readable and human-readable resource endpoints."""

    def active_defaults_registry():
        return context_provider().defaults_registry

    @mcp.resource("contracts://manifest")
    def contract_manifest() -> str:
        """Machine-readable contract manifest."""

        payload = build_contract_manifest(active_defaults_registry()).model_dump(mode="json")
        return json.dumps(payload, indent=2)

    @mcp.resource("defaults://manifest")
    def defaults_manifest() -> str:
        """Versioned defaults manifest including hashes and source counts."""

        return json.dumps(active_defaults_registry().manifest(), indent=2)

    @mcp.resource("defaults://curation-report")
    def defaults_curation_report_resource() -> str:
        """Machine-readable parameter-branch curation report for defaults."""

        payload = build_defaults_curation_report(active_defaults_registry()).model_dump(
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

        return defaults_evidence_map(active_defaults_registry())

    @mcp.resource("docs://defaults-curation-report")
    def docs_defaults_curation_report() -> str:
        """Human-readable summary of curated and heuristic defaults branches."""

        return defaults_curation_report_markdown()

    @mcp.resource("docs://operator-guide")
    def docs_operator_guide() -> str:
        """Operator guide for transports, validation, and interpretation boundaries."""

        return operator_guide()

    @mcp.resource("docs://deployment-hardening-guide")
    def docs_deployment_hardening_guide() -> str:
        """Guide to externally hardening remote streamable-http deployments."""

        return deployment_hardening_guide()

    @mcp.resource("docs://http-audit-operations-guide")
    def docs_http_audit_operations_guide() -> str:
        """Guide to replaying, retaining, and debugging HTTP audit events."""

        return http_audit_operations_guide()

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

    @mcp.resource("docs://red-team-review-memo")
    def docs_red_team_review_memo() -> str:
        """Adversarial review memo describing the strongest credible attacks on the MCP."""

        return red_team_review_memo_guide()

    @mcp.resource("docs://cross-mcp-contract-guide")
    def docs_cross_mcp_contract_guide() -> str:
        """Guide to the shared suite-facing contracts published by Direct-Use Exposure MCP."""

        return cross_mcp_contract_guide()

    @mcp.resource("docs://service-selection-guide")
    def docs_service_selection_guide() -> str:
        """Guide to routing questions and handoffs across the ToxMCP service boundaries."""

        return service_selection_guide()

    @mcp.resource("docs://herbal-medicinal-routing-guide")
    def docs_herbal_medicinal_routing_guide() -> str:
        """Guide to routing TCM, herbal medicine, and supplement cases cleanly across the stack."""

        return herbal_medicinal_routing_guide()

    @mcp.resource("docs://toxmcp-suite-index")
    def docs_toxmcp_suite_index() -> str:
        """One-page orientation guide to the current ToxMCP service family."""

        return toxmcp_suite_index_guide()

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

        report = build_release_readiness_report(active_defaults_registry())
        return release_readiness_markdown(report)

    @mcp.resource("docs://release-trust-checklist")
    def docs_release_trust_checklist() -> str:
        """Human-readable checklist for public-release trust posture and sign-off."""

        return release_trust_checklist_guide()

    @mcp.resource("docs://release-notes")
    def docs_release_notes() -> str:
        """Human-readable release notes for the current published candidate."""

        report = build_release_metadata_report(active_defaults_registry())
        return release_notes_markdown(report)

    @mcp.resource("docs://conformance-report")
    def docs_conformance_report() -> str:
        """Human-readable conformance summary for the current release candidate."""

        defaults_registry = active_defaults_registry()
        metadata = build_release_metadata_report(defaults_registry)
        readiness = build_release_readiness_report(defaults_registry)
        security_review = build_security_provenance_review_report(defaults_registry)
        return conformance_report_markdown(metadata, readiness, security_review)

    @mcp.resource("docs://security-provenance-review")
    def docs_security_provenance_review() -> str:
        """Human-readable security and provenance review derived from the current surface."""

        report = build_security_provenance_review_report(active_defaults_registry())
        return security_provenance_review_markdown(report)

    @mcp.resource("docs://test-evidence-summary")
    def docs_test_evidence_summary() -> str:
        """Human-readable summary of public test and release-gate evidence."""

        return test_evidence_summary_guide()

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

        payload = build_validation_dossier_report(active_defaults_registry()).model_dump(
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

    @mcp.resource("verification://summary")
    def verification_summary_resource() -> str:
        """Machine-readable consolidated verification summary."""

        payload = build_verification_summary_report(active_defaults_registry()).model_dump(
            mode="json",
            by_alias=True,
        )
        return json.dumps(payload, indent=2)

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

    @mcp.resource("docs://verification-summary")
    def docs_verification_summary() -> str:
        """Human-readable guide to the consolidated verification summary surface."""

        return verification_summary_guide()

    @mcp.resource("release://readiness-report")
    def release_readiness_report() -> str:
        """Machine-readable release-readiness report."""

        payload = build_release_readiness_report(active_defaults_registry()).model_dump(
            mode="json",
            by_alias=True,
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://metadata-report")
    def release_metadata_report() -> str:
        """Machine-readable release metadata report."""

        payload = build_release_metadata_report(active_defaults_registry()).model_dump(
            mode="json",
            by_alias=True,
        )
        return json.dumps(payload, indent=2)

    @mcp.resource("release://security-provenance-review-report")
    def security_provenance_review_report() -> str:
        """Machine-readable security and provenance review report."""

        payload = build_security_provenance_review_report(active_defaults_registry()).model_dump(
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

    async def read_resource_with_protocol_errors(_self, uri) -> list[ReadResourceContents]:
        uri_str = str(uri)

        if uri_str.startswith("schemas://"):
            schema_name = uri_str.partition("://")[2]
            payload = schema_payloads()
            if schema_name not in payload:
                raise _resource_error(
                    code=INVALID_PARAMS,
                    message=f"Schema '{schema_name}' not found.",
                    uri=uri_str,
                    resource_type="schema",
                    resource_name=schema_name,
                )
            return [
                ReadResourceContents(
                    content=json.dumps(payload[schema_name], indent=2),
                    mime_type="text/plain",
                )
            ]

        if uri_str.startswith("examples://"):
            example_name = uri_str.partition("://")[2]
            payload = build_examples()
            if example_name not in payload:
                raise _resource_error(
                    code=INVALID_PARAMS,
                    message=f"Example '{example_name}' not found.",
                    uri=uri_str,
                    resource_type="example",
                    resource_name=example_name,
                )
            return [
                ReadResourceContents(
                    content=json.dumps(payload[example_name], indent=2),
                    mime_type="text/plain",
                )
            ]

        try:
            resource = await mcp._resource_manager.get_resource(uri, context=mcp.get_context())
        except ValueError as error:
            raise _resource_error(
                code=INVALID_PARAMS,
                message=str(error),
                uri=uri_str,
            ) from error

        if resource is None:  # pragma: no cover
            raise _resource_error(
                code=INVALID_PARAMS,
                message=f"Unknown resource: {uri_str}",
                uri=uri_str,
            )

        try:
            content = await resource.read()
        except McpError:
            raise
        except Exception as error:  # pragma: no cover
            raise _resource_error(
                code=INTERNAL_ERROR,
                message=f"Error reading resource '{uri_str}'.",
                uri=uri_str,
                exception_type=type(error).__name__,
            ) from error

        return [ReadResourceContents(content=content, mime_type=resource.mime_type)]

    mcp.read_resource = MethodType(read_resource_with_protocol_errors, mcp)  # type: ignore[method-assign]
    mcp._mcp_server.read_resource()(mcp.read_resource)


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

    @mcp.prompt(name="exposure_evidence_reconciliation_brief")
    def exposure_evidence_reconciliation_brief(
        primary_source: str,
        target_region: str = "EU",
    ) -> str:
        """Prompt template for reconciling reviewed evidence into one request."""

        return (
            f"Reconcile {primary_source} as the primary reviewed evidence source for a "
            f"{target_region} direct-use screening request. Compare every incoming source "
            "record, preserve field-level provenance, flag model-family mismatches, keep "
            "`manualReviewRequired`, `qualityFlags`, and `limitations` explicit, and do not "
            "add live external API calls."
        )

    @mcp.prompt(name="exposure_integrated_workflow_operator")
    def exposure_integrated_workflow_operator(
        route: str,
        outcome_goal: str = "PBPK handoff package",
    ) -> str:
        """Prompt template for running the integrated workflow safely."""

        return (
            f"Operate the integrated {route} workflow and produce a {outcome_goal}. "
            "Normalize only caller-supplied typed evidence records, review reconciliation fit, "
            "call out manual-review gates, keep solver and tier semantics visible, and make "
            "the final output auditable enough for downstream orchestration."
        )

    @mcp.prompt(name="exposure_inhalation_tier1_triage")
    def exposure_inhalation_tier1_triage(
        product_family: str,
        application_method: str = "trigger_spray",
    ) -> str:
        """Prompt template for deciding whether a spray case is Tier 1 ready."""

        return (
            f"Triage a Tier 1 inhalation scenario for {product_family} using {application_method}. "
            "Check whether the case should stay on heuristic screening, request explicit "
            "near-field inputs, or escalate to worker tooling; preserve benchmark-backed "
            "routing rationale; and keep auto-selection default-off unless the approved two-zone "
            "benchmark gate is explicitly met."
        )

    @mcp.prompt(name="exposure_worker_bridge_handoff")
    def exposure_worker_bridge_handoff(
        route: str,
        target_model_family: str = "external worker model",
    ) -> str:
        """Prompt template for packaging worker bridge handoffs."""

        return (
            f"Prepare a worker {route} bridge handoff for a {target_model_family}. "
            "List missing task-context fields, keep routing and compatibility reports attached, "
            "summarize the screening assumptions that downstream experts must review, and do not "
            "hide adapter quality flags or manual-review requirements."
        )

    @mcp.prompt(name="exposure_jurisdictional_review")
    def exposure_jurisdictional_review(
        jurisdiction_a: str,
        jurisdiction_b: str = "china",
    ) -> str:
        """Prompt template for comparing one scenario across jurisdictions."""

        return (
            f"Compare the same scenario across {jurisdiction_a} and {jurisdiction_b}. "
            "Identify which defaults and evidence records drive the dose delta, preserve the "
            "comparison as an audit trace rather than a final regulatory conclusion, and call "
            "out where a reviewer would need jurisdiction-specific evidence before refining "
            "the case."
        )
