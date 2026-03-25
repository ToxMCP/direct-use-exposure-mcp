from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_request_rejects_control_characters_in_chemical_id() -> None:
    with pytest.raises(ValidationError):
        ExposureScenarioRequest(
            chemical_id="DTXSID123\nunsafe",
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


def test_product_use_profile_rejects_control_characters_in_category() -> None:
    with pytest.raises(ValidationError):
        ProductUseProfile(
            product_category="personal\x00care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=3,
        )


def test_request_rejects_unexpected_extra_field() -> None:
    with pytest.raises(ValidationError):
        ExposureScenarioRequest(
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
            unexpected_field="blocked",
        )


def test_extreme_valid_body_weights_build_without_numeric_instability() -> None:
    engine = build_engine()
    low_weight = engine.build(
        ExposureScenarioRequest(
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
            population_profile=PopulationProfile(population_group="adult", body_weight_kg=0.1),
        )
    )
    high_weight = engine.build(
        ExposureScenarioRequest(
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
            population_profile=PopulationProfile(population_group="adult", body_weight_kg=10000.0),
        )
    )

    low_dose = low_weight.external_dose.value
    high_dose = high_weight.external_dose.value

    assert math.isfinite(low_dose)
    assert math.isfinite(high_dose)
    assert low_dose > high_dose > 0.0
