import pytest
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.runtime import ScenarioEngine, PluginRegistry
from exposure_scenario_mcp.plugins import ScreeningScenarioPlugin, InhalationScreeningPlugin
from exposure_scenario_mcp.defaults import DefaultsRegistry


def build_engine() -> ScenarioEngine:
    defaults_registry = DefaultsRegistry.load()
    plugins = PluginRegistry()
    plugins.register(ScreeningScenarioPlugin())
    plugins.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=plugins, defaults_registry=defaults_registry)


def test_melatonin_gummy_validation_check() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_MELATONIN",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="dietary_supplement",
            product_subtype="melatonin_gummy",
            physical_form="gummy",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.002,  # e.g., 5mg in 2.5g
            use_amount_per_event=2.5,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    check = next(
        (c for c in checks if c.check_id == "dietary_supplement_melatonin_gummy_daily_mass_2026"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(5.0, rel=1e-6)
    assert check.reference_lower == 5.0
    assert check.reference_upper == 5.0


def test_echinacea_tincture_validation_check() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_ECHINACEA",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="botanical_supplement",
            product_subtype="echinacea_tincture",
            physical_form="liquid",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.25,  # 250mg in 1g (approx 1mL)
            use_amount_per_event=1.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    check = next(
        (c for c in checks if c.check_id == "botanical_supplement_echinacea_tincture_daily_mass_2026"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(250.0, rel=1e-6)
    assert check.reference_lower == 250.0
    assert check.reference_upper == 250.0


def test_vitaminc_effervescent_validation_check() -> None:
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID_VITAMINC",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="dietary_supplement",
            product_subtype="vitamin_c_effervescent",
            physical_form="tablet",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.25,  # 1000mg in a 4g tablet
            use_amount_per_event=4.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )

    scenario = engine.build(request)
    checks = scenario.validation_summary.executed_validation_checks

    check = next(
        (c for c in checks if c.check_id == "dietary_supplement_effervescent_vitaminc_daily_mass_2026"),
        None,
    )
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(1000.0, rel=1e-6)
    assert check.reference_lower == 1000.0
    assert check.reference_upper == 1000.0
