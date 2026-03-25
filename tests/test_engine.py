from __future__ import annotations

import pytest

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
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
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParameterBoundInput,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
    TierLevel,
    UncertaintyTier,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_capability_notice
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
)
from exposure_scenario_mcp.scenario_probability_packages import (
    ScenarioProbabilityPackageRegistry,
)
from exposure_scenario_mcp.uncertainty import (
    build_exposure_envelope,
    build_exposure_envelope_from_library,
    build_parameter_bounds_summary,
)


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


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
    assert scenario.external_dose.value == pytest.approx(0.95625, rel=1e-6)
    assert scenario.route_metrics["surface_loading_mg_per_cm2_day"] == pytest.approx(
        0.01342105, rel=1e-6
    )
    assumption_names = {item.name for item in scenario.assumptions}
    assert {"retention_factor", "transfer_efficiency", "body_weight_kg"} <= assumption_names
    assert any(flag.code == "heuristic_default_source" for flag in scenario.quality_flags)
    retention = next(item for item in scenario.assumptions if item.name == "retention_factor")
    assert retention.governance.evidence_basis == EvidenceBasis.HEURISTIC_DEFAULT
    assert retention.governance.evidence_grade == EvidenceGrade.GRADE_1
    assert retention.governance.default_visibility == DefaultVisibility.WARN
    assert retention.governance.applicability_status == ApplicabilityStatus.SCREENING_EXTRAPOLATION
    assert retention.governance.applicability_domain["retention_type"] == "leave_on"
    assert scenario.tier_semantics.tier_claimed == TierLevel.TIER_0
    assert scenario.tier_semantics.tier_earned == TierLevel.TIER_0
    assert scenario.tier_semantics.assumption_checks_passed is True
    assert scenario.uncertainty_tier == UncertaintyTier.TIER_A
    assert scenario.validation_summary is not None
    assert scenario.validation_summary.validation_status.value == "benchmark_regression"
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

    assert scenario.external_dose.value == pytest.approx(0.02844477, rel=1e-6)
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        4.29832067, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(1.9342443, rel=1e-6)
    assert any(item.code == "breathing_zone_not_modeled" for item in scenario.limitations)
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
    assert any(
        item.entry_id == "limitation-breathing_zone_not_modeled"
        for item in scenario.uncertainty_register
    )


def test_inhalation_tier_1_stub_notice_is_machine_actionable() -> None:
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
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=2.0,
        airflow_directionality="cross_draft",
        particle_size_regime="coarse_spray",
    )

    notice = build_inhalation_tier_1_capability_notice(request)

    assert notice.status == "blocked_not_implemented"
    assert notice.tool_name == "exposure_build_inhalation_tier1_screening_scenario"
    assert notice.recommended_model_family == "inhalation_near_field_far_field_screening"
    assert notice.guidance_resource == "docs://inhalation-tier-upgrade-guide"
    assert notice.accepted_inputs == [
        "source_distance_m",
        "spray_duration_seconds",
        "near_field_volume_m3",
        "airflow_directionality",
        "particle_size_regime",
    ]
    assert "tier_1_solver_not_implemented" in notice.blocking_gaps


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
    assert density.source.source_id == "heuristic_screening_defaults_v1"
    assert density.governance.applicability_domain["physical_form"] == "cream"
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(161.5, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(2.01875, rel=1e-6)


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
    transfer_efficiency = next(
        item for item in scenario.assumptions if item.name == "transfer_efficiency"
    )

    assert transfer_efficiency.value == pytest.approx(0.65, rel=1e-6)
    assert transfer_efficiency.source.source_id == "heuristic_screening_defaults_v1"
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(65.0, rel=1e-6)
    assert scenario.external_dose.value == pytest.approx(0.8125, rel=1e-6)


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

    assert aerosolized_fraction.value == pytest.approx(0.3, rel=1e-6)
    assert aerosolized_fraction.source.source_id == "heuristic_screening_defaults_v1"
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        9.48180838, rel=1e-6
    )
    assert scenario.route_metrics["inhaled_mass_mg_per_day"] == pytest.approx(
        9.48180838, rel=1e-6
    )
    assert scenario.external_dose.value == pytest.approx(0.13545441, rel=1e-6)


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
    assert aggregate.normalized_total_external_dose.value == pytest.approx(0.98469477, rel=1e-6)
    assert any(item.code == "cross_route_aggregate" for item in aggregate.limitations)
    assert aggregate.uncertainty_tier == UncertaintyTier.TIER_A
    assert aggregate.validation_summary is not None
    assert delta.absolute_delta == pytest.approx(-0.37125, rel=1e-6)
    assert delta.percent_delta == pytest.approx(-38.8235, rel=1e-6)
    assert any(item.name == "retention_factor" for item in delta.changed_assumptions)


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
