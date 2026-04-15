from __future__ import annotations

import pytest
from pydantic import ValidationError

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    BuildAggregateExposureScenarioInput,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
    TierLevel,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_screening_scenario
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine, aggregate_scenarios


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_inhalation_request_rejects_wrong_route() -> None:
    with pytest.raises(ValidationError):
        InhalationScenarioRequest(
            chemical_id="DTXSID123",
            route=Route.DERMAL,
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
            population_profile=PopulationProfile(population_group="adult"),
        )


def test_screening_engine_rejects_unsupported_plugin_pair() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.SCREENING,
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
        population_profile=PopulationProfile(population_group="adult"),
    )

    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(request)

    assert exc_info.value.code == "plugin_not_available"


def test_inhalation_defaults_fail_for_unknown_application_method() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="unknown_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(request)

    assert exc_info.value.code == "aerosol_method_unsupported"


def test_inhalation_requested_tier_1_fails_loudly() -> None:
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        requestedTier=TierLevel.TIER_1,
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
        population_profile=PopulationProfile(population_group="adult"),
    )

    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(request)

    assert exc_info.value.code == "inhalation_tier_1_not_implemented"
    assert exc_info.value.details["guidanceResource"] == "docs://inhalation-tier-upgrade-guide"
    assert (
        exc_info.value.details["stubTool"]
        == "exposure_build_inhalation_tier1_screening_scenario"
    )


def test_inhalation_tier_1_request_rejects_non_spray_scope() -> None:
    with pytest.raises(ValidationError):
        InhalationTier1ScenarioRequest(
            chemical_id="DTXSID123",
            route=Route.INHALATION,
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
            source_distance_m=0.4,
            spray_duration_seconds=10.0,
            near_field_volume_m3=2.0,
            airflow_directionality="cross_draft",
            particle_size_regime="coarse_spray",
        )


def test_inhalation_tier_1_near_field_volume_must_leave_far_field_room() -> None:
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
            room_volume_m3=10,
            exposure_duration_hours=0.5,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=8.0,
        near_field_volume_m3=10.0,
        airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
        particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
    )

    with pytest.raises(ExposureScenarioError) as exc_info:
        build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load())

    assert exc_info.value.code == "inhalation_tier_1_near_field_volume_invalid"


def test_aggregate_rejects_duplicate_component_ids() -> None:
    engine = build_engine()
    defaults_registry = DefaultsRegistry.load()
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

    with pytest.raises(ExposureScenarioError) as exc_info:
        aggregate_scenarios(
            BuildAggregateExposureScenarioInput(
                chemical_id="DTXSID123",
                label="duplicate",
                component_scenarios=[scenario, scenario],
            ),
            defaults_registry,
        )

    assert exc_info.value.code == "aggregate_duplicate_component"


def test_resolve_population_value_rejects_zero_body_weight() -> None:
    from exposure_scenario_mcp.runtime import resolve_population_value
    from exposure_scenario_mcp.provenance import AssumptionTracker

    tracker = AssumptionTracker(registry=DefaultsRegistry.load())
    with pytest.raises(ExposureScenarioError) as exc_info:
        resolve_population_value(
            field_name="body_weight_kg",
            supplied_value=0.0,
            population_group="adult",
            registry=DefaultsRegistry.load(),
            tracker=tracker,
            unit="kg",
            rationale="Test zero body weight.",
            gt=0.0,
        )
    assert exc_info.value.code == "population_value_not_positive"


def test_resolve_population_value_rejects_zero_surface_area() -> None:
    from exposure_scenario_mcp.runtime import resolve_population_value
    from exposure_scenario_mcp.provenance import AssumptionTracker

    tracker = AssumptionTracker(registry=DefaultsRegistry.load())
    with pytest.raises(ExposureScenarioError) as exc_info:
        resolve_population_value(
            field_name="exposed_surface_area_cm2",
            supplied_value=-10.0,
            population_group="adult",
            registry=DefaultsRegistry.load(),
            tracker=tracker,
            unit="cm2",
            rationale="Test negative surface area.",
            gt=0.0,
        )
    assert exc_info.value.code == "population_value_not_positive"


def test_unknown_population_group_fails_loudly() -> None:
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
        population_profile=PopulationProfile(population_group="astronaut"),
    )

    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(request)

    assert exc_info.value.code == "population_group_unsupported"
