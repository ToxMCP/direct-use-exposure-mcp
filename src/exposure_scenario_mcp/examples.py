"""Generated example payloads for contracts and tests."""

from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
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
    BuildAggregateExposureScenarioInput,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
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


def _engine() -> ScenarioEngine:
    defaults_registry = DefaultsRegistry.load()
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=defaults_registry)


def build_examples() -> dict[str, dict]:
    engine = _engine()
    defaults_registry = DefaultsRegistry.load()

    dermal_request = ExposureScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name="Example Hand Cream",
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=3,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            demographic_tags=["consumer", "general_population"],
            region="EU",
        ),
    )
    dermal_scenario = engine.build(dermal_request)

    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID7020182",
        chemical_name="Example Solvent A",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_name="Example Trigger Spray",
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )
    inhalation_scenario = engine.build(inhalation_request)

    refined_request = dermal_request.model_copy(
        update={
            "product_use_profile": dermal_request.product_use_profile.model_copy(
                update={"retention_factor": 0.65, "transfer_efficiency": 0.8}
            )
        }
    )
    refined_scenario = engine.build(refined_request)

    aggregate_input = BuildAggregateExposureScenarioInput(
        chemical_id="DTXSID7020182",
        label="Example co-use summary",
        component_scenarios=[dermal_scenario, inhalation_scenario],
    )
    aggregate_summary = aggregate_scenarios(aggregate_input, defaults_registry)
    pbpk_input = export_pbpk_input(
        ExportPbpkScenarioInputRequest(
            scenario=dermal_scenario, regimen_name="screening_daily_use"
        ),
        defaults_registry,
    )
    comparison = compare_scenarios(
        CompareExposureScenariosInput(baseline=dermal_scenario, comparison=refined_scenario),
        defaults_registry,
    )
    comp_tox_record = CompToxChemicalRecord(
        chemical_id="DTXSID7020182",
        preferred_name="Example Solvent A",
        casrn="123-45-6",
        product_use_categories=["personal_care", "household_cleaner"],
        physchem_summary={"vapor_pressure_pa": 150.0, "water_solubility_mg_l": 1200.0},
        evidence_sources=["CompTox:mock-record-001"],
    )
    comp_tox_enriched_request = apply_comptox_enrichment(dermal_request, comp_tox_record)
    toxclaw_evidence = build_toxclaw_evidence_envelope(
        dermal_scenario,
        context_of_use="screening_prioritization",
    )
    toxclaw_evidence_bundle = build_toxclaw_evidence_bundle(
        ExportToxClawEvidenceBundleRequest(
            scenario=dermal_scenario,
            case_id="case-example-001",
            report_id="report-example-001",
            context_of_use="screening-brief",
        )
    )
    toxclaw_refinement_bundle = build_toxclaw_refinement_bundle(
        ExportToxClawRefinementBundleRequest(
            baseline=dermal_scenario,
            comparison=refined_scenario,
            case_id="case-example-001",
            report_id="report-example-001",
            workflow_action="scenario_comparison",
        )
    )
    pbpk_compatibility = check_pbpk_compatibility(dermal_scenario)
    pbpk_external_import_package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(
            scenario=dermal_scenario,
            context_of_use="screening-brief",
        )
    )
    tool_result_meta_completed = build_tool_result_meta(
        result_status="completed",
        payload_model=dermal_scenario,
    )
    tool_result_meta_failed = build_tool_result_meta(
        result_status="failed",
        error=ExposureScenarioError(
            code="example_failure",
            message="Illustrative failure for result-status metadata.",
        ),
    )

    return {
        "screening_dermal_request": dermal_request.model_dump(mode="json", by_alias=True),
        "screening_dermal_scenario": dermal_scenario.model_dump(mode="json", by_alias=True),
        "inhalation_request": inhalation_request.model_dump(mode="json", by_alias=True),
        "inhalation_scenario": inhalation_scenario.model_dump(mode="json", by_alias=True),
        "aggregate_summary": aggregate_summary.model_dump(mode="json", by_alias=True),
        "pbpk_input": pbpk_input.model_dump(mode="json", by_alias=True),
        "pbpk_external_import_request": pbpk_external_import_package.request_payload.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_external_import_tool_call": pbpk_external_import_package.tool_call.model_dump(
            mode="json", by_alias=True
        ),
        "toxclaw_pbpk_module_params": pbpk_external_import_package.toxclaw_module_params.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_external_import_package": pbpk_external_import_package.model_dump(
            mode="json", by_alias=True
        ),
        "comparison_record": comparison.model_dump(mode="json", by_alias=True),
        "comp_tox_record": comp_tox_record.model_dump(mode="json", by_alias=True),
        "comp_tox_enriched_request": comp_tox_enriched_request.model_dump(
            mode="json", by_alias=True
        ),
        "toxclaw_evidence_envelope": toxclaw_evidence.model_dump(mode="json", by_alias=True),
        "toxclaw_evidence_bundle": toxclaw_evidence_bundle.model_dump(
            mode="json", by_alias=True
        ),
        "toxclaw_refinement_bundle": toxclaw_refinement_bundle.model_dump(
            mode="json", by_alias=True
        ),
        "pbpk_compatibility_report": pbpk_compatibility.model_dump(mode="json", by_alias=True),
        "tool_result_meta_completed": tool_result_meta_completed,
        "tool_result_meta_failed": tool_result_meta_failed,
    }
