from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.integrations import (
    CompToxChemicalRecord,
    ConsExpoEvidenceRecord,
    ProductUseEvidenceRecord,
    RunIntegratedExposureWorkflowInput,
    apply_comptox_enrichment,
    apply_product_use_evidence,
    assess_product_use_evidence_fit,
    build_pbpk_external_import_package,
    build_product_use_evidence_from_comptox,
    build_product_use_evidence_from_consexpo,
    build_toxclaw_evidence_bundle,
    build_toxclaw_evidence_envelope,
    build_toxclaw_refinement_bundle,
    check_pbpk_compatibility,
    reconcile_product_use_evidence,
    run_integrated_exposure_workflow,
)
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    ExportPbpkExternalImportBundleRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
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
            product_category="pesticide",
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


def test_product_use_evidence_fit_flags_cross_jurisdiction_review() -> None:
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    comptox_record = CompToxChemicalRecord(
        chemical_id="DTXSID123",
        preferred_name="Benchmark Solvent A",
        casrn="123-45-6",
        product_use_categories=["personal_care"],
        physchem_summary={"vapor_pressure_pa": 150.0},
        evidence_sources=["CompTox:mock-record-001"],
    )

    evidence = build_product_use_evidence_from_comptox(comptox_record)
    report = assess_product_use_evidence_fit(request, evidence)

    assert report.compatible is True
    assert report.auto_apply_safe is False
    assert report.recommendation == "accept_with_review"
    assert report.suggested_request.product_use_profile.product_category == "personal_care"
    assert any("jurisdictions" in item for item in report.warnings)


def test_product_use_evidence_blocks_mismatched_application_method() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["granule_spread"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        evidence_sources=["EU-Dossier:001"],
    )

    report = assess_product_use_evidence_fit(request, evidence)

    assert report.compatible is False
    assert report.recommendation == "reject"
    assert report.blocking_issues


def test_apply_product_use_evidence_preserves_source_metadata() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Benchmark Solvent A",
        casrn="123-45-6",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        source_record_id="EU-DOSSIER-001",
        source_locator="https://example.org/eu-dossier/001",
        product_name="Example Surface Spray",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        physchem_summary={"density_g_per_ml": 1.08},
        evidence_sources=["EU-Dossier:001"],
    )

    enriched = apply_product_use_evidence(request, evidence)

    assert enriched.chemical_name == "Benchmark Solvent A"
    assert enriched.product_use_profile.product_category == "pesticide"
    assert enriched.product_use_profile.product_name == "Example Surface Spray"
    assert enriched.product_use_profile.product_subtype == "indoor_surface_insecticide"
    assert enriched.product_use_profile.density_g_per_ml == 1.08
    assert enriched.assumption_overrides["external_product_use_source_name"] == (
        "EU pesticide dossier"
    )
    assert enriched.assumption_overrides["external_product_use_casrn"] == "123-45-6"
    assert enriched.assumption_overrides["external_product_use_physchem_density_g_per_ml"] == 1.08


def test_product_use_evidence_does_not_override_explicit_density() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
            density_g_per_ml=0.95,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        physchem_summary={"density_g_per_ml": 1.08},
    )

    report = assess_product_use_evidence_fit(request, evidence)

    assert report.compatible is True
    assert report.suggested_request.product_use_profile.density_g_per_ml == 0.95
    assert any("density_g_per_ml" in item for item in report.warnings)


def test_product_use_evidence_blocks_mismatched_product_subtype() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="crack_and_crevice_insecticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
    )

    report = assess_product_use_evidence_fit(request, evidence)

    assert report.compatible is False
    assert report.recommendation == "reject"
    assert any("product_subtype" in item for item in report.blocking_issues)


def test_apply_product_use_evidence_returns_base_request_contract() -> None:
    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
    )

    enriched = apply_product_use_evidence(inhalation_request, evidence)

    assert isinstance(enriched, ExposureScenarioRequest)
    assert "requestedTier" not in enriched.model_dump(mode="json", by_alias=True)


def test_build_product_use_evidence_from_consexpo_maps_pest_control_family() -> None:
    record = ConsExpoEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        factSheetId="pest_control_products_fact_sheet_2006",
        factSheetTitle="ConsExpo Pest Control Products Fact Sheet",
        factSheetVersion="RIVM report 320005002 / 2006",
        factSheetLocator="https://www.rivm.nl/bibliotheek/rapporten/320005002.pdf",
        productGroup="pest_control_products",
        productSubgroup="Indoor trigger spray insecticide",
        modelFamily="spray",
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        physchem_summary={"density_g_per_ml": 1.08},
    )

    evidence = build_product_use_evidence_from_consexpo(record)

    assert evidence.source_kind == "consexpo"
    assert evidence.source_name == "RIVM ConsExpo"
    assert evidence.product_subtype == "indoor_surface_insecticide"
    assert evidence.product_use_categories == ["pest_control", "pesticide", "biocide"]
    assert evidence.source_record_id == "pest_control_products_fact_sheet_2006"
    assert evidence.source_locator == "https://www.rivm.nl/bibliotheek/rapporten/320005002.pdf"
    assert any("supported routes" in note.lower() for note in evidence.notes)


def test_build_product_use_evidence_from_consexpo_maps_air_space_subtype() -> None:
    record = ConsExpoEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        factSheetId="pest_control_products_fact_sheet_2006",
        factSheetTitle="ConsExpo Pest Control Products Fact Sheet",
        factSheetVersion="RIVM report 320005002 / 2006",
        factSheetLocator="https://www.rivm.nl/bibliotheek/rapporten/320005002.pdf",
        productGroup="pest_control_products",
        productSubgroup="Air space aerosol insecticide",
        modelFamily="spray",
        supportedRoutes=[Route.INHALATION],
        physical_forms=["spray"],
        application_methods=["aerosol_spray"],
        retention_types=["surface_contact"],
        physchem_summary={"density_g_per_ml": 0.8},
    )

    evidence = build_product_use_evidence_from_consexpo(record)

    assert evidence.product_subtype == "air_space_insecticide"
    assert evidence.product_use_categories == ["pest_control", "pesticide", "biocide"]
    assert evidence.application_methods == ["aerosol_spray"]


def test_reconcile_product_use_evidence_prefers_region_specific_reviewed_source() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    comptox_record = CompToxChemicalRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        evidence_sources=["CompTox:mock-record-001"],
    )
    eu_evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_name="Diazinon indoor surface spray",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        physchem_summary={"density_g_per_ml": 1.08},
        evidence_sources=["EU-Dossier:001"],
    )

    report = reconcile_product_use_evidence(
        request,
        [build_product_use_evidence_from_comptox(comptox_record), eu_evidence],
    )

    assert report.recommendation == "apply"
    assert report.recommended_source_name == "EU pesticide dossier"
    assert report.manual_review_required is False
    assert report.merged_request is not None
    assert report.merged_request.product_use_profile.product_subtype == "indoor_surface_insecticide"
    assert report.merged_request.product_use_profile.density_g_per_ml == 1.08
    assert report.field_sources["product_use_profile.density_g_per_ml"] == "EU pesticide dossier"


def test_reconcile_product_use_evidence_prefers_consexpo_over_comptox_in_eu() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    comptox_record = CompToxChemicalRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        evidence_sources=["CompTox:mock-record-001"],
    )
    cons_expo_record = ConsExpoEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Diazinon",
        casrn="333-41-5",
        factSheetId="pest_control_products_fact_sheet_2006",
        factSheetTitle="ConsExpo Pest Control Products Fact Sheet",
        factSheetVersion="RIVM report 320005002 / 2006",
        factSheetLocator="https://www.rivm.nl/bibliotheek/rapporten/320005002.pdf",
        productGroup="pest_control_products",
        productSubgroup="Indoor trigger spray insecticide",
        modelFamily="spray",
        supportedRoutes=[Route.DERMAL, Route.INHALATION],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        physchem_summary={"density_g_per_ml": 1.08},
    )

    report = reconcile_product_use_evidence(
        request,
        [
            build_product_use_evidence_from_comptox(comptox_record),
            build_product_use_evidence_from_consexpo(cons_expo_record),
        ],
    )

    assert report.recommended_source_name == "RIVM ConsExpo"
    assert report.recommendation == "apply"
    assert report.merged_request is not None
    assert report.merged_request.product_use_profile.density_g_per_ml == 1.08


def test_reconcile_product_use_evidence_rejects_when_no_source_fits() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="Granule dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_use_categories=["pesticide"],
        physical_forms=["granule"],
        application_methods=["granule_spread"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
    )

    report = reconcile_product_use_evidence(request, [evidence])

    assert report.recommendation == "reject"
    assert report.merged_request is None
    assert report.compatible_sources == []


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


def test_integrated_workflow_reconciles_evidence_builds_scenario_and_exports_pbpk() -> None:
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        chemical_name="Example Worker Chemical",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25.0,
            air_exchange_rate_per_hour=2.0,
            exposure_duration_hours=0.5,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=75.0,
            inhalation_rate_m3_per_hour=1.0,
            region="EU",
        ),
    )
    comptox_record = CompToxChemicalRecord(
        chemical_id="DTXSID123",
        preferred_name="Example Worker Chemical",
        casrn="123-45-6",
        product_use_categories=["pesticide"],
        evidence_sources=["CompTox:mock-record-001"],
    )
    dossier_evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        preferred_name="Example Worker Chemical",
        casrn="123-45-6",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_name="Example Surface Spray",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
        physchem_summary={"density_g_per_ml": 1.08},
        evidence_sources=["EU-Dossier:001"],
    )

    result = run_integrated_exposure_workflow(
        RunIntegratedExposureWorkflowInput(
            request=request,
            comp_tox_record=comptox_record,
            evidence_records=[dossier_evidence],
            pbpk_regimen_name="screening_daily_use",
            pbpk_context_of_use="screening-brief",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.evidence_strategy == "reconciled_evidence_applied"
    assert result.selected_evidence_source_name == "EU pesticide dossier"
    assert result.manual_review_required is False
    assert result.effective_request.product_use_profile.product_category == "pesticide"
    assert result.effective_request.product_use_profile.product_name == "Example Surface Spray"
    assert result.effective_request.product_use_profile.density_g_per_ml == 1.08
    assert result.scenario.route == Route.INHALATION
    assert result.pbpk_scenario_input is not None
    assert result.pbpk_external_import_package is not None
    assert result.pbpk_external_import_package.compatibility_report.ready_for_external_pbpk_import
    assert any(
        flag.code == "integrated_workflow_pbpk_external_import_bundle_exported"
        for flag in result.quality_flags
    )


def test_integrated_workflow_preserves_tier1_request_contract_after_reconciliation() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        chemical_name="Example Worker Chemical",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="legacy_category",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25.0,
            air_exchange_rate_per_hour=2.0,
            exposure_duration_hours=0.5,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=75.0,
            inhalation_rate_m3_per_hour=1.0,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=10.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )
    dossier_evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="EU pesticide dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_subtype="indoor_surface_insecticide",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        retention_types=["surface_contact"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
    )

    result = run_integrated_exposure_workflow(
        RunIntegratedExposureWorkflowInput(
            request=request,
            evidence_records=[dossier_evidence],
            export_pbpk_external_import_bundle=False,
        ),
        registry=DefaultsRegistry.load(),
    )

    assert isinstance(result.effective_request, InhalationTier1ScenarioRequest)
    assert result.effective_request.requested_tier.value == "tier_1"
    assert result.effective_request.source_distance_m == 0.35
    assert result.effective_request.product_use_profile.product_category == "pesticide"
    assert result.scenario.route == Route.INHALATION
    assert result.pbpk_scenario_input is not None
    assert result.pbpk_external_import_package is None


def test_integrated_workflow_can_continue_when_all_evidence_is_rejected() -> None:
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="liquid",
            application_method="wipe",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=5.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    incompatible_evidence = ProductUseEvidenceRecord(
        chemical_id="DTXSID123",
        source_name="Mismatched spray dossier",
        source_kind="regulatory_dossier",
        review_status="reviewed",
        product_use_categories=["pesticide"],
        physical_forms=["spray"],
        application_methods=["trigger_spray"],
        region_scopes=["EU"],
        jurisdictions=["EU"],
    )

    result = run_integrated_exposure_workflow(
        RunIntegratedExposureWorkflowInput(
            request=request,
            evidence_records=[incompatible_evidence],
            continue_on_evidence_reject=True,
            export_pbpk_external_import_bundle=False,
            export_pbpk_scenario_input=False,
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.evidence_strategy == "evidence_rejected_source_request_retained"
    assert result.manual_review_required is True
    assert result.effective_request.product_use_profile.product_category == "household_cleaner"
    assert result.scenario.product_use_profile.product_category == "household_cleaner"
    assert any(
        flag.code == "integrated_workflow_evidence_rejected_source_request_retained"
        for flag in result.quality_flags
    )


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
