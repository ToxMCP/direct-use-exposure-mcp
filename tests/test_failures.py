from __future__ import annotations

import pytest
from pydantic import ValidationError

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
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
