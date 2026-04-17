import pytest

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
    defaults_registry = DefaultsRegistry.load()
    plugins = PluginRegistry()
    plugins.register(ScreeningScenarioPlugin())
    plugins.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=plugins, defaults_registry=defaults_registry)


def test_ema_herbal_ointment_validation_check() -> None:
    engine = build_engine()
    # 1.5 g on 1000 cm2 = 1.5 mg/cm2 (Passes EMA 1.0-2.0 band)
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_HERBAL",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="herbal_topical_product",
            physical_form="ointment",
            application_method="hand_application",
            retention_type="leave_on",
            intended_use_family="medicinal",
            concentration_fraction=0.01,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            exposed_surface_area_cm2=1000.0,
        ),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    check = next(
        (c for c in checks if c.check_id == "ema_hmpc_topical_ointment_loading_default"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == 1.5
    assert check.reference_lower == 1.0
    assert check.reference_upper == 2.0


def test_sccs_cosmetic_balm_validation_check() -> None:
    engine = build_engine()
    # 2.236 g on 860 cm2 = 2.6 mg/cm2 (Passes SCCS 2.5-2.7 band)
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_BALM",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="balm",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.05,
            use_amount_per_event=2.236,
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

    check = next(
        (c for c in checks if c.check_id == "sccs_cosmetic_balm_loading_category"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(2.6, rel=1e-3)


def test_ftu_dermatology_validation_check() -> None:
    engine = build_engine()
    # 0.5 g on 300 cm2 = 1.666... mg/cm2 (Passes FTU 1.5-1.8 band)
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_FTU",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="generic_topical",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            application_coverage_context="two_hand_prints_area",
            concentration_fraction=0.1,
            use_amount_per_event=0.5,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            exposed_surface_area_cm2=300.0,
        ),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    check = next(
        (c for c in checks if c.check_id == "dermatology_fingertip_unit_loading_anchor"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(1.66666667, rel=1e-6)
