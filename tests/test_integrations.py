from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.integrations import (
    CompToxChemicalRecord,
    apply_comptox_enrichment,
    build_pbpk_external_import_package,
    build_toxclaw_evidence_bundle,
    build_toxclaw_evidence_envelope,
    build_toxclaw_refinement_bundle,
    check_pbpk_compatibility,
)
from exposure_scenario_mcp.models import (
    ExportPbpkExternalImportBundleRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PBPK_TOOL_PATH = (
    WORKSPACE_ROOT.parent
    / "PBPK_MCP"
    / "src"
    / "mcp"
    / "tools"
    / "ingest_external_pbpk_bundle.py"
)


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_comptox_enrichment_and_toxclaw_wrapper() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="legacy_category",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=3,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )
    record = CompToxChemicalRecord(
        chemical_id="DTXSID123",
        preferred_name="Benchmark Solvent A",
        casrn="123-45-6",
        product_use_categories=["personal_care"],
        evidence_sources=["CompTox:mock-record-001"],
    )

    enriched = apply_comptox_enrichment(request, record)
    scenario = engine.build(enriched)
    envelope = build_toxclaw_evidence_envelope(
        scenario,
        context_of_use="screening_prioritization",
    )
    report = check_pbpk_compatibility(scenario)

    assert enriched.chemical_name == "Benchmark Solvent A"
    assert enriched.product_use_profile.product_category == "personal_care"
    assert envelope.record_kind == "exposureScenario"
    assert envelope.chemical_id == scenario.chemical_id
    assert report.compatible is True
    assert report.checked_dose_unit == "mg/kg-day"
    assert report.ready_for_external_pbpk_import is True


def test_toxclaw_evidence_bundle_is_deterministic_and_claim_linked() -> None:
    engine = build_engine()
    scenario = engine.build(
        ExposureScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="personal_care",
                physical_form="cream",
                application_method="hand_application",
                retention_type="leave_on",
                concentration_fraction=0.02,
                use_amount_per_event=1.5,
                use_amount_unit="g",
                use_events_per_day=3,
            ),
            population_profile=PopulationProfile(population_group="adult"),
        )
    )

    request = ExportToxClawEvidenceBundleRequest(
        scenario=scenario,
        case_id="case-001",
        report_id="report-001",
    )
    first = build_toxclaw_evidence_bundle(request)
    second = build_toxclaw_evidence_bundle(request)

    assert first.evidence_record.evidence_id == second.evidence_record.evidence_id
    assert first.evidence_record.content_hash == second.evidence_record.content_hash
    assert first.report_section.evidence_ids == [first.evidence_record.evidence_id]
    assert all(
        claim.evidence_ids == [first.evidence_record.evidence_id]
        for claim in first.report_section.claims
    )
    exported = first.model_dump(mode="json", by_alias=True)
    assert exported["evidenceRecord"]["evidenceId"] == first.evidence_record.evidence_id
    assert exported["reportSection"]["sectionKey"] == "exposure-scenario"


def test_toxclaw_refinement_bundle_signals_refine_exposure_and_preserves_deltas() -> None:
    engine = build_engine()
    baseline_request = ExposureScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=3,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )
    baseline = engine.build(baseline_request)
    refined = engine.build(
        baseline_request.model_copy(
            update={
                "product_use_profile": baseline_request.product_use_profile.model_copy(
                    update={"retention_factor": 0.3, "transfer_efficiency": 0.25}
                )
            }
        )
    )

    bundle = build_toxclaw_refinement_bundle(
        ExportToxClawRefinementBundleRequest(
            baseline=baseline,
            comparison=refined,
            case_id="case-001",
            report_id="report-001",
        )
    )
    exported = bundle.model_dump(mode="json", by_alias=True)

    assert exported["workflowAction"] == "scenario_comparison"
    assert exported["refinementSignal"]["recommendation"] == "refine_exposure"
    assert exported["refinementSignal"]["loeCandidateKeys"] == ["exposure_context"]
    assert "exposure-refinement" in exported["evidenceRecord"]["tags"]
    assert "refinement" in exported["evidenceRecord"]["tags"]
    assert exported["reportSection"]["evidenceIds"] == [exported["evidenceRecord"]["evidenceId"]]
    assert {
        delta["name"] for delta in exported["comparisonRecord"]["changed_assumptions"]
    } >= {"retention_factor", "transfer_efficiency"}
    assert {
        hook["toolName"] for hook in exported["refinementSignal"]["workflowHooks"]
    } == {
        "exposure_compare_exposure_scenarios",
        "exposure_build_screening_exposure_scenario",
        "exposure_build_aggregate_exposure_scenario",
        "exposure_export_pbpk_external_import_bundle",
    }


def test_pbpk_external_import_package_prefills_real_request_shape() -> None:
    engine = build_engine()
    scenario = engine.build(
        ExposureScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="personal_care",
                physical_form="cream",
                application_method="hand_application",
                retention_type="leave_on",
                concentration_fraction=0.02,
                use_amount_per_event=1.5,
                use_amount_unit="g",
                use_events_per_day=3,
            ),
            population_profile=PopulationProfile(population_group="adult"),
        )
    )

    package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(scenario=scenario)
    )
    exported = package.model_dump(mode="json", by_alias=True)

    assert exported["ingestToolName"] == "ingest_external_pbpk_bundle"
    assert exported["toolCall"]["toolName"] == "ingest_external_pbpk_bundle"
    assert exported["toolCall"]["arguments"]["assessmentContext"]["contextOfUse"] == (
        "screening-brief"
    )
    assert "bundle" not in exported["toolCall"]["arguments"]
    assert exported["requestPayload"]["sourcePlatform"] == "exposure-scenario-mcp"
    assert exported["bundle"]["sourcePlatform"] == "exposure-scenario-mcp"
    assert exported["bundle"]["assessmentContext"]["doseScenario"]["scenarioId"] == (
        scenario.scenario_id
    )
    assert exported["bundle"]["chemicalIdentity"]["preferredName"] == "Example Solvent A"
    assert exported["bundle"]["supportingHandoffs"]["pbpkScenarioInput"]["schema_version"] == (
        "pbpkScenarioInput.v1"
    )
    assert exported["toxclawModuleParams"]["ingestToolName"] == "ingest_external_pbpk_bundle"
    assert exported["toxclawModuleParams"]["arguments"]["sourcePlatform"] == (
        "exposure-scenario-mcp"
    )
    assert exported["toxclawModuleParams"]["supportingHandoffs"]["pbpkScenarioInput"][
        "schema_version"
    ] == (
        "pbpkScenarioInput.v1"
    )
    assert exported["compatibilityReport"]["ready_for_external_pbpk_import"] is True
    assert exported["compatibilityReport"]["missing_external_bundle_fields"] == []


def test_pbpk_external_import_package_validates_against_sibling_pbpk_request_when_available(
) -> None:
    if not PBPK_TOOL_PATH.exists():
        return

    spec = importlib.util.spec_from_file_location(
        "pbpk_external_bundle_upstream_check",
        PBPK_TOOL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load upstream PBPK tool from {PBPK_TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("pbpk_external_bundle_upstream_check", module)
    spec.loader.exec_module(module)

    engine = build_engine()
    scenario = engine.build(
        ExposureScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="personal_care",
                physical_form="cream",
                application_method="hand_application",
                retention_type="leave_on",
                concentration_fraction=0.02,
                use_amount_per_event=1.5,
                use_amount_unit="g",
                use_events_per_day=3,
            ),
            population_profile=PopulationProfile(population_group="adult"),
        )
    )
    package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(scenario=scenario)
    )
    arguments = package.tool_call.model_dump(mode="json", by_alias=True)["arguments"]

    request = module.IngestExternalPbpkBundleRequest(**arguments)
    response = module.ingest_external_pbpk_bundle(request).model_dump(by_alias=True)

    assert "bundle" not in arguments
    assert response["tool"] == "ingest_external_pbpk_bundle"
    assert response["contractVersion"] == "pbpk-mcp.v1"
    assert response["externalRun"]["sourcePlatform"] == arguments["sourcePlatform"]
    assert response["ngraObjects"]["assessmentContext"]["sourcePlatform"] == (
        arguments["sourcePlatform"]
    )
