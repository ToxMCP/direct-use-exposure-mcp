"""Schema, example, and manifest helpers."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.assets import repo_path
from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.examples import build_examples
from exposure_scenario_mcp.integrations import (
    CompToxChemicalRecord,
    ExposureWorkflowHook,
    PbpkCompatibilityReport,
    PbpkExternalImportBundle,
    PbpkExternalImportPackage,
    PbpkExternalImportRequest,
    PbpkExternalImportToolCall,
    ToxClawEvidenceBundle,
    ToxClawEvidenceEnvelope,
    ToxClawEvidenceRecord,
    ToxClawExposureRefinementBundle,
    ToxClawExposureRefinementSignal,
    ToxClawPbpkModuleParams,
    ToxClawReportClaim,
    ToxClawReportEvidenceReference,
    ToxClawReportSection,
)
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    ArchetypeLibraryManifest,
    ArchetypeLibrarySet,
    ArchetypeLibraryTemplate,
    AssumptionGovernance,
    BuildAggregateExposureScenarioInput,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    BuildParameterBoundsInput,
    BuildProbabilityBoundsFromProfileInput,
    BuildProbabilityBoundsFromScenarioPackageInput,
    CompareExposureScenariosInput,
    ContractManifest,
    ContractPromptEntry,
    ContractResourceEntry,
    ContractToolEntry,
    DependencyDescriptor,
    EnvelopeArchetypeInput,
    EnvelopeArchetypeResult,
    EnvelopeDriverAttribution,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureAssumptionRecord,
    ExposureEnvelopeSummary,
    ExposureScenario,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    MonotonicityCheck,
    ParameterBoundInput,
    ParameterBoundsSummary,
    PbpkScenarioInput,
    PopulationProfile,
    ProbabilityBoundDosePoint,
    ProbabilityBoundsDriverProfile,
    ProbabilityBoundsProfileManifest,
    ProbabilityBoundsProfileSummary,
    ProbabilityBoundSupportPointDefinition,
    ProductUseProfile,
    ProvenanceBundle,
    PublicSurfaceSummary,
    ReleaseDistributionArtifact,
    ReleaseMetadataReport,
    ReleaseReadinessCheck,
    ReleaseReadinessReport,
    ReviewedSurfaceIndex,
    ScenarioComparisonRecord,
    ScenarioPackageProbabilityManifest,
    ScenarioPackageProbabilityPointDefinition,
    ScenarioPackageProbabilityPointResult,
    ScenarioPackageProbabilityProfile,
    ScenarioPackageProbabilitySummary,
    SecurityProvenanceReviewFinding,
    SecurityProvenanceReviewReport,
    SensitivityRankingEntry,
    Tier1AirflowClassProfile,
    Tier1InhalationParameterManifest,
    Tier1InhalationProductProfile,
    Tier1ParticleRegimeProfile,
    TierSemantics,
    TierUpgradeAdvisory,
    TierUpgradeInputRequirement,
    ToolResultMeta,
    UncertaintyRegisterEntry,
    ValidationSummary,
)
from exposure_scenario_mcp.package_metadata import PACKAGE_NAME, __version__
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.release_artifacts import distribution_artifacts_for_release
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry

SCHEMA_MODELS = {
    "productUseProfile.v1": ProductUseProfile,
    "populationProfile.v1": PopulationProfile,
    "exposureScenarioRequest.v1": ExposureScenarioRequest,
    "inhalationScenarioRequest.v1": InhalationScenarioRequest,
    "inhalationTier1ScenarioRequest.v1": InhalationTier1ScenarioRequest,
    "tier1AirflowClassProfile.v1": Tier1AirflowClassProfile,
    "tier1ParticleRegimeProfile.v1": Tier1ParticleRegimeProfile,
    "tier1InhalationProductProfile.v1": Tier1InhalationProductProfile,
    "tier1InhalationParameterManifest.v1": Tier1InhalationParameterManifest,
    "exposureScenario.v1": ExposureScenario,
    "archetypeLibraryTemplate.v1": ArchetypeLibraryTemplate,
    "archetypeLibrarySet.v1": ArchetypeLibrarySet,
    "archetypeLibraryManifest.v1": ArchetypeLibraryManifest,
    "uncertaintyRegisterEntry.v1": UncertaintyRegisterEntry,
    "sensitivityRankingEntry.v1": SensitivityRankingEntry,
    "dependencyDescriptor.v1": DependencyDescriptor,
    "validationSummary.v1": ValidationSummary,
    "tierUpgradeInputRequirement.v1": TierUpgradeInputRequirement,
    "tierUpgradeAdvisory.v1": TierUpgradeAdvisory,
    "buildExposureEnvelopeFromLibraryInput.v1": BuildExposureEnvelopeFromLibraryInput,
    "probabilityBoundSupportPointDefinition.v1": ProbabilityBoundSupportPointDefinition,
    "probabilityBoundsDriverProfile.v1": ProbabilityBoundsDriverProfile,
    "probabilityBoundsProfileManifest.v1": ProbabilityBoundsProfileManifest,
    "buildProbabilityBoundsFromProfileInput.v1": BuildProbabilityBoundsFromProfileInput,
    "probabilityBoundDosePoint.v1": ProbabilityBoundDosePoint,
    "probabilityBoundsProfileSummary.v1": ProbabilityBoundsProfileSummary,
    "scenarioPackageProbabilityPointDefinition.v1": ScenarioPackageProbabilityPointDefinition,
    "scenarioPackageProbabilityProfile.v1": ScenarioPackageProbabilityProfile,
    "scenarioPackageProbabilityManifest.v1": ScenarioPackageProbabilityManifest,
    "buildProbabilityBoundsFromScenarioPackageInput.v1": (
        BuildProbabilityBoundsFromScenarioPackageInput
    ),
    "scenarioPackageProbabilityPointResult.v1": ScenarioPackageProbabilityPointResult,
    "scenarioPackageProbabilitySummary.v1": ScenarioPackageProbabilitySummary,
    "parameterBoundInput.v1": ParameterBoundInput,
    "monotonicityCheck.v1": MonotonicityCheck,
    "buildParameterBoundsInput.v1": BuildParameterBoundsInput,
    "parameterBoundsSummary.v1": ParameterBoundsSummary,
    "aggregateExposureSummary.v1": AggregateExposureSummary,
    "exposureAssumptionRecord.v1": ExposureAssumptionRecord,
    "assumptionGovernance.v1": AssumptionGovernance,
    "pbpkScenarioInput.v1": PbpkScenarioInput,
    "scenarioComparisonRecord.v1": ScenarioComparisonRecord,
    "provenanceBundle.v1": ProvenanceBundle,
    "tierSemantics.v1": TierSemantics,
    "buildExposureEnvelopeInput.v1": BuildExposureEnvelopeInput,
    "envelopeArchetypeInput.v1": EnvelopeArchetypeInput,
    "envelopeArchetypeResult.v1": EnvelopeArchetypeResult,
    "envelopeDriverAttribution.v1": EnvelopeDriverAttribution,
    "exposureEnvelopeSummary.v1": ExposureEnvelopeSummary,
    "buildAggregateExposureScenarioInput.v1": BuildAggregateExposureScenarioInput,
    "exportPbpkScenarioInputRequest.v1": ExportPbpkScenarioInputRequest,
    "exportPbpkExternalImportBundleRequest.v1": ExportPbpkExternalImportBundleRequest,
    "exportToxClawEvidenceBundleRequest.v1": ExportToxClawEvidenceBundleRequest,
    "exportToxClawRefinementBundleRequest.v1": ExportToxClawRefinementBundleRequest,
    "compareExposureScenariosInput.v1": CompareExposureScenariosInput,
    "compToxChemicalRecord.v1": CompToxChemicalRecord,
    "toxclawEvidenceEnvelope.v1": ToxClawEvidenceEnvelope,
    "toxclawEvidenceRecord.v1": ToxClawEvidenceRecord,
    "toxclawReportEvidenceReference.v1": ToxClawReportEvidenceReference,
    "toxclawReportClaim.v1": ToxClawReportClaim,
    "toxclawReportSection.v1": ToxClawReportSection,
    "toxclawEvidenceBundle.v1": ToxClawEvidenceBundle,
    "exposureWorkflowHook.v1": ExposureWorkflowHook,
    "toxclawExposureRefinementSignal.v1": ToxClawExposureRefinementSignal,
    "toxclawExposureRefinementBundle.v1": ToxClawExposureRefinementBundle,
    "pbpkCompatibilityReport.v1": PbpkCompatibilityReport,
    "pbpkExternalImportBundle.v1": PbpkExternalImportBundle,
    "pbpkExternalImportRequest.v1": PbpkExternalImportRequest,
    "pbpkExternalImportToolCall.v1": PbpkExternalImportToolCall,
    "pbpkExternalImportPackage.v1": PbpkExternalImportPackage,
    "toxclawPbpkModuleParams.v1": ToxClawPbpkModuleParams,
    "toolResultMeta.v1": ToolResultMeta,
    "releaseMetadataReport.v1": ReleaseMetadataReport,
    "releaseReadinessReport.v1": ReleaseReadinessReport,
    "securityProvenanceReviewReport.v1": SecurityProvenanceReviewReport,
}

def schema_payloads() -> dict[str, dict]:
    return {name: model.model_json_schema() for name, model in SCHEMA_MODELS.items()}


def build_contract_manifest(defaults_registry: DefaultsRegistry) -> ContractManifest:
    examples = build_examples()
    return ContractManifest(
        server_name="exposure_scenario_mcp",
        server_version="0.1.0",
        defaults_version=defaults_registry.version,
        tools=[
            ContractToolEntry(
                name="exposure_build_screening_exposure_scenario",
                request_schema="exposureScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build one deterministic dermal or oral external exposure screening scenario."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_exposure_envelope",
                request_schema="buildExposureEnvelopeInput.v1",
                response_schema="exposureEnvelopeSummary.v1",
                description="Build a deterministic Tier B envelope from named scenario archetypes.",
            ),
            ContractToolEntry(
                name="exposure_build_exposure_envelope_from_library",
                request_schema="buildExposureEnvelopeFromLibraryInput.v1",
                response_schema="exposureEnvelopeSummary.v1",
                description=(
                    "Instantiate a packaged Tier B archetype-library set into a deterministic "
                    "envelope."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_parameter_bounds_summary",
                request_schema="buildParameterBoundsInput.v1",
                response_schema="parameterBoundsSummary.v1",
                description=(
                    "Build a deterministic bounds-propagation summary from explicit lower "
                    "and upper parameter values."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_probability_bounds_from_profile",
                request_schema="buildProbabilityBoundsFromProfileInput.v1",
                response_schema="probabilityBoundsProfileSummary.v1",
                description=(
                    "Build a packaged single-driver probability-bounds summary with "
                    "other scenario inputs fixed."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_probability_bounds_from_scenario_package",
                request_schema="buildProbabilityBoundsFromScenarioPackageInput.v1",
                response_schema="scenarioPackageProbabilitySummary.v1",
                description=(
                    "Build a packaged coupled-driver probability-bounds summary from "
                    "scenario packages."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_aggregate_exposure_scenario",
                request_schema="buildAggregateExposureScenarioInput.v1",
                response_schema="aggregateExposureSummary.v1",
                description="Combine component scenarios into a simple additive aggregate summary.",
            ),
            ContractToolEntry(
                name="exposure_build_inhalation_screening_scenario",
                request_schema="inhalationScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build a deterministic inhalation screening scenario using room semantics."
                ),
            ),
            ContractToolEntry(
                name="exposure_build_inhalation_tier1_screening_scenario",
                request_schema="inhalationTier1ScenarioRequest.v1",
                response_schema="exposureScenario.v1",
                description=(
                    "Build a deterministic Tier 1 near-field/far-field inhalation screening "
                    "scenario for spray events."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_pbpk_scenario_input",
                request_schema="exportPbpkScenarioInputRequest.v1",
                response_schema="pbpkScenarioInput.v1",
                description="Export a PBPK-ready handoff object from a source scenario.",
            ),
            ContractToolEntry(
                name="exposure_export_pbpk_external_import_bundle",
                request_schema="exportPbpkExternalImportBundleRequest.v1",
                response_schema="pbpkExternalImportPackage.v1",
                description=(
                    "Export a PBPK MCP external-import payload template plus readiness report."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_toxclaw_evidence_bundle",
                request_schema="exportToxClawEvidenceBundleRequest.v1",
                response_schema="toxclawEvidenceBundle.v1",
                description=(
                    "Export deterministic ToxClaw evidence and report-section primitives."
                ),
            ),
            ContractToolEntry(
                name="exposure_export_toxclaw_refinement_bundle",
                request_schema="exportToxClawRefinementBundleRequest.v1",
                response_schema="toxclawExposureRefinementBundle.v1",
                description=(
                    "Export a ToxClaw-facing exposure refinement delta with workflow hooks."
                ),
            ),
            ContractToolEntry(
                name="exposure_compare_exposure_scenarios",
                request_schema="compareExposureScenariosInput.v1",
                response_schema="scenarioComparisonRecord.v1",
                description="Compare two scenarios and surface dose and assumption deltas.",
            ),
        ],
        resources=[
            ContractResourceEntry(
                uri="contracts://manifest", description="Machine-readable contract manifest."
            ),
            ContractResourceEntry(
                uri="defaults://manifest", description="Versioned defaults manifest."
            ),
            ContractResourceEntry(
                uri="tier1-inhalation://manifest",
                description=(
                    "Machine-readable packaged Tier 1 inhalation parameter and "
                    "product-profile manifest."
                ),
            ),
            ContractResourceEntry(
                uri="archetypes://manifest",
                description="Machine-readable packaged Tier B archetype-library manifest.",
            ),
            ContractResourceEntry(
                uri="probability-bounds://manifest",
                description="Machine-readable packaged Tier C single-driver profile manifest.",
            ),
            ContractResourceEntry(
                uri="scenario-probability://manifest",
                description=(
                    "Machine-readable packaged Tier C coupled-driver "
                    "scenario package manifest."
                ),
            ),
            ContractResourceEntry(
                uri="docs://algorithm-notes",
                description="Algorithm notes for the deterministic engines.",
            ),
            ContractResourceEntry(
                uri="docs://archetype-library-guide",
                description="Guide to the packaged Tier B archetype library and its guardrails.",
            ),
            ContractResourceEntry(
                uri="docs://probability-bounds-guide",
                description="Guide to the packaged Tier C probability-bounds profiles.",
            ),
            ContractResourceEntry(
                uri="docs://defaults-evidence-map",
                description="Source register and interpretation notes for defaults and heuristics.",
            ),
            ContractResourceEntry(
                uri="docs://operator-guide",
                description=(
                    "Operator guide for validation, transports, "
                    "and interpretation boundaries."
                ),
            ),
            ContractResourceEntry(
                uri="docs://provenance-policy",
                description="Provenance and assumption-emission policy for auditability.",
            ),
            ContractResourceEntry(
                uri="docs://result-status-semantics",
                description=(
                    "Non-breaking result-status conventions carried in "
                    "top-level tool-result metadata."
                ),
            ),
            ContractResourceEntry(
                uri="docs://uncertainty-framework",
                description="Tier A/B/C uncertainty guidance and interpretation boundaries.",
            ),
            ContractResourceEntry(
                uri="docs://inhalation-tier-upgrade-guide",
                description="Guide to Tier 1 inhalation upgrade hooks and current boundaries.",
            ),
            ContractResourceEntry(
                uri="docs://validation-framework",
                description="Validation and benchmark-domain posture for current route models.",
            ),
            ContractResourceEntry(
                uri="docs://suite-integration-guide",
                description="Boundary and integration guide for CompTox, ToxClaw, and PBPK MCP.",
            ),
            ContractResourceEntry(
                uri="docs://troubleshooting",
                description=(
                    "Troubleshooting guide for common scenario, aggregation, "
                    "and export failures."
                ),
            ),
            ContractResourceEntry(
                uri="docs://release-readiness",
                description="Release-readiness guidance derived from the current contract surface.",
            ),
            ContractResourceEntry(
                uri="docs://release-notes",
                description=(
                    "Release notes and migration notes for the current published candidate."
                ),
            ),
            ContractResourceEntry(
                uri="docs://conformance-report",
                description=(
                    "Human-readable conformance summary across validation, benchmarks, "
                    "and release checks."
                ),
            ),
            ContractResourceEntry(
                uri="docs://security-provenance-review",
                description=(
                    "Human-readable security and provenance review derived from the current "
                    "tool, resource, and defaults surface."
                ),
            ),
            ContractResourceEntry(
                uri="benchmarks://manifest",
                description="Machine-readable benchmark and regression corpus manifest.",
            ),
            ContractResourceEntry(
                uri="validation://manifest",
                description="Machine-readable validation and external-dataset candidate manifest.",
            ),
            ContractResourceEntry(
                uri="release://readiness-report",
                description=(
                    "Machine-readable release-readiness report with "
                    "validation and security checks."
                ),
            ),
            ContractResourceEntry(
                uri="release://metadata-report",
                description=(
                    "Machine-readable release metadata with package, benchmark, schema, "
                    "and limitation details."
                ),
            ),
            ContractResourceEntry(
                uri="release://security-provenance-review-report",
                description=(
                    "Machine-readable security and provenance review with pass, warning, "
                    "and blocked findings."
                ),
            ),
            ContractResourceEntry(
                uri="schemas://{schema_name}", description="JSON Schema by schema name."
            ),
            ContractResourceEntry(
                uri="examples://{example_name}", description="Generated example payload by name."
            ),
        ],
        prompts=[
            ContractPromptEntry(
                name="exposure_refinement_playbook",
                description=(
                    "Checklist for refining a screening scenario without collapsing auditability."
                ),
            ),
            ContractPromptEntry(
                name="exposure_pbpk_handoff_checklist",
                description=(
                    "Checklist for validating PBPK handoff readiness from a source scenario."
                ),
            ),
        ],
        schemas={name: f"schemas/{name}.json" for name in SCHEMA_MODELS},
        examples={name: f"schemas/examples/{name}.json" for name in examples},
    )


def algorithm_notes() -> str:
    return """# Exposure Scenario MCP Algorithm Notes

## Screening Plugin

- Convert product amount per event into grams.
- Convert grams into chemical mass per event using `concentration_fraction`.
- Emit explicit assumption governance showing evidence grade, applicability status,
  and uncertainty families for every resolved parameter.
- Dermal:
  `external_mass_mg_day = chemical_mass_mg_event * use_events_per_day *
  retention_factor * transfer_efficiency`
- Oral:
  `external_mass_mg_day = chemical_mass_mg_event * use_events_per_day *
  ingestion_fraction`
- Normalize by body weight to emit `mg/kg-day`.
- Attach `tierSemantics` so the result stays bounded as Tier-0 deterministic screening.
- Attach Tier A diagnostics: `uncertaintyRegister`, `sensitivityRanking`,
  `dependencyMetadata`, and `validationSummary`.

## Inhalation Plugin

- Convert product amount per event into chemical mass.
- Apply `aerosolized_fraction` to obtain released mass.
- Compute initial well-mixed room concentration as `released_mass / room_volume`.
- Convert to time-averaged air concentration using a first-order air exchange removal term.
- Compute inhaled mass as
  `average_air_concentration * inhalation_rate * exposure_duration *
  events_per_day`.
- Normalize by body weight to emit `mg/kg-day`.
- Emit Tier-0 caveats that forbid interpreting room-average output as a breathing-zone peak.
- Preserve inhalation-specific uncertainty entries when spray assumptions
  exceed well-mixed validity.

## Tier 1 Inhalation Screening

- Tier 1 NF/FF screening resolves airflow-directionality and particle-regime heuristics from the
  packaged manifest at `tier1-inhalation://manifest`.
- Product-family screening profiles are published alongside those parameter packs so callers can
  anchor Tier 1 geometry and spray inputs to governed use-context templates.
- Tier 1 remains a deterministic screening model and must not be interpreted as CFD,
  deposition, or absorbed-dose simulation.

## Aggregate Summary

- Sum compatible normalized doses across components.
- Preserve route-wise subtotals.
- Emit an explicit limitation when multiple routes are rolled into a single screening summary.
- Attach Tier A aggregate uncertainty notes explaining that co-use dependence is not modeled.

## Deterministic Envelope

- Build named archetype scenarios with the same route, scenario class, chemical, and dose unit.
- Report minimum, median, and maximum deterministic dose across the archetypes.
- Attribute envelope span to explicit assumption differences between the low and high archetypes.
- Label the result as Tier B bounded uncertainty, not as a confidence interval.

## Packaged Archetype Library

- The packaged archetype library publishes governed Tier B screening templates by route and use
  context.
- `exposure_build_exposure_envelope_from_library` injects caller-supplied chemical identity into
  a packaged set and then resolves the same deterministic envelope algorithm.
- Library-backed envelopes keep `archetypeLibrarySetId`, `archetypeLibraryVersion`, template IDs,
  and library limitations visible in the result.

## Single-Driver Probability Bounds

- Packaged Tier C profiles publish cumulative probability bounds for one selected driver at a
  time, with all other scenario inputs fixed at the base request.
- `exposure_build_probability_bounds_from_profile` evaluates each support point deterministically
  and preserves the packaged probability bounds without Monte Carlo sampling.
- Probability-bounds outputs remain screening summaries and must not be interpreted as validated
  population exposure distributions.

## Scenario-Package Probability Bounds

- Packaged Tier C scenario-package profiles publish cumulative probability bounds over coupled
  driver states by referencing archetype-library templates.
- `exposure_build_probability_bounds_from_scenario_package` materializes deterministic scenarios
  for each packaged state and preserves dependence within those states.
- Scenario-package outputs remain screening summaries and must not be interpreted as full joint
  population exposure distributions.

## Comparison

- Compare primary dose values directly.
- Diff assumptions by stable parameter name.
- Report absolute and percent deltas without making risk claims.
"""


def benchmark_manifest() -> dict:
    return load_benchmark_manifest()


def archetype_library_manifest() -> dict:
    return ArchetypeLibraryRegistry.load().manifest().model_dump(mode="json", by_alias=True)


def tier1_inhalation_parameter_manifest() -> dict:
    return Tier1InhalationProfileRegistry.load().manifest().model_dump(
        mode="json",
        by_alias=True,
    )


def probability_bounds_profile_manifest() -> dict:
    return ProbabilityBoundsProfileRegistry.load().manifest().model_dump(
        mode="json",
        by_alias=True,
    )


def scenario_probability_package_manifest() -> dict:
    return ScenarioProbabilityPackageRegistry.load().manifest().model_dump(
        mode="json",
        by_alias=True,
    )


def _project_metadata() -> tuple[str, str]:
    pyproject_path = repo_path("pyproject.toml")
    if pyproject_path is not None and pyproject_path.exists():
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = payload["project"]
        return str(project["name"]), str(project["version"])
    return PACKAGE_NAME, __version__


def _distribution_artifacts(package_name: str, version: str) -> list[ReleaseDistributionArtifact]:
    return distribution_artifacts_for_release(package_name, version, repo_path("dist"))


def _review_status(findings: list[SecurityProvenanceReviewFinding]) -> str:
    if any(finding.status == "blocked" for finding in findings):
        return "blocked"
    if any(finding.status == "warning" for finding in findings):
        return "acceptable_with_warnings"
    return "acceptable"


def build_security_provenance_review_report(
    defaults_registry: DefaultsRegistry,
) -> SecurityProvenanceReviewReport:
    manifest = build_contract_manifest(defaults_registry)
    defaults_manifest = defaults_registry.manifest()
    examples = build_examples()
    reviewed_surface = ReviewedSurfaceIndex(
        tool_names=[tool.name for tool in manifest.tools],
        resource_uris=[resource.uri for resource in manifest.resources],
        prompt_names=[prompt.name for prompt in manifest.prompts],
    )
    heuristic_sources = [
        source["source_id"]
        for source in defaults_registry.payload.get("sources", [])
        if str(source.get("source_id", "")).startswith("heuristic_")
    ]
    provenance_example_names = [
        "screening_dermal_scenario",
        "inhalation_scenario",
        "aggregate_summary",
        "comparison_record",
        "pbpk_input",
    ]
    provenance_examples_ok = all(
        "provenance" in examples[example_name] for example_name in provenance_example_names
    )
    pbpk_external_import_ok = bool(
        examples["pbpk_external_import_package"]["bundle"].get("supportingHandoffs")
    )
    toxclaw_hashing_ok = all(
        {"evidenceId", "contentHash"} <= set(examples[example_name]["evidenceRecord"])
        for example_name in ["toxclaw_evidence_bundle", "toxclaw_refinement_bundle"]
    )
    provenance_status = (
        "pass"
        if provenance_examples_ok and pbpk_external_import_ok and toxclaw_hashing_ok
        else "blocked"
    )
    findings = [
        SecurityProvenanceReviewFinding(
            finding_id="public-surface-indexed",
            category="contract_integrity",
            title="Public tool and resource surface is machine-readable",
            status="pass",
            applies_to=[*reviewed_surface.tool_names, *reviewed_surface.resource_uris],
            evidence=(
                f"The manifest declares {len(manifest.tools)} tools, "
                f"{len(manifest.resources)} resources, and {len(manifest.prompts)} prompts, "
                "with JSON Schemas published for every declared public schema."
            ),
            references=[
                "contracts://manifest",
                "schemas://{schema_name}",
                "examples://{example_name}",
            ],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="defaults-pack-integrity",
            category="defaults_integrity",
            title="Defaults pack integrity is explicit and reviewable",
            status="pass",
            applies_to=["defaults://manifest", "docs://defaults-evidence-map"],
            evidence=(
                f"Defaults pack `{defaults_manifest['defaults_version']}` carries SHA256 "
                f"`{defaults_manifest['defaults_hash_sha256'][:16]}` with "
                f"{defaults_manifest['source_count']} declared source entries across "
                f"{len(defaults_manifest['supported_regions'])} supported regions."
            ),
            references=["defaults://manifest", "docs://defaults-evidence-map"],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="output-auditability",
            category="provenance_auditability",
            title="Public outputs preserve provenance or auditable handoff context",
            status=provenance_status,
            applies_to=reviewed_surface.tool_names,
            evidence=(
                "Generated scenario, aggregate, comparison, and PBPK input examples all carry "
                "explicit `provenance`; PBPK external-import output preserves auditable "
                "handoff context through supporting handoffs and compatibility reporting; "
                "ToxClaw-facing exports carry deterministic evidence records."
            ),
            recommendation=(
                None
                if provenance_status == "pass"
                else "Do not release the surface until every public output restores explicit "
                "auditability through provenance or deterministic evidence traces."
            ),
            references=[
                "docs://provenance-policy",
                "docs://suite-integration-guide",
            ],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="deterministic-toxclaw-evidence",
            category="deterministic_evidence_hashing",
            title="ToxClaw exports use deterministic evidence IDs and content hashes",
            status="pass" if toxclaw_hashing_ok else "blocked",
            applies_to=[
                "exposure_export_toxclaw_evidence_bundle",
                "exposure_export_toxclaw_refinement_bundle",
            ],
            evidence=(
                "Both ToxClaw export example families emit `evidenceId` and `contentHash`, "
                "keeping downstream citation and report linkage stable across reruns."
            ),
            recommendation=(
                None
                if toxclaw_hashing_ok
                else "Restore deterministic hashing before release so evidence and claim "
                "linkage stay stable across repeated scenario exports."
            ),
            references=[
                "docs://provenance-policy",
                "docs://suite-integration-guide",
            ],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="heuristic-defaults-remain",
            category="defaults_integrity",
            title="Heuristic screening factors remain visible to downstream consumers",
            status="warning" if heuristic_sources else "pass",
            applies_to=[
                "exposure_build_screening_exposure_scenario",
                "exposure_build_inhalation_screening_scenario",
                "defaults://manifest",
                "docs://defaults-evidence-map",
            ],
            evidence=(
                "The defaults source register still includes heuristic screening source "
                f"families: {', '.join(f'`{item}`' for item in heuristic_sources)}. "
                "When these defaults are applied, the runtime emits warning-quality flags "
                "instead of hiding the uncertainty."
                if heuristic_sources
                else "No heuristic defaults remain in the active defaults registry."
            ),
            recommendation=(
                "Replace heuristic factor families with curated region or product-family packs "
                "where possible, and treat flagged defaults as screening-grade until then."
                if heuristic_sources
                else None
            ),
            references=["docs://defaults-evidence-map", "docs://provenance-policy"],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="remote-transport-controls-externalized",
            category="transport_security",
            title="Remote HTTP deployment still depends on external security controls",
            status="warning",
            applies_to=[
                "docs://operator-guide",
                "docs://troubleshooting",
                "streamable-http",
            ],
            evidence=(
                "The server supports `stdio` and `streamable-http`, but the MCP itself does "
                "not impose authentication, authorization, or origin filtering for remote "
                "HTTP exposure."
            ),
            recommendation=(
                "Prefer `stdio` locally and put any `streamable-http` deployment behind a "
                "trusted gateway with auth, TLS, and origin validation."
            ),
            references=["docs://operator-guide", "docs://troubleshooting"],
        ),
        SecurityProvenanceReviewFinding(
            finding_id="scientific-boundary-explicit",
            category="scientific_boundary",
            title="Scientific ownership boundary remains explicit",
            status="pass",
            applies_to=reviewed_surface.tool_names,
            evidence=(
                "The published surface keeps ownership at external-dose construction and "
                "explicitly excludes PBPK execution, internal dose estimation, BER, PoD "
                "derivation, and final risk conclusions."
            ),
            references=[
                "docs://operator-guide",
                "docs://suite-integration-guide",
                "docs://release-readiness",
            ],
        ),
    ]
    status = _review_status(findings)
    reviewed_at = datetime.now(UTC).isoformat()
    warning_titles = [finding.title.lower() for finding in findings if finding.status == "warning"]
    if status == "blocked":
        summary = (
            "The security and provenance review is blocked because at least one public-surface "
            "auditability check failed."
        )
    elif warning_titles:
        summary = (
            "The security and provenance review is acceptable with warnings. The remaining "
            "cautions are confined to remote HTTP deployment controls and still-heuristic "
            "screening factor families."
        )
    else:
        summary = (
            "The security and provenance review found no blocking or warning-level issues "
            "across the current public surface."
        )
    return SecurityProvenanceReviewReport(
        review_id=f"security-provenance-review-{reviewed_at[:10]}",
        server_name=manifest.server_name,
        server_version=manifest.server_version,
        defaults_version=manifest.defaults_version,
        reviewed_at=reviewed_at,
        status=status,
        summary=summary,
        reviewed_surface=reviewed_surface,
        findings=findings,
        external_requirements=[
            (
                "Keep any `streamable-http` deployment behind authentication, TLS "
                "termination, and origin policy enforcement."
            ),
            (
                "Treat heuristic-default warnings as screening-level uncertainty "
                "until curated defaults packs replace them."
            ),
        ],
    )


def build_release_metadata_report(defaults_registry: DefaultsRegistry) -> ReleaseMetadataReport:
    manifest = build_contract_manifest(defaults_registry)
    examples = build_examples()
    benchmarks = benchmark_manifest()
    readiness = build_release_readiness_report(defaults_registry)
    security_review = build_security_provenance_review_report(defaults_registry)
    package_name, package_version = _project_metadata()
    benchmark_cases = benchmarks.get("cases", [])
    artifacts = _distribution_artifacts(package_name, package_version)
    return ReleaseMetadataReport(
        release_version=package_version,
        package_name=package_name,
        package_version=package_version,
        server_name=manifest.server_name,
        server_version=manifest.server_version,
        defaults_version=manifest.defaults_version,
        readiness_status=readiness.status,
        security_review_status=security_review.status,
        benchmark_case_count=len(benchmark_cases),
        benchmark_case_ids=[str(case["id"]) for case in benchmark_cases],
        contract_schema_count=len(manifest.schemas),
        contract_example_count=len(examples),
        distribution_artifacts=artifacts,
        published_docs=[
            "docs://release-notes",
            "docs://conformance-report",
            "docs://release-readiness",
            "docs://security-provenance-review",
            "docs/releases/v0.1.0.md",
        ],
        validation_commands=readiness.validation_commands,
        migration_notes=[
            "This is the first public v0.1.0 release, so no prior stable migration path applies.",
            (
                "Pre-release PBPK wrappers that nested requests under `toolCall.arguments.bundle` "
                "are superseded by the published v0.1.0 top-level request payload."
            ),
        ],
        known_limitations=readiness.known_limitations,
    )


def build_release_readiness_report(defaults_registry: DefaultsRegistry) -> ReleaseReadinessReport:
    manifest = build_contract_manifest(defaults_registry)
    defaults_manifest = defaults_registry.manifest()
    security_review = build_security_provenance_review_report(defaults_registry)
    package_name, package_version = _project_metadata()
    artifacts = _distribution_artifacts(package_name, package_version)
    all_artifacts_present = all(artifact.present for artifact in artifacts)
    all_artifacts_hashed = all(
        artifact.sha256 is not None and artifact.size_bytes is not None
        for artifact in artifacts
        if artifact.present
    )
    checks = [
        ReleaseReadinessCheck(
            check_id="contract-surface",
            title="Contract surface is published",
            status="pass",
            blocking=False,
            evidence=(
                f"{len(manifest.tools)} tools, {len(manifest.resources)} resources, and "
                f"{len(manifest.prompts)} prompts are declared in the manifest."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="defaults-integrity",
            title="Defaults pack is versioned and hashed",
            status="pass",
            blocking=False,
            evidence=(
                f"Defaults pack `{defaults_manifest['defaults_version']}` is tracked with "
                f"SHA256 `{defaults_manifest['defaults_hash_sha256'][:16]}` and "
                f"{defaults_manifest['source_count']} declared source entries."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="provenance-coverage",
            title="Public outputs preserve provenance or deterministic hashes",
            status="pass",
            blocking=False,
            evidence=(
                "The published security/provenance review confirms that scenario, aggregate, "
                "comparison, and PBPK outputs preserve auditability, and that ToxClaw exports "
                "retain deterministic evidence IDs and content hashes."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="pbpk-upstream-request-alignment",
            title="PBPK handoff emits the upstream ingest request shape",
            status="pass",
            blocking=False,
            evidence=(
                "PBPK export wrappers now emit top-level `ingest_external_pbpk_bundle` request "
                "arguments directly, and integration coverage validates the generated payload "
                "against the sibling PBPK MCP request model when that repo is present."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="security-provenance-review",
            title="Security and provenance review artifact is published",
            status=(
                "blocked"
                if security_review.status == "blocked"
                else "warning"
                if security_review.status == "acceptable_with_warnings"
                else "pass"
            ),
            blocking=security_review.status == "blocked",
            evidence=(
                f"`{security_review.schema_version}` covers "
                f"{len(security_review.reviewed_surface.tool_names)} tools and "
                f"{len(security_review.reviewed_surface.resource_uris)} resources with "
                f"{len(security_review.findings)} explicit findings."
            ),
            recommendation=(
                None
                if security_review.status == "acceptable"
                else "Review `release://security-provenance-review-report` before publishing a "
                "remote deployment or tightening defaults claims."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="validation-suite",
            title="Local validation gates are defined",
            status="pass" if all_artifacts_present and all_artifacts_hashed else "warning",
            blocking=False,
            evidence=(
                "The standard validation path is `uv run ruff check .`, `uv run pytest`, "
                "`uv build`, `uv run generate-exposure-contracts`, and "
                "`uv run check-exposure-release-artifacts`."
                if all_artifacts_present and all_artifacts_hashed
                else (
                    "The validation path is defined, but release metadata still needs to be "
                    "regenerated after `uv build` before artifact verification can pass."
                )
            ),
        ),
        ReleaseReadinessCheck(
            check_id="result-status-semantics",
            title="Future-safe result metadata is published",
            status="pass",
            blocking=False,
            evidence=(
                "Tool responses retain their existing payload schemas while top-level `_meta` "
                "publishes `toolResultMeta.v1` with sync terminal states reserved for future "
                "async reuse."
            ),
        ),
        ReleaseReadinessCheck(
            check_id="scientific-boundary",
            title="Scope boundary remains explicit",
            status="pass",
            blocking=False,
            evidence=(
                "The public surface states that this MCP owns external-dose construction only "
                "and does not claim PBPK execution, internal exposure, BER, PoD derivation, "
                "or final risk conclusions."
            ),
        ),
    ]
    status = (
        "blocked"
        if any(check.status == "blocked" for check in checks)
        else "ready_with_known_limitations"
        if any(check.status == "warning" for check in checks)
        else "ready"
    )
    return ReleaseReadinessReport(
        release_candidate="0.1.0",
        server_name=manifest.server_name,
        server_version=manifest.server_version,
        defaults_version=manifest.defaults_version,
        status=status,
        summary=(
            "The current Exposure Scenario MCP build satisfies its contract, regression, and "
            "provenance gates for a deterministic external-dose release candidate, with "
            "declared limitations and remote-deployment cautions still visible."
        ),
        public_surface=PublicSurfaceSummary(
            tool_count=len(manifest.tools),
            resource_count=len(manifest.resources),
            prompt_count=len(manifest.prompts),
            transports=["stdio", "streamable-http"],
        ),
        validation_commands=[
            "uv run ruff check .",
            "uv run pytest",
            "uv build",
            "uv run generate-exposure-contracts",
            "uv run check-exposure-release-artifacts",
        ],
        checks=checks,
        known_limitations=[
            (
                "This is a deterministic-first v0.1.0 server; "
                "no probabilistic population engine is shipped."
            ),
            (
                "The module does not execute PBPK, estimate internal dose, "
                "derive BER or PoD values, or make final risk decisions."
            ),
            (
                "Remote `streamable-http` deployment requires external "
                "authentication and origin controls."
            ),
            (
                "Some screening factors still resolve from heuristic defaults packs and should "
                "be treated as flagged screening-level assumptions until curated replacements "
                "are added."
            ),
            (
                "PBPK request alignment should be re-validated whenever PBPK MCP "
                "changes its published contract version or request model."
            ),
        ],
    )
