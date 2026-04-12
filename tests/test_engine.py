from __future__ import annotations

from copy import deepcopy

import pytest

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    AggregationMode,
    AirflowDirectionality,
    ApplicabilityStatus,
    BuildAggregateExposureScenarioInput,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    BuildParameterBoundsInput,
    BuildProbabilityBoundsFromProfileInput,
    BuildProbabilityBoundsFromScenarioPackageInput,
    CompareExposureScenariosInput,
    DefaultVisibility,
    EnvelopeArchetypeInput,
    EvidenceBasis,
    EvidenceGrade,
    ExportPbpkScenarioInputRequest,
    ExposureScenarioRequest,
    InhalationResidualAirReentryScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParameterBoundInput,
    ParticleSizeRegime,
    PhyschemContext,
    PopulationProfile,
    ProductUseProfile,
    ResidualAirReentryMode,
    Route,
    RouteBioavailabilityAdjustment,
    ScenarioClass,
    TierLevel,
    UncertaintyTier,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import (
    build_inhalation_residual_air_reentry_scenario,
    build_inhalation_tier_1_screening_scenario,
)
from exposure_scenario_mcp.probability_bounds import (
    build_probability_bounds_from_profile,
    build_probability_bounds_from_scenario_package,
)
from exposure_scenario_mcp.probability_profiles import ProbabilityBoundsProfileRegistry
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)
from exposure_scenario_mcp.uncertainty import (
    build_exposure_envelope,
    build_exposure_envelope_from_library,
    build_parameter_bounds_summary,
    enrich_scenario_uncertainty,
)


def build_engine(defaults_registry: DefaultsRegistry | None = None) -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(
        registry=registry,
        defaults_registry=defaults_registry or DefaultsRegistry.load(),
    )


def _registry_with_zero_deposition() -> DefaultsRegistry:
    base = DefaultsRegistry.load()
    payload = deepcopy(base.payload)
    section = payload["inhalation_physical_caps"]["deposition_rate_per_hour"]
    section["global"]["value"] = 0.0
    for group in (
        "physical_form_overrides",
        "application_method_overrides",
        "product_subtype_overrides",
        "particle_size_regime_overrides",
    ):
        for entry in section.get(group, {}).values():
            entry["value"] = 0.0
    return DefaultsRegistry(
        path=base.path,
        location=base.location,
        payload=payload,
        sha256=base.sha256,
    )


def _registry_with_zero_tier1_local_entrainment() -> DefaultsRegistry:
    base = DefaultsRegistry.load()
    payload = deepcopy(base.payload)
    section = payload["inhalation_physical_caps"]["tier1_local_entrainment_rates"]
    section["thermal_plume_rate_m3_per_hour"]["value"] = 0.0
    jet_section = section["spray_jet_rate_m3_per_hour"]
    jet_section["global"]["value"] = 0.0
    for entry in jet_section.get("application_method_overrides", {}).values():
        entry["value"] = 0.0
    return DefaultsRegistry(
        path=base.path,
        location=base.location,
        payload=payload,
        sha256=base.sha256,
    )


def _registry_with_full_pressurized_aerosol_volume_interpretation() -> DefaultsRegistry:
    base = DefaultsRegistry.load()
    payload = deepcopy(base.payload)
    section = payload["conversion_defaults"]["pressurized_aerosol_volume_interpretation_factor"]
    section["global"]["value"] = 1.0
    for entry in section.get("product_category_overrides", {}).values():
        entry["value"] = 1.0
    for entry in section.get("product_subtype_overrides", {}).values():
        entry["value"] = 1.0
    return DefaultsRegistry(
        path=base.path,
        location=base.location,
        payload=payload,
        sha256=base.sha256,
    )


def test_dermal_screening_defaults_and_dose() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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

    scenario = engine.build(request)

    assert scenario.external_dose.unit.value == "mg/kg-day"
    assert scenario.external_dose.value == pytest.approx(1.125, rel=1e-6)
    assert scenario.route_metrics["surface_loading_mg_per_cm2_day"] == pytest.approx(
        0.01578947, rel=1e-6
    )
    assumption_names = {item.name for item in scenario.assumptions}
    assert {"retention_factor", "transfer_efficiency", "body_weight_kg"} <= assumption_names
    assert not any(flag.code == "heuristic_default_source" for flag in scenario.quality_flags)
    retention = next(item for item in scenario.assumptions if item.name == "retention_factor")
    transfer = next(item for item in scenario.assumptions if item.name == "transfer_efficiency")
    assert retention.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert retention.governance.evidence_grade == EvidenceGrade.GRADE_2
    assert retention.governance.default_visibility == DefaultVisibility.SILENT_TRACEABLE
    assert retention.governance.applicability_status == ApplicabilityStatus.IN_DOMAIN
    assert retention.governance.applicability_domain["retention_type"] == "leave_on"
    assert transfer.value == pytest.approx(1.0, rel=1e-6)
    assert transfer.source.source_id == "rivm_cosmetics_hand_cream_direct_application_defaults_2025"
    assert transfer.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert transfer.governance.evidence_grade == EvidenceGrade.GRADE_3
    assert transfer.governance.default_visibility == DefaultVisibility.SILENT_TRACEABLE
    assert transfer.governance.applicability_status == ApplicabilityStatus.IN_DOMAIN
    assert scenario.tier_semantics.tier_claimed == TierLevel.TIER_0
    assert scenario.tier_semantics.tier_earned == TierLevel.TIER_0
    assert scenario.tier_semantics.assumption_checks_passed is True
    assert scenario.uncertainty_tier == UncertaintyTier.TIER_A
    assert scenario.validation_summary is not None
    assert scenario.validation_summary.validation_status.value == "benchmark_regression"
    assert scenario.validation_summary.evidence_readiness.value == "external_partial"
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "dermal_validation_partial_only" in scenario.validation_summary.validation_gap_ids
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert scenario.sensitivity_ranking[0].parameter_name in {
        "body_weight_kg",
        "concentration_fraction",
        "retention_factor",
        "transfer_efficiency",
        "use_amount_per_event",
        "use_events_per_day",
    }
    assert any(
        item.entry_id == "dependency-handling-required" for item in scenario.uncertainty_register
    )
    assert scenario.validation_summary.executed_validation_checks == []


def test_face_cream_sccs_guidance_alignment() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=0.71962617,
            use_amount_unit="g",
            use_events_per_day=2.14,
            transfer_efficiency=1.0,
            retention_factor=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=63.79453,
            exposed_surface_area_cm2=565.0,
        ),
    )

    scenario = engine.build(request)

    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(
        30.80000008, rel=1e-6
    )
    assert scenario.route_metrics["surface_loading_mg_per_cm2_day"] == pytest.approx(
        0.05451327, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.48280001, rel=1e-6)
    assert scenario.validation_summary.executed_validation_checks == []


def test_rinse_off_retention_uses_sccs_guidance_source() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="gel",
            application_method="hand_application",
            retention_type="rinse_off",
            concentration_fraction=0.02,
            use_amount_per_event=2.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    retention = next(item for item in scenario.assumptions if item.name == "retention_factor")

    assert retention.value == pytest.approx(0.01, rel=1e-6)
    assert retention.source.source_id == "sccs_notes_of_guidance_12th_revision_2023"
    assert retention.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert retention.governance.evidence_grade == EvidenceGrade.GRADE_4


def test_hand_scale_cream_application_executes_validation_check() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.05,
            use_amount_per_event=0.85,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            exposed_surface_area_cm2=860.0,
        ),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    assert len(checks) == 1
    assert checks[0].check_id == "hand_cream_application_loading_2012"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.98837209, rel=1e-6)
    assert checks[0].reference_dataset_id == "skin_protection_cream_dose_per_area_2012"


def test_generic_hand_application_uses_route_semantic_transfer_default() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="generic_topical",
            physical_form="gel",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.1,
            use_amount_per_event=1.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    transfer = next(item for item in scenario.assumptions if item.name == "transfer_efficiency")

    assert transfer.value == pytest.approx(1.0, rel=1e-6)
    assert transfer.source.source_id == "screening_route_semantics_defaults_v1"
    assert transfer.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert transfer.governance.evidence_grade == EvidenceGrade.GRADE_2
    assert transfer.governance.default_visibility == DefaultVisibility.SILENT_TRACEABLE
    assert transfer.governance.applicability_status == ApplicabilityStatus.IN_DOMAIN
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(100.0, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(1.25, rel=1e-6)


def test_inhalation_screening_defaults_and_dose() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        ),
    )

    scenario = engine.build(request)

    assert scenario.external_dose.value == pytest.approx(0.02443285, rel=1e-6)
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        3.69207438, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        1.66143347, rel=1e-6
    )
    assert scenario.route_metrics["extrathoracic_swallow_fraction"] == pytest.approx(
        0.25, rel=1e-6
    )
    assert scenario.route_metrics["swallowed_extrathoracic_mass_mg_per_day"] == pytest.approx(
        0.41535837, rel=1e-6
    )
    assert scenario.route_metrics["lower_respiratory_inhaled_mass_mg_per_day"] == pytest.approx(
        1.2460751, rel=1e-6
    )
    assert scenario.route_metrics["deposition_rate_per_hour"] == pytest.approx(0.5, rel=1e-6)
    assert scenario.route_metrics["total_loss_rate_per_hour"] == pytest.approx(1.1, rel=1e-6)
    assert scenario.route_metrics["room_air_decay_half_life_hours"] == pytest.approx(
        0.6301338, rel=1e-6
    )
    assert scenario.route_metrics["saturation_cap_mg_per_m3"] is None
    assert scenario.route_metrics["saturation_cap_applied"] is False
    assert any(item.code == "breathing_zone_not_modeled" for item in scenario.limitations)
    assert any(item.code == "extrathoracic_oral_handoff_screening" for item in scenario.limitations)
    assert any(item.code == "tier_0_spray_screening" for item in scenario.quality_flags)
    assert scenario.tier_upgrade_advisories[0].target_tier == TierLevel.TIER_1
    assert scenario.tier_upgrade_advisories[0].status.value == "recommended_not_implemented"
    assert scenario.tier_upgrade_advisories[0].guidance_resource == (
        "docs://inhalation-tier-upgrade-guide"
    )
    assert "source_distance_m" in {
        item.field_name for item in scenario.tier_upgrade_advisories[0].required_inputs
    }
    assert "breathing-zone peak concentration" in " ".join(
        scenario.tier_semantics.forbidden_interpretations
    )
    assert scenario.validation_summary is not None
    assert scenario.validation_summary.route_mechanism == "inhalation_well_mixed_spray"
    assert scenario.validation_summary.evidence_readiness.value == "external_partial"
    assert "tier0_spray_external_validation_partial_only" in (
        scenario.validation_summary.validation_gap_ids
    )


def test_inhalation_saturation_cap_clamps_impossible_room_concentration() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID999",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=1.0,
            use_amount_per_event=1000.0,
            use_amount_unit="mL",
            use_events_per_day=1.0,
            room_volume_m3=1.0,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=1.0,
        ),
        physchem_context=PhyschemContext(
            vapor_pressure_mmhg=10.0,
            molecular_weight_g_per_mol=100.0,
        ),
    )

    scenario = engine.build(request)

    assert scenario.route_metrics["saturation_cap_applied"] is True
    assert scenario.route_metrics["saturation_cap_mg_per_m3"] == pytest.approx(
        53781.63753201, rel=1e-6
    )
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        53781.63753201, rel=1e-6
    )
    assert scenario.route_metrics["uncapped_average_air_concentration_mg_per_m3"] == pytest.approx(
        410774.05669097, rel=1e-6
    )
    assert any(flag.code == "saturation_cap_applied" for flag in scenario.quality_flags)
    assert any(
        item.entry_id == "mechanistic-constraint-saturation-cap-active"
        for item in scenario.uncertainty_register
    )


def test_tier0_deposition_lowers_trigger_spray_against_zero_deposition_baseline() -> None:
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        ),
    )

    baseline = build_engine(_registry_with_zero_deposition()).build(request)
    bounded = build_engine().build(request)

    assert baseline.route_metrics["deposition_rate_per_hour"] == pytest.approx(0.0, rel=1e-6)
    assert bounded.route_metrics["deposition_rate_per_hour"] == pytest.approx(0.5, rel=1e-6)
    assert bounded.route_metrics["average_air_concentration_mg_per_m3"] < baseline.route_metrics[
        "average_air_concentration_mg_per_m3"
    ]
    assert bounded.external_dose.value < baseline.external_dose.value


def test_tier1_deposition_is_stronger_for_coarse_than_fine_aerosol() -> None:
    coarse_request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=2.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )
    fine_request = coarse_request.model_copy(
        update={"particle_size_regime": ParticleSizeRegime.FINE_AEROSOL}
    )

    coarse = build_inhalation_tier_1_screening_scenario(coarse_request, DefaultsRegistry.load())
    fine = build_inhalation_tier_1_screening_scenario(fine_request, DefaultsRegistry.load())

    assert coarse.route_metrics["deposition_rate_per_hour"] == pytest.approx(1.0, rel=1e-6)
    assert fine.route_metrics["deposition_rate_per_hour"] == pytest.approx(0.1, rel=1e-6)
    assert coarse.route_metrics["extrathoracic_swallow_fraction"] == pytest.approx(0.4, rel=1e-6)
    assert fine.route_metrics["extrathoracic_swallow_fraction"] == pytest.approx(0.05, rel=1e-6)
    assert coarse.route_metrics["swallowed_extrathoracic_mass_mg_per_day"] > fine.route_metrics[
        "swallowed_extrathoracic_mass_mg_per_day"
    ]
    assert coarse.route_metrics["average_air_concentration_mg_per_m3"] < fine.route_metrics[
        "average_air_concentration_mg_per_m3"
    ]
    assert coarse.external_dose.value < fine.external_dose.value


def test_air_space_insecticide_aerosol_executes_validation_check() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID127",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="air_space_insecticide",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=0.65,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )

    scenario = engine.build(request)
    assert scenario.validation_summary.route_mechanism == "inhalation_well_mixed_spray"
    assert "household_mosquito_aerosol_indoor_air_2001" in (
        scenario.validation_summary.external_dataset_ids
    )
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "air_space_insecticide_aerosol_concentration_2001"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.16357451, rel=1e-6)
    assert checks[0].reference_dataset_id == "household_mosquito_aerosol_indoor_air_2001"
    assert any(
        item.entry_id == "limitation-breathing_zone_not_modeled"
        for item in scenario.uncertainty_register
    )


def test_air_space_insecticide_aerosol_executes_0p75h_time_series_check() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID127",
        chemical_name="Benchmark Pyrethroid A",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="air_space_insecticide",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=0.5059327,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=58.0,
            air_exchange_rate_per_hour=0.96,
            exposure_duration_hours=0.75,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "air_space_insecticide_aerosol_0p75h_concentration_2001"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.16605849, rel=1e-6)
    assert scenario.route_metrics["air_concentration_at_event_end_mg_per_m3"] == pytest.approx(
        0.16605849, rel=1e-6
    )


def test_air_space_insecticide_aerosol_executes_6h_time_series_check() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID127",
        chemical_name="Benchmark Pyrethroid A",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="air_space_insecticide",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=0.5059327,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=58.0,
            air_exchange_rate_per_hour=0.96,
            exposure_duration_hours=6.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "air_space_insecticide_aerosol_6h_concentration_2001"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.00091837, rel=1e-6)
    assert scenario.route_metrics["air_concentration_at_event_end_mg_per_m3"] == pytest.approx(
        0.00091837, rel=1e-6
    )


def test_household_cleaner_trigger_spray_executes_airborne_fraction_check() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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

    scenario = engine.build(request)
    assert "cleaning_trigger_spray_airborne_mass_fraction_2019" in (
        scenario.validation_summary.external_dataset_ids
    )
    assert "spray_cleaning_disinfection_decay_half_life_2023" in (
        scenario.validation_summary.external_dataset_ids
    )
    checks = scenario.validation_summary.executed_validation_checks
    check_ids = {item.check_id for item in checks}
    assert {
        "cleaning_trigger_spray_airborne_fraction_2019",
        "trigger_spray_aerosol_decay_half_life_2023",
    } <= check_ids
    airborne = next(
        item for item in checks if item.check_id == "cleaning_trigger_spray_airborne_fraction_2019"
    )
    assert airborne.status.value == "pass"
    assert airborne.observed_value == pytest.approx(0.2, rel=1e-6)
    assert airborne.reference_dataset_id == "cleaning_trigger_spray_airborne_mass_fraction_2019"
    half_life = next(
        item for item in checks if item.check_id == "trigger_spray_aerosol_decay_half_life_2023"
    )
    assert half_life.status.value == "pass"
    assert half_life.observed_value == pytest.approx(0.27725887, rel=1e-6)
    assert half_life.reference_dataset_id == "spray_cleaning_disinfection_decay_half_life_2023"


def test_tier1_disinfectant_trigger_spray_executes_external_dose_check() -> None:
    engine = build_engine()
    request = InhalationTier1ScenarioRequest(
        chemical_id="PM_DISINFECTANT_SPRAY_2015",
        chemical_name="Consumer Disinfectant Spray Particulate",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="disinfectant",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.004,
            use_amount_per_event=5.0,
            use_amount_unit="mL",
            use_events_per_day=1.0,
            room_volume_m3=40.0,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0 / 60.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=1.0,
            region="EU",
        ),
        assumption_overrides={},
        source_distance_m=0.35,
        spray_duration_seconds=60.0,
        near_field_volume_m3=3.0,
        airflow_directionality="cross_draft",
        particle_size_regime="coarse_spray",
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load()),
    )
    assert "consumer_disinfectant_trigger_spray_inhalation_2015" in (
        scenario.validation_summary.external_dataset_ids
    )
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "consumer_disinfectant_trigger_spray_inhaled_dose_2015"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.00107475, rel=1e-6)
    assert checks[0].reference_dataset_id == "consumer_disinfectant_trigger_spray_inhalation_2015"


def test_medicinal_liquid_direct_oral_executes_delivered_dose_check() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID126",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="medicinal_liquid",
            physical_form="liquid",
            application_method="direct_oral",
            retention_type="leave_on",
            concentration_fraction=0.125,
            use_amount_per_event=9,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="child",
            body_weight_kg=15,
            region="global",
        ),
    )

    scenario = engine.build(request)

    assert "vigabatrin_ready_to_use_dosing_accuracy_2025" in (
        scenario.validation_summary.external_dataset_ids
    )
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "medicinal_liquid_direct_oral_delivered_mass_2025"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(1125.0, rel=1e-6)
    assert checks[0].reference_dataset_id == "vigabatrin_ready_to_use_dosing_accuracy_2025"


def test_indoor_surface_insecticide_trigger_spray_does_not_borrow_reentry_candidates() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
    )

    scenario = engine.build(request)

    assert scenario.validation_summary.route_mechanism == "inhalation_well_mixed_spray"
    assert scenario.validation_summary.evidence_readiness.value == "benchmark_only"
    assert "household_mosquito_aerosol_indoor_air_2001" not in (
        scenario.validation_summary.external_dataset_ids
    )
    assert "chlorpyrifos_broadcast_residential_air_1990" not in (
        scenario.validation_summary.external_dataset_ids
    )
    assert "diazinon_office_postapplication_air_1990" not in (
        scenario.validation_summary.external_dataset_ids
    )
    assert "diazinon_indoor_air_monitoring_home_use_2008" not in (
        scenario.validation_summary.external_dataset_ids
    )
    assert scenario.validation_summary.executed_validation_checks == []


def test_residual_air_reentry_executes_chlorpyrifos_anchor_check() -> None:
    engine = build_engine()
    request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID9020412",
        chemical_name="Chlorpyrifos",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=4.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        air_concentration_at_reentry_start_mg_per_m3=0.08,
        additional_decay_rate_per_hour=0.03,
        post_application_delay_hours=4.0,
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_residual_air_reentry_scenario(
            request,
            DefaultsRegistry.load(),
        ),
    )

    assert scenario.validation_summary.route_mechanism == "inhalation_residual_air_reentry"
    assert scenario.validation_summary.validation_status.value == "benchmark_regression"
    assert scenario.validation_summary.evidence_readiness.value == (
        "benchmark_plus_external_candidates"
    )
    assert {
        "chlorpyrifos_broadcast_residential_air_1990",
        "diazinon_office_postapplication_air_1990",
        "diazinon_indoor_air_monitoring_home_use_2008",
    } <= set(scenario.validation_summary.external_dataset_ids)
    assert "residual_air_reentry_validation_narrow_anchor_only" in (
        scenario.validation_summary.validation_gap_ids
    )
    assert len(scenario.validation_summary.executed_validation_checks) == 1
    assert scenario.validation_summary.executed_validation_checks[0].check_id == (
        "chlorpyrifos_residual_air_reentry_start_concentration_1990"
    )
    assert scenario.validation_summary.executed_validation_checks[0].status.value == "pass"
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        0.03298487,
        rel=1e-6,
    )
    assert scenario.route_metrics["air_concentration_at_reentry_end_mg_per_m3"] == pytest.approx(
        0.00941239,
        rel=1e-6,
    )
    assert scenario.external_dose.value == pytest.approx(0.00136887, rel=1e-6)
    assert any(item.code == "treated_surface_emission_not_modeled" for item in scenario.limitations)


def test_residual_air_reentry_executes_sparse_time_series_check_at_24_hours() -> None:
    engine = build_engine()
    request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID9020412",
        chemical_name="Chlorpyrifos",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.02,
            exposure_duration_hours=20.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        air_concentration_at_reentry_start_mg_per_m3=0.08,
        additional_decay_rate_per_hour=0.02904146,
        post_application_delay_hours=4.0,
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_residual_air_reentry_scenario(
            request,
            DefaultsRegistry.load(),
        ),
    )

    check_ids = {item.check_id for item in scenario.validation_summary.executed_validation_checks}
    assert {
        "chlorpyrifos_residual_air_reentry_start_concentration_1990",
        "chlorpyrifos_residual_air_reentry_24h_concentration_1990",
    } <= check_ids
    checks_by_id = {
        item.check_id: item for item in scenario.validation_summary.executed_validation_checks
    }
    assert (
        checks_by_id["chlorpyrifos_residual_air_reentry_24h_concentration_1990"].status.value
        == "pass"
    )
    assert scenario.route_metrics["air_concentration_at_reentry_end_mg_per_m3"] == pytest.approx(
        0.02714512,
        rel=1e-6,
    )
    assert scenario.external_dose.value == pytest.approx(0.0101472, rel=1e-6)


def test_native_residual_air_reentry_derives_surface_emission_profile() -> None:
    engine = build_engine()
    request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID9020412",
        chemical_name="Chlorpyrifos",
        route=Route.INHALATION,
        reentryMode=ResidualAirReentryMode.NATIVE_TREATED_SURFACE_REENTRY,
        physchemContext=PhyschemContext(
            vaporPressureMmhg=0.02,
            molecularWeightGPerMol=350.59,
            logKow=4.7,
            waterSolubilityMgPerL=1.4,
        ),
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.005,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=4.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        additionalDecayRatePerHour=0.03,
        postApplicationDelayHours=4.0,
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_residual_air_reentry_scenario(request, DefaultsRegistry.load()),
    )

    assert scenario.route_metrics["reentry_mode"] == "native_treated_surface_reentry"
    assert scenario.route_metrics["treated_surface_chemical_mass_mg_initial"] > 0.0
    assert (
        scenario.route_metrics["treated_surface_chemical_mass_mg_at_reentry_start"]
        < scenario.route_metrics["treated_surface_chemical_mass_mg_initial"]
    )
    assert scenario.route_metrics["surface_emission_rate_per_hour"] > 0.0
    assert scenario.route_metrics["air_concentration_at_reentry_start_mg_per_m3"] > 0.0
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] > 0.0
    assert scenario.external_dose.value > 0.0
    assert any(
        item.code == "native_treated_surface_emission_bounded" for item in scenario.limitations
    )
    assert not any(
        item.code == "treated_surface_emission_not_modeled" for item in scenario.limitations
    )
    assert not any(item.code == "reentry_air_anchor_required" for item in scenario.limitations)


def test_residual_air_reentry_executes_diazinon_time_series_checks() -> None:
    engine = build_engine()
    request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID9020407",
        chemical_name="Diazinon",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.01,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.01,
            exposure_duration_hours=24.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
        ),
        air_concentration_at_reentry_start_mg_per_m3=0.125,
        additional_decay_rate_per_hour=0.02575091,
        post_application_delay_hours=24.0,
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_residual_air_reentry_scenario(
            request,
            DefaultsRegistry.load(),
        ),
    )

    check_ids = {item.check_id for item in scenario.validation_summary.executed_validation_checks}
    assert {
        "diazinon_residual_air_reentry_24h_concentration_1990",
        "diazinon_residual_air_reentry_48h_concentration_1990",
    } <= check_ids
    assert "chlorpyrifos_residual_air_reentry_start_concentration_1990" not in check_ids
    assert scenario.route_metrics["air_concentration_at_reentry_end_mg_per_m3"] == pytest.approx(
        0.04700678,
        rel=1e-6,
    )
    assert scenario.external_dose.value == pytest.approx(0.01985673, rel=1e-6)


def test_residual_air_reentry_executes_diazinon_home_use_native_anchor_check() -> None:
    engine = build_engine()
    request = InhalationResidualAirReentryScenarioRequest(
        chemical_id="DTXSID9020407",
        chemical_name="Diazinon",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="residual_air_reentry",
            retention_type="surface_contact",
            concentration_fraction=0.01,
            use_amount_per_event=20,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=30,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=4.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            inhalation_rate_m3_per_hour=0.83,
            region="EU",
            demographic_tags=[
                "residential_reentry",
                "home_use_monitoring",
                "native_treated_surface_mode",
            ],
        ),
        reentry_mode=ResidualAirReentryMode.NATIVE_TREATED_SURFACE_REENTRY,
        treated_surface_chemical_mass_mg=12.35,
        surface_emission_rate_per_hour=0.04,
        additional_decay_rate_per_hour=0.02,
        post_application_delay_hours=24.0,
    )

    scenario = enrich_scenario_uncertainty(
        engine,
        build_inhalation_residual_air_reentry_scenario(
            request,
            DefaultsRegistry.load(),
        ),
    )

    check_ids = {item.check_id for item in scenario.validation_summary.executed_validation_checks}
    assert "diazinon_home_use_residual_air_concentration_2008" in check_ids
    assert any(
        item.check_id == "diazinon_home_use_residual_air_concentration_2008"
        and item.status.value == "pass"
        for item in scenario.validation_summary.executed_validation_checks
    )
    assert any(
        item.entry_id == "mechanistic-constraint-native-treated-surface-source"
        for item in scenario.uncertainty_register
    )
    assert scenario.route_metrics["air_concentration_at_reentry_start_mg_per_m3"] == pytest.approx(
        0.01299982,
        rel=1e-6,
    )


def test_inhalation_tier_1_nf_ff_screening_builds_scenario() -> None:
    engine = build_engine()
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=2.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.external_dose.value == pytest.approx(0.05899338, rel=1e-6)
    assert scenario.tier_semantics.tier_claimed == TierLevel.TIER_1
    assert scenario.route_metrics["far_field_average_air_concentration_mg_per_m3"] == pytest.approx(
        2.48598349, rel=1e-6
    )
    assert scenario.route_metrics[
        "near_field_active_spray_concentration_mg_per_m3"
    ] == pytest.approx(1448.91455492, rel=1e-6)
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        8.91455492, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        4.01154971, rel=1e-6
    )
    assert scenario.route_metrics["interzonal_mixing_rate_m3_per_hour"] == pytest.approx(
        68.0, rel=1e-6
    )
    assert scenario.route_metrics["tier1_product_profile_id"] == (
        "household_cleaner_trigger_spray_tier1"
    )
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "aligned"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 0
    assert any(item.code == "near_field_exchange_screening" for item in scenario.limitations)
    assert any(item.code == "tier_1_nf_ff_screening" for item in scenario.quality_flags)
    assert not any(
        item.code == "tier1_profile_anchor_divergence" for item in scenario.quality_flags
    )
    assumptions = {item.name: item for item in scenario.assumptions}
    assert assumptions["near_field_exchange_turnover_per_hour"].value == pytest.approx(
        32.0, rel=1e-6
    )
    assert assumptions["near_field_exchange_turnover_per_hour"].source.source_id == (
        "benchmark_tier1_nf_ff_parameter_pack_v1"
    )
    assert assumptions["particle_persistence_factor"].value == pytest.approx(0.85, rel=1e-6)
    assert assumptions["particle_persistence_factor"].source.source_id == (
        "benchmark_tier1_nf_ff_parameter_pack_v1"
    )
    assert any(
        "household_cleaner_trigger_spray_tier1" in note
        for note in scenario.interpretation_notes
    )

    enriched = enrich_scenario_uncertainty(engine, scenario)
    assert enriched.validation_summary is not None
    assert enriched.validation_summary.route_mechanism == "inhalation_near_field_far_field"
    assert enriched.validation_summary.highest_supported_uncertainty_tier == UncertaintyTier.TIER_C
    assert "tier1_nf_ff_external_validation_partial_only" in (
        enriched.validation_summary.validation_gap_ids
    )
    assert any(
        item.dependency_id == "near-field-geometry-cluster"
        for item in enriched.dependency_metadata
    )
    assert any(item.parameter_name == "source_distance_m" for item in enriched.sensitivity_ranking)


def test_inhalation_tier_1_applies_local_entrainment_floor_when_static_mixing_is_weak() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=0.5,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=0.5,
        airflow_directionality=AirflowDirectionality.QUIESCENT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )

    baseline = build_inhalation_tier_1_screening_scenario(
        request,
        _registry_with_zero_tier1_local_entrainment(),
    )
    bounded = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())
    enriched = enrich_scenario_uncertainty(build_engine(), bounded)

    assert bounded.route_metrics["static_interzonal_mixing_rate_m3_per_hour"] == pytest.approx(
        10.25, rel=1e-6
    )
    assert bounded.route_metrics["thermal_plume_rate_m3_per_hour"] == pytest.approx(
        36.0, rel=1e-6
    )
    assert bounded.route_metrics["spray_jet_rate_m3_per_hour"] == pytest.approx(
        8.0, rel=1e-6
    )
    assert bounded.route_metrics["local_entrainment_rate_m3_per_hour"] == pytest.approx(
        44.0, rel=1e-6
    )
    assert bounded.route_metrics["interzonal_mixing_rate_m3_per_hour"] == pytest.approx(
        44.0, rel=1e-6
    )
    assert bounded.route_metrics["interzonal_mixing_floor_applied"] is True
    assert (
        bounded.route_metrics["near_field_active_spray_concentration_mg_per_m3"]
        < baseline.route_metrics["near_field_active_spray_concentration_mg_per_m3"]
    )
    assert bounded.external_dose.value < baseline.external_dose.value
    assert any(
        item.code == "tier1_local_entrainment_floor_screening"
        for item in bounded.limitations
    )
    assert any(
        item.entry_id == "mechanistic-constraint-tier1-local-entrainment-floor"
        for item in enriched.uncertainty_register
    )


def test_inhalation_tier_1_matches_personal_care_pump_profile() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="spray",
            application_method="pump_spray",
            retention_type="surface_contact",
            concentration_fraction=0.03,
            use_amount_per_event=1.5,
            use_amount_unit="mL",
            use_events_per_day=2,
            room_volume_m3=18,
            exposure_duration_hours=0.25,
            air_exchange_rate_per_hour=1.5,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.8,
            region="EU",
        ),
        source_distance_m=0.28,
        spray_duration_seconds=5.0,
        near_field_volume_m3=1.7,
        airflow_directionality=AirflowDirectionality.SOURCE_TO_BREATHING_ZONE,
        particle_size_regime=ParticleSizeRegime.MIXED_SPRAY,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.route_metrics["tier1_product_profile_id"] == "personal_care_pump_spray_tier1"
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "aligned"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 0
    assert any("personal_care_pump_spray_tier1" in note for note in scenario.interpretation_notes)


def test_inhalation_tier_1_warns_when_inputs_diverge_from_profile_anchor() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=2.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.7,
        spray_duration_seconds=18.0,
        near_field_volume_m3=3.2,
        airflow_directionality=AirflowDirectionality.GENERAL_ROOM_MIXING,
        particle_size_regime=ParticleSizeRegime.MIXED_SPRAY,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.route_metrics["tier1_product_profile_id"] == (
        "household_cleaner_trigger_spray_tier1"
    )
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "divergent"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 5
    divergence_flag = next(
        item for item in scenario.quality_flags if item.code == "tier1_profile_anchor_divergence"
    )
    assert divergence_flag.severity.value == "warning"
    assert "airflow_directionality=general_room_mixing" in divergence_flag.message
    assert "particle_size_regime=mixed_spray" in divergence_flag.message
    assert any(
        "Tier 1 profile alignment warning:" in note for note in scenario.interpretation_notes
    )


def test_eu_inhalation_room_defaults_use_regional_source() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )

    scenario = engine.build(request)
    air_exchange = next(
        item for item in scenario.assumptions if item.name == "air_exchange_rate_per_hour"
    )

    assert air_exchange.value == pytest.approx(2.0, rel=1e-6)
    assert air_exchange.source.source_id == "echa_consumer_inhalation_room_defaults"


def test_global_inhalation_room_defaults_split_room_and_duration_sources() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="global",
        ),
    )

    scenario = engine.build(request)
    assumptions = {item.name: item for item in scenario.assumptions}

    assert assumptions["room_volume_m3"].value == pytest.approx(20.0, rel=1e-6)
    assert assumptions["room_volume_m3"].source.source_id == (
        "rivm_general_fact_sheet_unspecified_room_defaults_2014"
    )
    assert assumptions["air_exchange_rate_per_hour"].value == pytest.approx(0.6, rel=1e-6)
    assert assumptions["air_exchange_rate_per_hour"].source.source_id == (
        "rivm_general_fact_sheet_unspecified_room_defaults_2014"
    )
    assert assumptions["exposure_duration_hours"].value == pytest.approx(0.5, rel=1e-6)
    assert assumptions["exposure_duration_hours"].source.source_id == (
        "heuristic_time_limited_release_duration_defaults_v1"
    )
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        4.61509298, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.03054106, rel=1e-6)


def test_disinfectant_trigger_spray_uses_consexpo_airborne_fraction_branch() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="disinfectant",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="global",
        ),
    )

    scenario = engine.build(request)
    aerosolized_fraction = next(
        item for item in scenario.assumptions if item.name == "aerosolized_fraction"
    )

    assert aerosolized_fraction.value == pytest.approx(0.2, rel=1e-6)
    assert aerosolized_fraction.source.source_id == (
        "rivm_disinfectant_trigger_spray_airborne_fraction_defaults_2006"
    )


def test_pesticide_trigger_spray_uses_explicit_consexpo_bridge_branch() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="global",
        ),
    )

    scenario = engine.build(request)
    assumptions = {item.name: item for item in scenario.assumptions}

    assert assumptions["aerosolized_fraction"].value == pytest.approx(0.15, rel=1e-6)
    assert assumptions["aerosolized_fraction"].source.source_id == (
        "heuristic_consexpo_pest_control_trigger_spray_airborne_fraction_bridge_2026"
    )
    assert assumptions["aerosolized_fraction"].governance.applicability_domain == {
        "product_category": "pesticide",
        "physical_form": "spray",
        "application_method": "trigger_spray",
    }
    subtype_flag = next(
        item
        for item in scenario.quality_flags
        if item.code == "product_subtype_missing_for_spray_family"
    )
    assert subtype_flag.severity.value == "warning"
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        3.46131973, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.02290579, rel=1e-6)


def test_pesticide_trigger_spray_subtype_uses_subtype_branch_without_gap_warning() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="global",
        ),
    )

    scenario = engine.build(request)
    assumptions = {item.name: item for item in scenario.assumptions}

    assert assumptions["aerosolized_fraction"].value == pytest.approx(0.15, rel=1e-6)
    assert assumptions["aerosolized_fraction"].governance.applicability_domain == {
        "product_category": "pesticide",
        "product_subtype": "indoor_surface_insecticide",
        "physical_form": "spray",
        "application_method": "trigger_spray",
    }
    assert not any(
        item.code == "product_subtype_missing_for_spray_family"
        for item in scenario.quality_flags
    )


def test_air_space_pesticide_aerosol_subtype_uses_consexpo_branches() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="air_space_insecticide",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
    )

    scenario = engine.build(request)
    assumptions = {item.name: item for item in scenario.assumptions}

    assert assumptions["density_g_per_ml"].value == pytest.approx(0.8, rel=1e-6)
    assert assumptions["density_g_per_ml"].source.source_id == (
        "heuristic_consexpo_pest_control_aerosol_density_bridge_2026"
    )
    assert assumptions["pressurized_aerosol_volume_interpretation_factor"].value == pytest.approx(
        1.0, rel=1e-6
    )
    assert assumptions["aerosolized_fraction"].value == pytest.approx(1.0, rel=1e-6)
    assert assumptions["aerosolized_fraction"].source.source_id == (
        "heuristic_consexpo_pest_control_aerosol_airborne_fraction_bridge_2026"
    )
    assert assumptions["room_volume_m3"].value == pytest.approx(58.0, rel=1e-6)
    assert assumptions["air_exchange_rate_per_hour"].value == pytest.approx(0.6, rel=1e-6)
    assert assumptions["exposure_duration_hours"].value == pytest.approx(4.0, rel=1e-6)
    assert assumptions["room_volume_m3"].source.source_id == (
        "heuristic_consexpo_pest_control_air_space_room_defaults_bridge_2026"
    )
    assert assumptions["air_exchange_rate_per_hour"].source.source_id == (
        "heuristic_consexpo_pest_control_air_space_room_defaults_bridge_2026"
    )
    assert assumptions["exposure_duration_hours"].source.source_id == (
        "heuristic_consexpo_pest_control_air_space_room_defaults_bridge_2026"
    )
    assert assumptions["aerosolized_fraction"].governance.applicability_domain == {
        "product_category": "pesticide",
        "product_subtype": "air_space_insecticide",
        "physical_form": "spray",
        "application_method": "aerosol_spray",
    }
    assert not any(
        item.code == "product_subtype_missing_for_spray_family"
        for item in scenario.quality_flags
    )
    assert not any(
        item.code == "pressurized_aerosol_volume_interpretation_defaulted"
        for item in scenario.quality_flags
    )
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        3.01983709, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.15987373, rel=1e-6)


def test_generic_volumetric_aerosol_spray_applies_pressurized_interpretation_factor() -> None:
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="general_consumer",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.001,
            use_amount_per_event=10.0,
            use_amount_unit="mL",
            use_events_per_day=1.0,
            room_volume_m3=20.0,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=1.0,
        ),
    )

    baseline_engine = build_engine(_registry_with_full_pressurized_aerosol_volume_interpretation())
    constrained_engine = build_engine()

    baseline = baseline_engine.build(request)
    constrained = constrained_engine.build(request)
    assumptions = {item.name: item for item in constrained.assumptions}

    assert assumptions["pressurized_aerosol_volume_interpretation_factor"].value == pytest.approx(
        0.35, rel=1e-6
    )
    assert assumptions["pressurized_aerosol_volume_interpretation_factor"].source.source_id == (
        "pressurized_aerosol_volume_interpretation_heuristics_2026"
    )
    assert constrained.external_dose.value == pytest.approx(
        baseline.external_dose.value * 0.35,
        abs=1e-8,
    )
    assert constrained.route_metrics["released_mass_mg_per_event"] == pytest.approx(
        baseline.route_metrics["released_mass_mg_per_event"] * 0.35,
        abs=1e-8,
    )
    assert any(
        item.code == "pressurized_aerosol_volume_interpretation_defaulted"
        for item in constrained.quality_flags
    )


def test_personal_care_deodorant_aerosol_uses_subtype_pressurized_override() -> None:
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            product_subtype="deodorant_spray",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.001,
            use_amount_per_event=10.0,
            use_amount_unit="mL",
            use_events_per_day=1.0,
            room_volume_m3=20.0,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=1.0,
        ),
    )

    baseline_engine = build_engine(_registry_with_full_pressurized_aerosol_volume_interpretation())
    constrained_engine = build_engine()

    baseline = baseline_engine.build(request)
    constrained = constrained_engine.build(request)
    assumptions = {item.name: item for item in constrained.assumptions}

    assert assumptions["pressurized_aerosol_volume_interpretation_factor"].value == pytest.approx(
        0.5, rel=1e-6
    )
    assert assumptions["pressurized_aerosol_volume_interpretation_factor"].source.source_id == (
        "pressurized_aerosol_volume_interpretation_heuristics_2026"
    )
    assert constrained.external_dose.value == pytest.approx(
        baseline.external_dose.value * 0.5,
        abs=1e-8,
    )
    assert constrained.route_metrics["released_mass_mg_per_event"] == pytest.approx(
        baseline.route_metrics["released_mass_mg_per_event"] * 0.5,
        abs=1e-8,
    )
    assert any(
        item.code == "pressurized_aerosol_volume_interpretation_defaulted"
        for item in constrained.quality_flags
    )


def test_inhalation_tier_1_matches_pesticide_subtype_profile() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="indoor_surface_insecticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=20,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=0.6,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=240.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.route_metrics["tier1_product_profile_id"] == (
        "pest_control_indoor_surface_trigger_spray_tier1"
    )
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "aligned"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 0
    assert any(
        "pest_control_indoor_surface_trigger_spray_tier1" in note
        for note in scenario.interpretation_notes
    )


def test_inhalation_tier_1_matches_targeted_spot_pesticide_profile() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="targeted_spot_insecticide",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=20,
            exposure_duration_hours=0.5,
            air_exchange_rate_per_hour=0.6,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=360.0,
        near_field_volume_m3=2.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.route_metrics["tier1_product_profile_id"] == (
        "pest_control_targeted_spot_trigger_spray_tier1"
    )
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "aligned"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 0


def test_inhalation_tier_1_matches_air_space_pesticide_profile() -> None:
    request = InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="pesticide",
            product_subtype="air_space_insecticide",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=58,
            exposure_duration_hours=4.0,
            air_exchange_rate_per_hour=0.6,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.6,
        spray_duration_seconds=20.0,
        near_field_volume_m3=3.0,
        airflow_directionality=AirflowDirectionality.GENERAL_ROOM_MIXING,
        particle_size_regime=ParticleSizeRegime.FINE_AEROSOL,
    )

    scenario = build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert scenario.route_metrics["tier1_product_profile_id"] == (
        "pest_control_air_space_aerosol_tier1"
    )
    assert scenario.route_metrics["tier1_profile_alignment_status"] == "aligned"
    assert scenario.route_metrics["tier1_profile_divergence_count"] == 0


def test_volume_based_cream_uses_physical_form_density_override() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.05,
            use_amount_per_event=2,
            use_amount_unit="mL",
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    density = next(item for item in scenario.assumptions if item.name == "density_g_per_ml")

    assert density.value == pytest.approx(0.95, rel=1e-6)
    assert density.source.source_id == "heuristic_density_defaults_v1"
    assert density.governance.applicability_domain["physical_form"] == "cream"
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(190.0, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(2.375, rel=1e-6)


def test_household_cleaner_wipe_uses_product_category_transfer_override() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="wipe",
            application_method="wipe",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=5,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    retention_factor = next(
        item for item in scenario.assumptions if item.name == "retention_factor"
    )
    transfer_efficiency = next(
        item for item in scenario.assumptions if item.name == "transfer_efficiency"
    )

    assert retention_factor.value == pytest.approx(0.2, rel=1e-6)
    assert (
        retention_factor.source.source_id
        == "rivm_cleaning_surface_contact_retention_defaults_2018"
    )
    assert transfer_efficiency.value == pytest.approx(0.5, rel=1e-6)
    assert transfer_efficiency.source.source_id == "rivm_cleaning_wet_cloth_transfer_defaults_2018"
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(50.0, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(0.625, rel=1e-6)
    assert scenario.validation_summary.route_mechanism == "dermal_secondary_transfer"
    assert scenario.validation_summary.evidence_readiness.value == "external_partial"
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert "rivm_wet_cloth_dermal_contact_loading_2018" in (
        scenario.validation_summary.external_dataset_ids
    )
    checks = scenario.validation_summary.executed_validation_checks
    assert len(checks) == 1
    assert checks[0].check_id == "wet_cloth_contact_mass_2018"
    assert checks[0].status.value == "pass"
    assert checks[0].observed_value == pytest.approx(0.5, rel=1e-6)


def test_dermal_trigger_spray_uses_route_semantic_transfer_default() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=5,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    transfer_efficiency = next(
        item for item in scenario.assumptions if item.name == "transfer_efficiency"
    )

    assert transfer_efficiency.value == pytest.approx(1.0, rel=1e-6)
    assert transfer_efficiency.source.source_id == "screening_route_semantics_defaults_v1"
    assert transfer_efficiency.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert transfer_efficiency.governance.evidence_grade == EvidenceGrade.GRADE_2
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(100.0, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(1.25, rel=1e-6)


def test_household_cleaner_pump_spray_uses_product_category_aerosol_override() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="pump_spray",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=10,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=20,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            inhalation_rate_m3_per_hour=1.0,
        ),
    )

    scenario = engine.build(request)
    aerosolized_fraction = next(
        item for item in scenario.assumptions if item.name == "aerosolized_fraction"
    )

    assert aerosolized_fraction.value == pytest.approx(0.2, rel=1e-6)
    assert aerosolized_fraction.source.source_id == "rivm_cleaning_sprays_airborne_fraction_2018"
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        5.38145026, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        5.38145026, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.07687786, rel=1e-6)


def test_personal_care_pump_spray_uses_curated_rivm_cosmetics_override() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="spray",
            application_method="pump_spray",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=10,
            use_amount_unit="g",
            use_events_per_day=1,
            room_volume_m3=20,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            inhalation_rate_m3_per_hour=1.0,
        ),
    )

    scenario = engine.build(request)
    aerosolized_fraction = next(
        item for item in scenario.assumptions if item.name == "aerosolized_fraction"
    )

    assert aerosolized_fraction.value == pytest.approx(0.2, rel=1e-6)
    assert (
        aerosolized_fraction.source.source_id
        == "rivm_cosmetics_sprays_airborne_fraction_defaults_2025"
    )
    assert aerosolized_fraction.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert aerosolized_fraction.governance.evidence_grade == EvidenceGrade.GRADE_3
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        5.38145026, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        5.38145026, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.07687786, rel=1e-6)


def test_personal_care_aerosol_spray_uses_curated_rivm_cosmetics_override() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="spray",
            application_method="aerosol_spray",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=10,
            use_amount_unit="g",
            use_events_per_day=1,
            room_volume_m3=20,
            air_exchange_rate_per_hour=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=70,
            inhalation_rate_m3_per_hour=1.0,
        ),
    )

    scenario = engine.build(request)
    aerosolized_fraction = next(
        item for item in scenario.assumptions if item.name == "aerosolized_fraction"
    )

    assert aerosolized_fraction.value == pytest.approx(0.9, rel=1e-6)
    assert (
        aerosolized_fraction.source.source_id
        == "rivm_cosmetics_sprays_airborne_fraction_defaults_2025"
    )
    assert aerosolized_fraction.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert aerosolized_fraction.governance.evidence_grade == EvidenceGrade.GRADE_3
    assert scenario.validation_summary.heuristic_assumption_names == []
    assert "heuristic_defaults_active" not in scenario.validation_summary.validation_gap_ids
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        28.09192891, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        28.09192891, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.40131327, rel=1e-6)


def test_aggregate_and_compare_flows() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()

    baseline_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        ),
    )
    comparison_request = baseline_request.model_copy(
        update={
            "product_use_profile": baseline_request.product_use_profile.model_copy(
                update={"retention_factor": 0.65, "transfer_efficiency": 0.8}
            )
        }
    )

    baseline = engine.build(baseline_request)
    inhalation = engine.build(inhalation_request)
    comparison = engine.build(comparison_request)

    aggregate = aggregate_scenarios(
        BuildAggregateExposureScenarioInput(
            chemical_id="DTXSID123",
            label="co-use",
            component_scenarios=[baseline, inhalation],
        ),
        defaults_registry,
    )
    delta = compare_scenarios(
        CompareExposureScenariosInput(baseline=baseline, comparison=comparison),
        defaults_registry,
    )

    assert aggregate.normalized_total_external_dose is not None
    assert aggregate.normalized_total_external_dose.value == pytest.approx(1.14943285, rel=1e-6)
    assert any(item.code == "cross_route_aggregate" for item in aggregate.limitations)
    assert aggregate.uncertainty_tier == UncertaintyTier.TIER_A
    assert aggregate.validation_summary is not None
    assert delta.absolute_delta == pytest.approx(-0.54, rel=1e-6)
    assert delta.percent_delta == pytest.approx(-48.0, rel=1e-6)
    assert any(item.name == "retention_factor" for item in delta.changed_assumptions)


def test_internal_equivalent_aggregate_requires_route_bioavailability_fractions() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    dermal_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    dermal = engine.build(dermal_request)
    inhalation = engine.build(inhalation_request)

    with pytest.raises(ExposureScenarioError):
        aggregate_scenarios(
            BuildAggregateExposureScenarioInput(
                chemical_id="DTXSID123",
                label="co-use-internal-equivalent",
                aggregationMode=AggregationMode.INTERNAL_EQUIVALENT,
                component_scenarios=[dermal, inhalation],
            ),
            defaults_registry,
        )


def test_internal_equivalent_aggregate_builds_adjusted_total() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    dermal_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    dermal = engine.build(dermal_request)
    inhalation = engine.build(inhalation_request)

    aggregate = aggregate_scenarios(
        BuildAggregateExposureScenarioInput(
            chemical_id="DTXSID123",
            label="co-use-internal-equivalent",
            aggregationMode=AggregationMode.INTERNAL_EQUIVALENT,
            routeBioavailabilityAdjustments=[
                RouteBioavailabilityAdjustment(
                    route=Route.DERMAL,
                    bioavailabilityFraction=0.1,
                ),
                RouteBioavailabilityAdjustment(
                    route=Route.INHALATION,
                    bioavailabilityFraction=1.0,
                ),
            ],
            component_scenarios=[dermal, inhalation],
        ),
        defaults_registry,
    )

    assert aggregate.aggregation_mode == AggregationMode.INTERNAL_EQUIVALENT
    assert aggregate.normalized_total_external_dose is not None
    assert aggregate.normalized_total_external_dose.value == pytest.approx(1.13921282, rel=1e-6)
    assert aggregate.internal_equivalent_total_dose is not None
    assert aggregate.internal_equivalent_total_dose.value == pytest.approx(0.12671282, rel=1e-6)
    internal_by_route = {
        item.route.value: item.total_dose.value
        for item in aggregate.per_route_internal_equivalent_totals
    }
    assert internal_by_route["dermal"] == pytest.approx(0.1125, rel=1e-6)
    assert internal_by_route["inhalation"] == pytest.approx(0.01421282, rel=1e-6)
    assert any(
        item.code == "internal_equivalent_bioavailability_user_supplied"
        for item in aggregate.limitations
    )


def test_pbpk_export_can_include_transient_inhalation_profile() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    inhalation_request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    inhalation = engine.build(inhalation_request)

    exported = export_pbpk_input(
        ExportPbpkScenarioInputRequest(
            scenario=inhalation,
            regimen_name="screening_daily_use",
            includeTransientConcentrationProfile=True,
        ),
        defaults_registry,
    )

    assert len(exported.transient_concentration_profile) == 3
    assert exported.transient_concentration_profile[0].time_hours == pytest.approx(0.0, rel=1e-6)
    assert exported.transient_concentration_profile[0].concentration_mg_per_m3 == pytest.approx(
        4.8, rel=1e-6
    )
    assert exported.transient_concentration_profile[1].time_hours == pytest.approx(0.25, rel=1e-6)
    assert exported.transient_concentration_profile[1].concentration_mg_per_m3 == pytest.approx(
        2.73982158, rel=1e-6
    )
    assert exported.transient_concentration_profile[-1].time_hours == pytest.approx(0.5, rel=1e-6)
    assert exported.transient_concentration_profile[-1].concentration_mg_per_m3 == pytest.approx(
        1.37522302, rel=1e-6
    )


def test_deterministic_exposure_envelope_builds_tier_b_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    base_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )

    summary = build_exposure_envelope(
        BuildExposureEnvelopeInput(
            chemical_id="DTXSID123",
            label="Dermal envelope",
            archetypes=[
                EnvelopeArchetypeInput(
                    label="Lower",
                    description="Lower plausible use.",
                    request=base_request.model_copy(
                        update={
                            "product_use_profile": base_request.product_use_profile.model_copy(
                                update={"use_amount_per_event": 1.0, "use_events_per_day": 2}
                            )
                        }
                    ),
                ),
                EnvelopeArchetypeInput(
                    label="Upper",
                    description="Upper plausible use.",
                    request=base_request.model_copy(
                        update={
                            "product_use_profile": base_request.product_use_profile.model_copy(
                                update={"use_amount_per_event": 2.0, "use_events_per_day": 4}
                            )
                        }
                    ),
                ),
            ],
        ),
        engine,
        defaults_registry,
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_B
    assert summary.min_dose.value < summary.max_dose.value
    assert summary.validation_summary is not None
    assert summary.validation_summary.highest_supported_uncertainty_tier == UncertaintyTier.TIER_B
    assert summary.uncertainty_register[0].quantification_status.value == "bounded"
    assert summary.driver_attribution


def test_packaged_archetype_library_builds_tier_b_envelope() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()

    summary = build_exposure_envelope_from_library(
        BuildExposureEnvelopeFromLibraryInput(
            librarySetId="adult_leave_on_hand_cream",
            chemicalId="DTXSID123",
            chemicalName="Example Chemical",
            label="Packaged dermal envelope",
        ),
        engine,
        defaults_registry,
        archetype_library,
        generated_at="2026-03-24T00:00:00+00:00",
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_B
    assert summary.archetype_library_set_id == "adult_leave_on_hand_cream"
    assert summary.archetype_library_version == archetype_library.version
    assert len(summary.archetypes) == 3
    assert all(item.template_id is not None for item in summary.archetypes)
    assert any(
        item.entry_id == "library-governed-archetypes" for item in summary.uncertainty_register
    )
    assert any(
        "packaged archetype-library set" in item for item in summary.interpretation_notes
    )


def test_packaged_archetype_library_builds_tier1_personal_care_envelope() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()

    summary = build_exposure_envelope_from_library(
        BuildExposureEnvelopeFromLibraryInput(
            librarySetId="adult_personal_care_pump_spray_tier1",
            chemicalId="DTXSID123",
            chemicalName="Example Chemical",
            label="Packaged Tier 1 personal-care envelope",
        ),
        engine,
        defaults_registry,
        archetype_library,
        generated_at="2026-03-24T00:00:00+00:00",
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_B
    assert summary.route == Route.INHALATION
    assert summary.scenario_class == ScenarioClass.INHALATION
    assert summary.archetype_library_set_id == "adult_personal_care_pump_spray_tier1"
    assert len(summary.archetypes) == 3
    assert all(
        item.scenario.tier_semantics.tier_claimed == TierLevel.TIER_1 for item in summary.archetypes
    )
    assert all(
        item.scenario.route_metrics["tier1_product_profile_id"] == "personal_care_pump_spray_tier1"
        for item in summary.archetypes
    )
    assert any(
        "adult_personal_care_pump_spray_tier1" in item for item in summary.interpretation_notes
    )


def test_parameter_bounds_summary_builds_bounded_range() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    base_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )

    summary = build_parameter_bounds_summary(
        BuildParameterBoundsInput(
            label="Dermal bounds",
            baseRequest=base_request,
            boundedParameters=[
                ParameterBoundInput(
                    parameterName="concentration_fraction",
                    lowerValue=0.01,
                    upperValue=0.03,
                    rationale="Bound concentration to plausible low and high values.",
                ),
                ParameterBoundInput(
                    parameterName="body_weight_kg",
                    lowerValue=60,
                    upperValue=90,
                    unit="kg",
                    rationale="Bound body weight for normalization.",
                ),
            ],
        ),
        engine,
        defaults_registry,
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_B
    assert summary.min_dose.value < summary.base_scenario.external_dose.value
    assert summary.max_dose.value > summary.base_scenario.external_dose.value
    assert all(item.status == "pass" for item in summary.monotonicity_checks)
    assert summary.uncertainty_register[0].quantification_status.value == "bounded"


def test_probability_bounds_profile_builds_tier_c_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    profiles = ProbabilityBoundsProfileRegistry.load()
    base_request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
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
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )

    summary = build_probability_bounds_from_profile(
        BuildProbabilityBoundsFromProfileInput(
            label="Dermal single-driver probability bounds",
            baseRequest=base_request,
            driverProfileId="adult_leave_on_hand_cream_use_amount_per_event",
        ),
        engine,
        defaults_registry,
        profiles,
        generated_at="2026-03-24T00:00:00+00:00",
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_C
    assert summary.driver_profile_id == "adult_leave_on_hand_cream_use_amount_per_event"
    assert summary.product_family == "personal_care"
    assert summary.driver_family.value == "use_burden"
    assert summary.dependency_cluster == "use-intensity-cluster"
    assert summary.fixed_axes == ["concentration_fraction", "use_events_per_day"]
    assert summary.relationship_type.value == "behavioral"
    assert summary.handling_strategy.value == "not_quantified"
    assert summary.profile_version == profiles.version
    assert summary.archetype_library_set_id == "adult_leave_on_hand_cream"
    assert len(summary.support_points) == 3
    assert summary.minimum_dose.value < summary.maximum_dose.value
    assert summary.uncertainty_register[0].quantification_status.value == "probability_bounds"
    assert any(
        item.dependency_id == "single-driver:adult_leave_on_hand_cream_use_amount_per_event"
        for item in summary.dependency_metadata
    )


def test_oral_probability_bounds_profile_builds_tier_c_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    profiles = ProbabilityBoundsProfileRegistry.load()
    base_request = ExposureScenarioRequest(
        chemical_id="DTXSID124",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="medicinal_liquid",
            physical_form="liquid",
            application_method="direct_oral",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=2.5,
            use_amount_unit="mL",
            use_events_per_day=2,
            density_g_per_ml=1.0,
            ingestion_fraction=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="child",
            body_weight_kg=16.0,
            region="EU",
        ),
    )

    summary = build_probability_bounds_from_profile(
        BuildProbabilityBoundsFromProfileInput(
            label="Child oral single-driver probability bounds",
            baseRequest=base_request,
            driverProfileId="child_direct_oral_liquid_use_events_per_day",
        ),
        engine,
        defaults_registry,
        profiles,
        generated_at="2026-03-25T00:00:00+00:00",
    )

    assert summary.route == Route.ORAL
    assert summary.product_family == "medicinal_liquid"
    assert summary.driver_family.value == "ingestion_regimen"
    assert summary.dependency_cluster == "oral-regimen-cluster"
    assert summary.fixed_axes == [
        "concentration_fraction",
        "use_amount_per_event",
        "ingestion_fraction",
    ]
    assert len(summary.support_points) == 3
    assert summary.minimum_dose.value < summary.maximum_dose.value


def test_scenario_package_probability_builds_tier_c_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    packages = ScenarioProbabilityPackageRegistry.load()

    summary = build_probability_bounds_from_scenario_package(
        BuildProbabilityBoundsFromScenarioPackageInput(
            packageProfileId="adult_leave_on_hand_cream_use_intensity_package",
            chemicalId="DTXSID123",
            chemicalName="Example Chemical",
            label="Dermal scenario-package probability bounds",
        ),
        engine,
        defaults_registry,
        archetype_library,
        packages,
        generated_at="2026-03-25T00:00:00+00:00",
    )

    assert summary.uncertainty_tier == UncertaintyTier.TIER_C
    assert summary.package_profile_id == "adult_leave_on_hand_cream_use_intensity_package"
    assert summary.archetype_library_set_id == "adult_leave_on_hand_cream"
    assert summary.archetype_library_version == archetype_library.version
    assert summary.product_family == "personal_care"
    assert summary.package_family.value == "use_intensity"
    assert summary.dependency_cluster == "use-intensity-cluster"
    assert summary.dependency_axes == [
        "concentration_fraction",
        "use_amount_per_event",
        "use_events_per_day",
    ]
    assert summary.relationship_type.value == "scenario_package"
    assert summary.handling_strategy.value == "scenario_packaged"
    assert len(summary.support_points) == 3
    assert all(item.scenario.route == Route.DERMAL for item in summary.support_points)
    assert summary.minimum_dose.value < summary.maximum_dose.value
    assert summary.uncertainty_register[0].quantification_status.value == "probability_bounds"
    assert any(
        item.dependency_id == "scenario-package:adult_leave_on_hand_cream_use_intensity_package"
        for item in summary.dependency_metadata
    )


def test_oral_scenario_package_probability_builds_tier_c_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    packages = ScenarioProbabilityPackageRegistry.load()

    summary = build_probability_bounds_from_scenario_package(
        BuildProbabilityBoundsFromScenarioPackageInput(
            packageProfileId="child_direct_oral_liquid_regimen_package",
            chemicalId="DTXSID124",
            chemicalName="Example Oral Chemical",
            label="Child oral scenario-package probability bounds",
        ),
        engine,
        defaults_registry,
        archetype_library,
        packages,
        generated_at="2026-03-25T00:00:00+00:00",
    )

    assert summary.route == Route.ORAL
    assert summary.scenario_class == ScenarioClass.SCREENING
    assert summary.product_family == "medicinal_liquid"
    assert summary.package_family.value == "ingestion_regimen"
    assert summary.dependency_axes == [
        "concentration_fraction",
        "use_amount_per_event",
        "use_events_per_day",
        "ingestion_fraction",
    ]
    assert len(summary.support_points) == 3
    assert all(item.scenario.route == Route.ORAL for item in summary.support_points)
    assert summary.minimum_dose.value < summary.maximum_dose.value


def test_tier1_scenario_package_probability_builds_tier_c_summary() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
    archetype_library = ArchetypeLibraryRegistry.load()
    packages = ScenarioProbabilityPackageRegistry.load()

    summary = build_probability_bounds_from_scenario_package(
        BuildProbabilityBoundsFromScenarioPackageInput(
            packageProfileId="adult_personal_care_pump_spray_tier1_near_field_context_package",
            chemicalId="DTXSID126",
            chemicalName="Example Tier 1 Chemical",
            label="Tier 1 inhalation scenario-package probability bounds",
        ),
        engine,
        defaults_registry,
        archetype_library,
        packages,
        generated_at="2026-03-25T00:00:00+00:00",
    )

    assert summary.route == Route.INHALATION
    assert summary.scenario_class == ScenarioClass.INHALATION
    assert summary.product_family == "personal_care"
    assert summary.package_family.value == "near_field_context"
    assert summary.archetype_library_set_id == "adult_personal_care_pump_spray_tier1"
    assert summary.dependency_cluster == "tier1-near-field-context-cluster"
    assert summary.dependency_axes == [
        "concentration_fraction",
        "use_amount_per_event",
        "use_events_per_day",
        "source_distance_m",
        "spray_duration_seconds",
        "near_field_volume_m3",
        "airflow_directionality",
        "particle_size_regime",
    ]
    assert len(summary.support_points) == 3
    assert all(item.scenario.route == Route.INHALATION for item in summary.support_points)
    assert all(
        item.scenario.tier_semantics.tier_claimed == TierLevel.TIER_1
        for item in summary.support_points
    )
    assert all(
        item.scenario.route_metrics["tier1_product_profile_id"] == "personal_care_pump_spray_tier1"
        for item in summary.support_points
    )
    assert summary.minimum_dose.value < summary.maximum_dose.value
    assert any(
        item.entry_id == "scenario-package-mechanistic-constraint-deposition-sink"
        for item in summary.uncertainty_register
    )
