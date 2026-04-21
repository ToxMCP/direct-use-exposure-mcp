from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
    build_verification_summary_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.package_metadata import (
    CURRENT_RELEASE_METADATA_RELATIVE_PATH,
    CURRENT_VERSION,
)
from exposure_scenario_mcp.server import create_mcp_server
from exposure_scenario_mcp.validation import (
    build_validation_coverage_report,
    build_validation_dossier_report,
)
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.validation_time_series import ValidationTimeSeriesReferenceRegistry
from scripts.generate_contract_assets import main as generate_contract_assets

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMA_DIR / "examples"
MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"
RELEASE_METADATA_PATH = REPO_ROOT / CURRENT_RELEASE_METADATA_RELATIVE_PATH


EXAMPLE_SCHEMA_MAP = {
    "chemical_identity": "chemicalIdentity.v1",
    "exposure_scenario_definition": "exposureScenarioDefinition.v1",
    "route_dose_estimate": "routeDoseEstimate.v1",
    "environmental_release_scenario": "environmentalReleaseScenario.v1",
    "concentration_surface": "concentrationSurface.v1",
    "screening_dermal_request": "exposureScenarioRequest.v1",
    "screening_dermal_scenario": "exposureScenario.v1",
    "inhalation_request": "inhalationScenarioRequest.v1",
    "inhalation_scenario": "exposureScenario.v1",
    "inhalation_tier1_request": "inhalationTier1ScenarioRequest.v1",
    "inhalation_tier1_scenario": "exposureScenario.v1",
    "exposure_envelope_summary": "exposureEnvelopeSummary.v1",
    "exposure_envelope_from_library_request": "buildExposureEnvelopeFromLibraryInput.v1",
    "exposure_envelope_from_library_summary": "exposureEnvelopeSummary.v1",
    "inhalation_tier1_envelope_from_library_request": "buildExposureEnvelopeFromLibraryInput.v1",
    "inhalation_tier1_envelope_from_library_summary": "exposureEnvelopeSummary.v1",
    "parameter_bounds_summary": "parameterBoundsSummary.v1",
    "probability_bounds_from_profile_request": "buildProbabilityBoundsFromProfileInput.v1",
    "probability_bounds_profile_summary": "probabilityBoundsProfileSummary.v1",
    "scenario_package_probability_request": "buildProbabilityBoundsFromScenarioPackageInput.v1",
    "scenario_package_probability_summary": "scenarioPackageProbabilitySummary.v1",
    "inhalation_tier1_scenario_package_probability_request": (
        "buildProbabilityBoundsFromScenarioPackageInput.v1"
    ),
    "inhalation_tier1_scenario_package_probability_summary": (
        "scenarioPackageProbabilitySummary.v1"
    ),
    "aggregate_summary": "aggregateExposureSummary.v1",
    "aggregate_internal_equivalent_summary": "aggregateExposureSummary.v1",
    "pbpk_input": "pbpkScenarioInput.v1",
    "pbpk_input_transient": "pbpkScenarioInput.v1",
    "pbpk_external_import_request": "pbpkExternalImportRequest.v1",
    "pbpk_external_import_tool_call": "pbpkExternalImportToolCall.v1",
    "toxclaw_pbpk_module_params": "toxclawPbpkModuleParams.v1",
    "pbpk_external_import_package": "pbpkExternalImportPackage.v1",
    "comparison_record": "scenarioComparisonRecord.v1",
    "compare_jurisdictional_scenarios_request": "compareJurisdictionalScenariosInput.v1",
    "jurisdictional_comparison_result": "jurisdictionalComparisonResult.v1",
    "comp_tox_record": "compToxChemicalRecord.v1",
    "comp_tox_enriched_request": "exposureScenarioRequest.v1",
    "cons_expo_evidence_record": "consExpoEvidenceRecord.v1",
    "cons_expo_product_use_evidence": "productUseEvidenceRecord.v1",
    "sccs_evidence_record": "sccsCosmeticsEvidenceRecord.v1",
    "sccs_product_use_evidence": "productUseEvidenceRecord.v1",
    "sccs_opinion_evidence_record": "sccsOpinionEvidenceRecord.v1",
    "sccs_opinion_product_use_evidence": "productUseEvidenceRecord.v1",
    "cosing_ingredient_record": "cosIngIngredientRecord.v1",
    "cosing_product_use_evidence": "productUseEvidenceRecord.v1",
    "nanomaterial_evidence_record": "nanoMaterialEvidenceRecord.v1",
    "nanomaterial_product_use_evidence": "productUseEvidenceRecord.v1",
    "synthetic_polymer_microparticle_evidence_record": (
        "syntheticPolymerMicroparticleEvidenceRecord.v1"
    ),
    "synthetic_polymer_microparticle_product_use_evidence": ("productUseEvidenceRecord.v1"),
    "non_plastic_particle_product_use_evidence_record": "nanoMaterialEvidenceRecord.v1",
    "non_plastic_particle_product_use_evidence": "productUseEvidenceRecord.v1",
    "product_use_evidence_record": "productUseEvidenceRecord.v1",
    "product_use_evidence_fit_report": "productUseEvidenceFitReport.v1",
    "product_use_evidence_enriched_request": "exposureScenarioRequest.v1",
    "product_use_evidence_reconciliation_report": "productUseEvidenceReconciliationReport.v1",
    "integrated_exposure_workflow_request": "runIntegratedExposureWorkflowInput.v1",
    "integrated_exposure_workflow_result": "integratedExposureWorkflowResult.v1",
    "worker_task_routing_request": "workerTaskRoutingInput.v1",
    "worker_task_routing_decision": "workerTaskRoutingDecision.v1",
    "worker_inhalation_tier2_bridge_request": "exportWorkerInhalationTier2BridgeRequest.v1",
    "worker_inhalation_tier2_bridge_package": "workerInhalationTier2BridgePackage.v1",
    "worker_inhalation_tier2_adapter_request": "workerInhalationTier2AdapterRequest.v1",
    "worker_inhalation_tier2_adapter_ingest_result": (
        "workerInhalationTier2AdapterIngestResult.v1"
    ),
    "worker_inhalation_tier2_execution_request": "executeWorkerInhalationTier2Request.v1",
    "worker_inhalation_tier2_execution_result": "workerInhalationTier2ExecutionResult.v1",
    "worker_art_execution_package_request": "exportWorkerArtExecutionPackageRequest.v1",
    "worker_art_execution_package": "workerArtExternalExecutionPackage.v1",
    "worker_art_external_result": "workerArtExternalExecutionResult.v1",
    "worker_art_execution_result_import_request": "importWorkerArtExecutionResultRequest.v1",
    "worker_art_execution_result_import": "workerInhalationTier2ExecutionResult.v1",
    "worker_dermal_absorbed_dose_bridge_request": (
        "exportWorkerDermalAbsorbedDoseBridgeRequest.v1"
    ),
    "worker_dermal_absorbed_dose_bridge_package": "workerDermalAbsorbedDoseBridgePackage.v1",
    "worker_dermal_absorbed_dose_adapter_request": ("workerDermalAbsorbedDoseAdapterRequest.v1"),
    "worker_dermal_absorbed_dose_adapter_ingest_result": (
        "workerDermalAbsorbedDoseAdapterIngestResult.v1"
    ),
    "worker_dermal_absorbed_dose_execution_request": ("executeWorkerDermalAbsorbedDoseRequest.v1"),
    "worker_dermal_absorbed_dose_execution_result": ("workerDermalAbsorbedDoseExecutionResult.v1"),
    "toxclaw_evidence_envelope": "toxclawEvidenceEnvelope.v1",
    "toxclaw_evidence_bundle": "toxclawEvidenceBundle.v1",
    "toxclaw_refinement_bundle": "toxclawExposureRefinementBundle.v1",
    "pbpk_compatibility_report": "pbpkCompatibilityReport.v1",
    "tool_result_meta_completed": "toolResultMeta.v1",
    "tool_result_meta_failed": "toolResultMeta.v1",
}


def test_contract_assets_validate_examples_against_schemas() -> None:
    generate_contract_assets()

    for example_name, schema_name in EXAMPLE_SCHEMA_MAP.items():
        schema = json.loads((SCHEMA_DIR / f"{schema_name}.json").read_text(encoding="utf-8"))
        payload = json.loads((EXAMPLES_DIR / f"{example_name}.json").read_text(encoding="utf-8"))
        validate(instance=payload, schema=schema)


def test_contract_manifest_and_server_boot() -> None:
    generate_contract_assets()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["server_name"] == "exposure_scenario_mcp"
    assert len(manifest["tools"]) == 39
    tool_names = {tool["name"] for tool in manifest["tools"]}
    assert "worker_route_task" in tool_names
    assert "exposure_route_worker_task" in tool_names
    assert "worker_export_inhalation_tier2_bridge" in tool_names
    assert "exposure_export_worker_inhalation_tier2_bridge" in tool_names
    assert "worker_export_dermal_absorbed_dose_bridge" in tool_names
    assert "exposure_export_worker_dermal_absorbed_dose_bridge" in tool_names
    assert "chemicalIdentity.v1" in manifest["schemas"]
    assert "exposureScenarioDefinition.v1" in manifest["schemas"]
    assert "routeDoseEstimate.v1" in manifest["schemas"]
    assert "environmentalReleaseScenario.v1" in manifest["schemas"]
    assert "concentrationSurface.v1" in manifest["schemas"]
    assert "exposureScenario.v1" in manifest["schemas"]
    assert "inhalationTier1ScenarioRequest.v1" in manifest["schemas"]
    assert "consExpoEvidenceRecord.v1" in manifest["schemas"]
    assert "sccsCosmeticsEvidenceRecord.v1" in manifest["schemas"]
    assert "sccsOpinionEvidenceRecord.v1" in manifest["schemas"]
    assert "cosIngIngredientRecord.v1" in manifest["schemas"]
    assert "nanoMaterialEvidenceRecord.v1" in manifest["schemas"]
    assert "syntheticPolymerMicroparticleEvidenceRecord.v1" in manifest["schemas"]
    assert "particleMaterialContext.v1" in manifest["schemas"]
    assert "buildProductUseEvidenceFromConsExpoInput.v1" in manifest["schemas"]
    assert "buildProductUseEvidenceFromSccsInput.v1" in manifest["schemas"]
    assert "buildProductUseEvidenceFromSccsOpinionInput.v1" in manifest["schemas"]
    assert "buildProductUseEvidenceFromCosIngInput.v1" in manifest["schemas"]
    assert "buildProductUseEvidenceFromNanoMaterialInput.v1" in manifest["schemas"]
    assert (
        "buildProductUseEvidenceFromSyntheticPolymerMicroparticleInput.v1" in (manifest["schemas"])
    )
    assert "productUseEvidenceRecord.v1" in manifest["schemas"]
    assert "productUseEvidenceFitReport.v1" in manifest["schemas"]
    assert "assessProductUseEvidenceFitInput.v1" in manifest["schemas"]
    assert "applyProductUseEvidenceInput.v1" in manifest["schemas"]
    assert "productUseEvidenceReconciliationReport.v1" in manifest["schemas"]
    assert "reconcileProductUseEvidenceInput.v1" in manifest["schemas"]
    assert "runIntegratedExposureWorkflowInput.v1" in manifest["schemas"]
    assert "integratedExposureWorkflowResult.v1" in manifest["schemas"]
    assert "workerTaskRoutingInput.v1" in manifest["schemas"]
    assert "workerTaskRoutingDecision.v1" in manifest["schemas"]
    assert "workerInhalationTier2TaskContext.v1" in manifest["schemas"]
    assert "workerInhalationTier2CompatibilityReport.v1" in manifest["schemas"]
    assert "workerInhalationTier2AdapterRequest.v1" in manifest["schemas"]
    assert "workerInhalationTier2AdapterToolCall.v1" in manifest["schemas"]
    assert "workerInhalationTier2BridgePackage.v1" in manifest["schemas"]
    assert "exportWorkerInhalationTier2BridgeRequest.v1" in manifest["schemas"]
    assert "workerArtDeterminantTemplateMatch.v1" in manifest["schemas"]
    assert "workerInhalationArtTaskEnvelope.v1" in manifest["schemas"]
    assert "workerInhalationTier2AdapterIngestResult.v1" in manifest["schemas"]
    assert "workerInhalationTier2ExecutionOverrides.v1" in manifest["schemas"]
    assert "executeWorkerInhalationTier2Request.v1" in manifest["schemas"]
    assert "workerInhalationTier2ExecutionResult.v1" in manifest["schemas"]
    assert "workerDermalTaskContext.v1" in manifest["schemas"]
    assert "workerDermalCompatibilityReport.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseAdapterRequest.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseAdapterToolCall.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseBridgePackage.v1" in manifest["schemas"]
    assert "exportWorkerDermalAbsorbedDoseBridgeRequest.v1" in manifest["schemas"]
    assert "workerDermalDeterminantTemplateMatch.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseTaskEnvelope.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseAdapterIngestResult.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseExecutionOverrides.v1" in manifest["schemas"]
    assert "executeWorkerDermalAbsorbedDoseRequest.v1" in manifest["schemas"]
    assert "workerDermalAbsorbedDoseExecutionResult.v1" in manifest["schemas"]
    assert "tier1AirflowClassProfile.v1" in manifest["schemas"]
    assert "tier1ParticleRegimeProfile.v1" in manifest["schemas"]
    assert "tier1InhalationProductProfile.v1" in manifest["schemas"]
    assert "tier1InhalationParameterManifest.v1" in manifest["schemas"]
    assert "tier1InhalationTemplateParameters.v1" in manifest["schemas"]
    assert "archetypeLibraryManifest.v1" in manifest["schemas"]
    assert "archetypeLibrarySet.v1" in manifest["schemas"]
    assert "archetypeLibraryTemplate.v1" in manifest["schemas"]
    assert "probabilityBoundsProfileManifest.v1" in manifest["schemas"]
    assert "probabilityBoundsDriverProfile.v1" in manifest["schemas"]
    assert "scenarioPackageProbabilityManifest.v1" in manifest["schemas"]
    assert "scenarioPackageProbabilityProfile.v1" in manifest["schemas"]
    assert "assumptionGovernance.v1" in manifest["schemas"]
    assert "uncertaintyRegisterEntry.v1" in manifest["schemas"]
    assert "sensitivityRankingEntry.v1" in manifest["schemas"]
    assert "dependencyDescriptor.v1" in manifest["schemas"]
    assert "validationBenchmarkDomain.v1" in manifest["schemas"]
    assert "externalValidationDataset.v1" in manifest["schemas"]
    assert "validationReferenceBand.v1" in manifest["schemas"]
    assert "validationReferenceBandManifest.v1" in manifest["schemas"]
    assert "validationTimeSeriesReferencePoint.v1" in manifest["schemas"]
    assert "validationTimeSeriesReferencePack.v1" in manifest["schemas"]
    assert "validationTimeSeriesReferenceManifest.v1" in manifest["schemas"]
    assert "validationGap.v1" in manifest["schemas"]
    assert "executedValidationCheck.v1" in manifest["schemas"]
    assert "defaultsCurationEntry.v1" in manifest["schemas"]
    assert "defaultsCurationReport.v1" in manifest["schemas"]
    assert "validationDossierReport.v1" in manifest["schemas"]
    assert "validationSummary.v1" in manifest["schemas"]
    assert "tierUpgradeInputRequirement.v1" in manifest["schemas"]
    assert "tierUpgradeAdvisory.v1" in manifest["schemas"]
    assert "buildExposureEnvelopeFromLibraryInput.v1" in manifest["schemas"]
    assert "buildProbabilityBoundsFromProfileInput.v1" in manifest["schemas"]
    assert "buildProbabilityBoundsFromScenarioPackageInput.v1" in manifest["schemas"]
    assert "compareJurisdictionalScenariosInput.v1" in manifest["schemas"]
    assert "buildExposureEnvelopeInput.v1" in manifest["schemas"]
    assert "exposureEnvelopeSummary.v1" in manifest["schemas"]
    assert "buildParameterBoundsInput.v1" in manifest["schemas"]
    assert "parameterBoundsSummary.v1" in manifest["schemas"]
    assert "probabilityBoundsProfileSummary.v1" in manifest["schemas"]
    assert "scenarioPackageProbabilitySummary.v1" in manifest["schemas"]
    assert "pbpkExternalImportPackage.v1" in manifest["schemas"]
    assert "pbpkExternalImportRequest.v1" in manifest["schemas"]
    assert "jurisdictionalComparisonResult.v1" in manifest["schemas"]
    assert "releaseMetadataReport.v1" in manifest["schemas"]
    assert "verificationCheck.v1" in manifest["schemas"]
    assert "verificationSummaryReport.v1" in manifest["schemas"]
    assert "releaseReadinessReport.v1" in manifest["schemas"]
    assert "securityProvenanceReviewReport.v1" in manifest["schemas"]
    assert "tierSemantics.v1" in manifest["schemas"]
    assert "chemical_identity" in manifest["examples"]
    assert "exposure_scenario_definition" in manifest["examples"]
    assert "tcm_medicinal_oral_request" in manifest["examples"]
    assert "botanical_supplement_oral_request" in manifest["examples"]
    assert "dietary_supplement_oral_request" in manifest["examples"]
    assert "herbal_medicinal_infusion_request" in manifest["examples"]
    assert "tcm_topical_balm_request" in manifest["examples"]
    assert "herbal_topical_spray_request" in manifest["examples"]
    assert "herbal_recovery_patch_request" in manifest["examples"]
    assert "capsicum_hydrogel_patch_request" in manifest["examples"]
    assert "route_dose_estimate" in manifest["examples"]
    assert "environmental_release_scenario" in manifest["examples"]
    assert "concentration_surface" in manifest["examples"]
    assert "screening_dermal_scenario" in manifest["examples"]
    assert "exposure_envelope_summary" in manifest["examples"]
    assert "inhalation_tier1_request" in manifest["examples"]
    assert "inhalation_tier1_scenario" in manifest["examples"]
    assert "exposure_envelope_from_library_request" in manifest["examples"]
    assert "exposure_envelope_from_library_summary" in manifest["examples"]
    assert "inhalation_tier1_envelope_from_library_request" in manifest["examples"]
    assert "inhalation_tier1_envelope_from_library_summary" in manifest["examples"]
    assert "parameter_bounds_summary" in manifest["examples"]
    assert "probability_bounds_from_profile_request" in manifest["examples"]
    assert "probability_bounds_profile_summary" in manifest["examples"]
    assert "scenario_package_probability_request" in manifest["examples"]
    assert "scenario_package_probability_summary" in manifest["examples"]
    assert "inhalation_tier1_scenario_package_probability_request" in manifest["examples"]
    assert "inhalation_tier1_scenario_package_probability_summary" in manifest["examples"]
    assert "compare_jurisdictional_scenarios_request" in manifest["examples"]
    assert "jurisdictional_comparison_result" in manifest["examples"]
    assert "cons_expo_evidence_record" in manifest["examples"]
    assert "cons_expo_product_use_evidence" in manifest["examples"]
    assert "sccs_evidence_record" in manifest["examples"]
    assert "sccs_product_use_evidence" in manifest["examples"]
    assert "sccs_opinion_evidence_record" in manifest["examples"]
    assert "sccs_opinion_product_use_evidence" in manifest["examples"]
    assert "cosing_ingredient_record" in manifest["examples"]
    assert "cosing_product_use_evidence" in manifest["examples"]
    assert "nanomaterial_evidence_record" in manifest["examples"]
    assert "nanomaterial_product_use_evidence" in manifest["examples"]
    assert "synthetic_polymer_microparticle_evidence_record" in manifest["examples"]
    assert "synthetic_polymer_microparticle_product_use_evidence" in manifest["examples"]
    assert "non_plastic_particle_product_use_evidence_record" in manifest["examples"]
    assert "non_plastic_particle_product_use_evidence" in manifest["examples"]
    assert "product_use_evidence_record" in manifest["examples"]
    assert "product_use_evidence_fit_report" in manifest["examples"]
    assert "product_use_evidence_enriched_request" in manifest["examples"]
    assert "product_use_evidence_reconciliation_report" in manifest["examples"]
    assert "integrated_exposure_workflow_request" in manifest["examples"]
    assert "integrated_exposure_workflow_result" in manifest["examples"]
    assert "worker_task_routing_request" in manifest["examples"]
    assert "worker_task_routing_decision" in manifest["examples"]
    assert "worker_inhalation_tier2_bridge_request" in manifest["examples"]
    assert "worker_inhalation_tier2_bridge_package" in manifest["examples"]
    assert "worker_inhalation_tier2_adapter_request" in manifest["examples"]
    assert "worker_inhalation_tier2_adapter_ingest_result" in manifest["examples"]
    assert "worker_inhalation_tier2_execution_request" in manifest["examples"]
    assert "worker_inhalation_tier2_execution_result" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_bridge_request" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_bridge_package" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_adapter_request" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_adapter_ingest_result" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_execution_request" in manifest["examples"]
    assert "worker_dermal_absorbed_dose_execution_result" in manifest["examples"]
    assert "inhalation_residual_reentry_request" in manifest["examples"]
    assert "inhalation_residual_reentry_scenario" in manifest["examples"]
    assert "toxclaw_evidence_bundle" in manifest["examples"]
    assert "toxclaw_refinement_bundle" in manifest["examples"]
    assert {
        "docs://operator-guide",
        "docs://deployment-hardening-guide",
        "docs://provenance-policy",
        "docs://result-status-semantics",
        "docs://archetype-library-guide",
        "docs://probability-bounds-guide",
        "docs://tier1-inhalation-parameter-guide",
        "docs://uncertainty-framework",
        "docs://inhalation-tier-upgrade-guide",
        "docs://inhalation-residual-air-reentry-guide",
        "docs://defaults-curation-report",
        "docs://validation-framework",
        "docs://validation-dossier",
        "docs://validation-coverage-report",
        "docs://validation-reference-bands",
        "docs://validation-time-series-packs",
        "docs://verification-summary",
        "docs://goldset-benchmark-guide",
        "docs://exposure-platform-architecture",
        "docs://capability-maturity-matrix",
        "docs://repository-slug-decision",
        "docs://red-team-review-memo",
        "docs://cross-mcp-contract-guide",
        "docs://service-selection-guide",
        "docs://herbal-medicinal-routing-guide",
        "docs://toxmcp-suite-index",
        "docs://integrated-exposure-workflow-guide",
        "docs://worker-routing-guide",
        "docs://worker-tier2-bridge-guide",
        "docs://worker-art-adapter-guide",
        "docs://worker-art-execution-guide",
        "docs://worker-dermal-bridge-guide",
        "docs://worker-dermal-adapter-guide",
        "docs://worker-dermal-execution-guide",
        "docs://troubleshooting",
        "defaults://curation-report",
        "tier1-inhalation://manifest",
        "archetypes://manifest",
        "probability-bounds://manifest",
        "scenario-probability://manifest",
        "benchmarks://goldset",
        "docs://release-readiness",
        "docs://release-trust-checklist",
        "docs://release-notes",
        "docs://conformance-report",
        "docs://security-provenance-review",
        "docs://test-evidence-summary",
        "validation://manifest",
        "validation://dossier-report",
        "validation://coverage-report",
        "validation://reference-bands",
        "validation://time-series-packs",
        "verification://summary",
        "release://metadata-report",
        "release://readiness-report",
        "release://security-provenance-review-report",
    } <= {resource["uri"] for resource in manifest["resources"]}

    server = create_mcp_server()
    assert server is not None


def test_validation_dossier_report_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "validationDossierReport.v1.json").read_text(encoding="utf-8")
    )
    report = build_validation_dossier_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=report, schema=schema)
    assert report["policyVersion"] == "2026.03.25.v4"
    assert "heuristic_defaults_active" in {item["gapId"] for item in report["openGaps"]}
    assert "residual_air_reentry_validation_narrow_anchor_only" in {
        item["gapId"] for item in report["openGaps"]
    }
    assert "consumer_spray_inhalation_exposure_2015" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "spray_cleaning_disinfection_decay_half_life_2023" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "consumer_disinfectant_trigger_spray_inhalation_2015" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "household_mosquito_aerosol_indoor_air_2001" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "worker_biocidal_spray_foam_inhalation_2023" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "worker_biocidal_spray_foam_dermal_2023" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "diazinon_office_postapplication_air_1990" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "chlorpyrifos_broadcast_residential_air_1990" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "rivm_wet_cloth_dermal_contact_loading_2018" in {
        item["datasetId"] for item in report["externalDatasets"]
    }


def test_validation_coverage_report_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "validationCoverageReport.v1.json").read_text(encoding="utf-8")
    )
    report = build_validation_coverage_report().model_dump(mode="json", by_alias=True)

    validate(instance=report, schema=schema)
    assert report["policyVersion"] == "2026.03.25.v4"
    assert report["domainCount"] == 12
    assert report["benchmarkCaseCount"] == len(load_benchmark_manifest()["cases"])
    assert report["externalDatasetCount"] == 28
    assert report["referenceBandCount"] == 25
    assert report["timeSeriesPackCount"] == 3
    assert report["goldsetCaseCount"] == 23
    assert report["goldsetCoverageCounts"] == {
        "benchmark_regressed_showcase": 21,
        "challenge_case": 1,
        "integration_showcase": 1,
    }
    assert report["unmappedGoldsetCaseIds"] == []

    domain_summaries = {item["domain"]: item for item in report["domainSummaries"]}
    assert domain_summaries["inhalation_residual_air_reentry"]["coverageLevel"] == (
        "benchmark_time_resolved"
    )
    assert set(domain_summaries["inhalation_residual_air_reentry"]["timeSeriesPackIds"]) == {
        "chlorpyrifos_residual_air_reentry_room_air_series_1990",
        "diazinon_office_residual_air_series_1990",
    }
    assert domain_summaries["inhalation_well_mixed_spray"]["coverageLevel"] == (
        "benchmark_time_resolved"
    )
    assert set(domain_summaries["inhalation_well_mixed_spray"]["executableReferenceBandIds"]) == {
        "air_space_insecticide_aerosol_concentration_2001",
        "cleaning_trigger_spray_airborne_fraction_2019",
        "trigger_spray_aerosol_decay_half_life_2023",
        "worker_biocidal_professional_cleaning_concentration_2023",
    }
    assert (
        domain_summaries["worker_inhalation_control_aware_screening"]["coverageLevel"]
        == "benchmark_plus_executable_references"
    )
    assert domain_summaries["worker_dermal_absorbed_dose_screening"]["coverageLevel"] == (
        "benchmark_plus_executable_references"
    )
    assert {
        "vigabatrin_ready_to_use_dosing_accuracy_2025",
        "ema_valerian_root_oral_posology_2015",
        "ema_valerian_root_infusion_posology_2015",
        "ema_traditional_herbal_medicinal_oral_context_2026",
        "ec_food_supplement_capsule_context_2026",
        "nlm_dailymed_sideral_iron_capsule_label_2025",
        "nlm_dailymed_melatonin_gummy_label_2026",
        "nlm_dailymed_echinacea_tincture_label_2026",
        "nlm_dailymed_vitaminc_effervescent_label_2026",
    } <= set(domain_summaries["oral_direct_intake"]["externalDatasetIds"])
    assert {
        "medicinal_liquid_direct_oral_delivered_mass_2025",
        "herbal_medicinal_valerian_oral_daily_mass_2015",
        "herbal_medicinal_valerian_infusion_daily_mass_2015",
        "dietary_supplement_iron_capsule_daily_mass_2025",
        "dietary_supplement_melatonin_gummy_daily_mass_2026",
        "botanical_supplement_echinacea_tincture_daily_mass_2026",
        "dietary_supplement_effervescent_vitaminc_daily_mass_2026",
    } <= set(domain_summaries["oral_direct_intake"]["executableReferenceBandIds"])
    assert {
        "who_traditional_medicine_topical_context_2026",
        "ema_arnica_topical_application_geometry_2014",
        "nlm_dailymed_ahealon_topical_spray_label_2026",
        "nlm_dailymed_activmend_patch_label_2025",
        "nlm_dailymed_upup_capsicum_patch_label_2025",
    } <= set(domain_summaries["dermal_direct_application"]["externalDatasetIds"])
    assert {
        "hand_cream_application_loading_2012",
        "herbal_topical_application_strip_length_2014",
        "herbal_topical_spray_label_amount_2026",
        "herbal_recovery_patch_label_amount_2025",
        "capsicum_hydrogel_patch_label_amount_2025",
    } <= set(domain_summaries["dermal_direct_application"]["executableReferenceBandIds"])
    assert any(
        "Coverage levels describe current trust posture by domain" in note
        for note in report["overallNotes"]
    )


def test_validation_reference_band_manifest_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "validationReferenceBandManifest.v1.json").read_text(encoding="utf-8")
    )
    report = (
        ValidationReferenceBandRegistry.load().manifest().model_dump(mode="json", by_alias=True)
    )

    validate(instance=report, schema=schema)
    assert report["referenceVersion"] == "2026.04.14.v3"
    assert report["bandCount"] == 25
    assert {item["checkId"] for item in report["bands"]} == {
        "air_space_insecticide_aerosol_concentration_2001",
        "capsicum_hydrogel_patch_label_amount_2025",
        "chlorpyrifos_residual_air_reentry_start_concentration_1990",
        "cleaning_trigger_spray_airborne_fraction_2019",
        "consumer_disinfectant_trigger_spray_inhaled_dose_2015",
        "dietary_supplement_iron_capsule_daily_mass_2025",
        "dietary_supplement_melatonin_gummy_daily_mass_2026",
        "botanical_supplement_echinacea_tincture_daily_mass_2026",
        "dietary_supplement_effervescent_vitaminc_daily_mass_2026",
        "diazinon_home_use_residual_air_concentration_2008",
        "hand_cream_application_loading_2012",
        "herbal_recovery_patch_label_amount_2025",
        "herbal_medicinal_valerian_infusion_daily_mass_2015",
        "herbal_medicinal_valerian_oral_daily_mass_2015",
        "herbal_topical_application_strip_length_2014",
        "herbal_topical_spray_label_amount_2026",
        "medicinal_liquid_direct_oral_delivered_mass_2025",
        "trigger_spray_aerosol_decay_half_life_2023",
        "worker_biocidal_handheld_trigger_spray_dermal_mass_2023",
        "worker_biocidal_handheld_trigger_spray_concentration_2023",
        "worker_biocidal_professional_cleaning_concentration_2023",
        "wet_cloth_contact_mass_2018",
        "ema_hmpc_topical_ointment_loading_default",
        "sccs_cosmetic_balm_loading_category",
        "dermatology_fingertip_unit_loading_anchor",
    }


def test_validation_time_series_manifest_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "validationTimeSeriesReferenceManifest.v1.json").read_text(encoding="utf-8")
    )
    report = (
        ValidationTimeSeriesReferenceRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )

    validate(instance=report, schema=schema)
    assert report["referenceVersion"] == "2026.04.08.v3"
    assert report["packCount"] == 3
    assert report["pointCount"] == 6
    assert {item["referencePackId"] for item in report["packs"]} == {
        "air_space_insecticide_aerosol_room_air_series_2001",
        "chlorpyrifos_residual_air_reentry_room_air_series_1990",
        "diazinon_office_residual_air_series_1990",
    }


def test_defaults_curation_report_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads((SCHEMA_DIR / "defaultsCurationReport.v1.json").read_text(encoding="utf-8"))
    report = build_defaults_curation_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=report, schema=schema)
    assert report["defaultsVersion"] == DefaultsRegistry.load().version
    assert report["heuristicEntryCount"] > 0
    cleaner_wipe_transfer = (
        "transfer_efficiency:application_method=wipe,product_category=household_cleaner"
    )
    cleaner_surface_contact = (
        "retention_factor:product_category=household_cleaner,retention_type=surface_contact"
    )
    assert any(
        item["pathId"] == cleaner_wipe_transfer and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == cleaner_surface_contact and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == "aerosolized_fraction:application_method=pump_spray,product_category=personal_care"
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == "aerosolized_fraction:application_method=aerosol_spray,product_category=personal_care"
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == "aerosolized_fraction:application_method=trigger_spray,product_category=disinfectant"
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == (
            "aerosolized_fraction:application_method=trigger_spray,"
            "product_subtype=surface_trigger_spray_disinfectant"
        )
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == "aerosolized_fraction:application_method=trigger_spray,product_category=pesticide"
        and item["curationStatus"] == "heuristic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == (
            "aerosolized_fraction:application_method=trigger_spray,"
            "product_subtype=indoor_surface_insecticide"
        )
        and item["curationStatus"] == "heuristic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "density_g_per_ml:product_subtype=air_space_insecticide"
        and item["curationStatus"] == "heuristic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == "pressurized_aerosol_volume_interpretation_factor:application_method=aerosol_spray"
        and item["curationStatus"] == "heuristic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"]
        == (
            "aerosolized_fraction:application_method=aerosol_spray,"
            "product_subtype=air_space_insecticide"
        )
        and item["curationStatus"] == "heuristic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "room_volume_m3:product_subtype=air_space_insecticide"
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "transfer_efficiency:application_method=trigger_spray"
        and item["curationStatus"] == "route_semantic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "transfer_efficiency:application_method=hand_application"
        and item["curationStatus"] == "route_semantic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "transfer_efficiency:application_method=wipe"
        and item["curationStatus"] == "curated"
        for item in report["entries"]
    )


def test_release_readiness_report_matches_schema_and_manifest_counts() -> None:
    generate_contract_assets()
    schema = json.loads((SCHEMA_DIR / "releaseReadinessReport.v1.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_release_readiness_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=report, schema=schema)
    assert report["publicSurface"]["toolCount"] == len(manifest["tools"])
    assert report["publicSurface"]["resourceCount"] == len(manifest["resources"])
    assert report["publicSurface"]["promptCount"] == len(manifest["prompts"])
    assert report["status"] == "ready_with_known_limitations"


def test_security_provenance_review_report_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "securityProvenanceReviewReport.v1.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_security_provenance_review_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=report, schema=schema)
    assert report["status"] == "acceptable_with_warnings"
    assert len(report["reviewedSurface"]["toolNames"]) == len(manifest["tools"])
    assert len(report["reviewedSurface"]["resourceUris"]) == len(manifest["resources"])
    assert len(report["reviewedSurface"]["promptNames"]) == len(manifest["prompts"])
    finding_ids = {finding["findingId"] for finding in report["findings"]}
    assert "heuristic-defaults-remain" in finding_ids
    assert "remote-transport-controls-externalized" in finding_ids


def test_release_metadata_report_matches_schema_and_published_artifact() -> None:
    generate_contract_assets()
    schema = json.loads((SCHEMA_DIR / "releaseMetadataReport.v1.json").read_text(encoding="utf-8"))
    artifact = json.loads(RELEASE_METADATA_PATH.read_text(encoding="utf-8"))
    report = build_release_metadata_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=artifact, schema=schema)
    validate(instance=report, schema=schema)
    assert artifact["releaseVersion"] == CURRENT_VERSION
    assert artifact["benchmarkCaseCount"] == len(load_benchmark_manifest()["cases"])
    assert {"wheel", "sdist"} == {item["kind"] for item in artifact["distributionArtifacts"]}
    assert "docs://release-notes" in artifact["publishedDocs"]
    assert "docs://release-trust-checklist" in artifact["publishedDocs"]
    assert "docs://deployment-hardening-guide" in artifact["publishedDocs"]
    assert "docs://goldset-benchmark-guide" in artifact["publishedDocs"]
    assert "docs://capability-maturity-matrix" in artifact["publishedDocs"]
    assert "docs://red-team-review-memo" in artifact["publishedDocs"]
    assert "docs://test-evidence-summary" in artifact["publishedDocs"]
    artifacts_by_kind = {item["kind"]: item for item in artifact["distributionArtifacts"]}
    wheel_artifact = artifacts_by_kind["wheel"]
    assert isinstance(wheel_artifact["sha256"], str)
    assert len(wheel_artifact["sha256"]) == 64
    assert isinstance(wheel_artifact["sizeBytes"], int)
    assert wheel_artifact["sizeBytes"] > 0

    sdist_artifact = artifacts_by_kind["sdist"]
    assert sdist_artifact["present"] is True
    assert sdist_artifact["sha256"] is None
    assert sdist_artifact["sizeBytes"] is None
    assert "uv build" in artifact["validationCommands"]
    assert "uv run check-exposure-release-artifacts" in artifact["validationCommands"]
    assert report["contractSchemaCount"] >= 1


def test_defaults_manifest_hash_matches_live_file() -> None:
    """The static defaults manifest hash must match the actual defaults file on disk."""
    manifest = json.loads((REPO_ROOT / "defaults" / "manifest.json").read_text(encoding="utf-8"))
    registry = DefaultsRegistry.load()
    assert manifest["defaults_hash_sha256"] == registry.sha256


def test_verification_summary_report_matches_schema_and_surface() -> None:
    generate_contract_assets()
    schema = json.loads(
        (SCHEMA_DIR / "verificationSummaryReport.v1.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = build_verification_summary_report(DefaultsRegistry.load()).model_dump(
        mode="json", by_alias=True
    )

    validate(instance=report, schema=schema)
    assert report["publicSurface"]["toolCount"] == len(manifest["tools"])
    assert report["publicSurface"]["resourceCount"] == len(manifest["resources"])
    assert report["validationDomainCount"] == 12
    assert report["benchmarkCaseCount"] == len(load_benchmark_manifest()["cases"])
    assert report["referenceBandCount"] == 25
    assert report["timeSeriesPackCount"] == 3
    assert report["goldsetCaseCount"] >= 1
    check_ids = {item["checkId"] for item in report["checks"]}
    assert "contract-surface-alignment" in check_ids
    assert "validation-resource-publication" in check_ids
    assert "suite-boundary-guides-published" in check_ids
    assert "verification://summary" in report["publishedResources"]
    assert "docs://verification-summary" in report["publishedResources"]
    assert "docs://release-trust-checklist" in report["publishedResources"]
    assert "docs://deployment-hardening-guide" in report["publishedResources"]
    assert "docs://test-evidence-summary" in report["publishedResources"]
