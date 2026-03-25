from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.server import create_mcp_server
from exposure_scenario_mcp.validation import build_validation_dossier_report
from scripts.generate_contract_assets import main as generate_contract_assets

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMA_DIR / "examples"
MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"
RELEASE_METADATA_PATH = REPO_ROOT / "docs" / "releases" / "v0.1.0.release_metadata.json"


EXAMPLE_SCHEMA_MAP = {
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
    "pbpk_input": "pbpkScenarioInput.v1",
    "pbpk_external_import_request": "pbpkExternalImportRequest.v1",
    "pbpk_external_import_tool_call": "pbpkExternalImportToolCall.v1",
    "toxclaw_pbpk_module_params": "toxclawPbpkModuleParams.v1",
    "pbpk_external_import_package": "pbpkExternalImportPackage.v1",
    "comparison_record": "scenarioComparisonRecord.v1",
    "comp_tox_record": "compToxChemicalRecord.v1",
    "comp_tox_enriched_request": "exposureScenarioRequest.v1",
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
    assert len(manifest["tools"]) == 14
    assert "exposureScenario.v1" in manifest["schemas"]
    assert "inhalationTier1ScenarioRequest.v1" in manifest["schemas"]
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
    assert "buildExposureEnvelopeInput.v1" in manifest["schemas"]
    assert "exposureEnvelopeSummary.v1" in manifest["schemas"]
    assert "buildParameterBoundsInput.v1" in manifest["schemas"]
    assert "parameterBoundsSummary.v1" in manifest["schemas"]
    assert "probabilityBoundsProfileSummary.v1" in manifest["schemas"]
    assert "scenarioPackageProbabilitySummary.v1" in manifest["schemas"]
    assert "pbpkExternalImportPackage.v1" in manifest["schemas"]
    assert "pbpkExternalImportRequest.v1" in manifest["schemas"]
    assert "releaseMetadataReport.v1" in manifest["schemas"]
    assert "releaseReadinessReport.v1" in manifest["schemas"]
    assert "securityProvenanceReviewReport.v1" in manifest["schemas"]
    assert "tierSemantics.v1" in manifest["schemas"]
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
    assert "toxclaw_evidence_bundle" in manifest["examples"]
    assert "toxclaw_refinement_bundle" in manifest["examples"]
    assert {
        "docs://operator-guide",
        "docs://provenance-policy",
        "docs://result-status-semantics",
        "docs://archetype-library-guide",
        "docs://probability-bounds-guide",
        "docs://tier1-inhalation-parameter-guide",
        "docs://uncertainty-framework",
        "docs://inhalation-tier-upgrade-guide",
        "docs://defaults-curation-report",
        "docs://validation-framework",
        "docs://validation-dossier",
        "docs://troubleshooting",
        "defaults://curation-report",
        "tier1-inhalation://manifest",
        "archetypes://manifest",
        "probability-bounds://manifest",
        "scenario-probability://manifest",
        "docs://release-readiness",
        "docs://release-notes",
        "docs://conformance-report",
        "docs://security-provenance-review",
        "validation://manifest",
        "validation://dossier-report",
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
    assert "consumer_spray_inhalation_exposure_2015" in {
        item["datasetId"] for item in report["externalDatasets"]
    }
    assert "rivm_wet_cloth_dermal_contact_loading_2018" in {
        item["datasetId"] for item in report["externalDatasets"]
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
        item["pathId"] == "transfer_efficiency:application_method=trigger_spray"
        and item["curationStatus"] == "route_semantic"
        for item in report["entries"]
    )
    assert any(
        item["pathId"] == "transfer_efficiency:application_method=wipe"
        and item["curationStatus"] == "heuristic"
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
    assert artifact["releaseVersion"] == "0.1.0"
    assert artifact["benchmarkCaseCount"] == len(load_benchmark_manifest()["cases"])
    assert {"wheel", "sdist"} == {item["kind"] for item in artifact["distributionArtifacts"]}
    assert "docs://release-notes" in artifact["publishedDocs"]
    for item in artifact["distributionArtifacts"]:
        if item["present"]:
            assert item["sha256"] is not None
            assert item["sizeBytes"] is not None
        else:
            assert item["sha256"] is None
            assert item["sizeBytes"] is None
    assert "uv build" in artifact["validationCommands"]
    assert "uv run check-exposure-release-artifacts" in artifact["validationCommands"]
    assert report["contractSchemaCount"] >= 1
