"""Tests for China population regionalization."""

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins.inhalation import InhalationScreeningPlugin
from exposure_scenario_mcp.plugins.screening import ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine


def _build_engine(defaults_registry: DefaultsRegistry | None = None) -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(
        registry=registry,
        defaults_registry=defaults_registry or DefaultsRegistry.load(),
    )


def test_china_adult_population_defaults() -> None:
    registry = DefaultsRegistry.load()
    defaults, source = registry.population_defaults("adult", region="china")
    assert defaults["body_weight_kg"] == pytest.approx(63.0, rel=1e-6)
    assert defaults["inhalation_rate_m3_per_hour"] == pytest.approx(0.67, rel=1e-6)
    assert defaults["exposed_surface_area_cm2"] == pytest.approx(16500.0, rel=1e-6)
    assert source.source_id == "china_exposure_factors_handbook_adults_2013"


def test_global_fallback_when_region_unknown() -> None:
    registry = DefaultsRegistry.load()
    defaults, source = registry.population_defaults("adult", region="mars")
    assert defaults["body_weight_kg"] == pytest.approx(80.0, rel=1e-6)
    assert source.source_id == "epa_exposure_factors_handbook_2011"


def test_china_population_dose_is_higher_than_global() -> None:
    """Same chemical mass with lighter body weight = higher normalized dose."""
    engine = _build_engine()
    profile = ProductUseProfile(
        product_category="herbal_medicinal_product",
        physical_form="solid",
        application_method="direct_oral",
        retention_type="leave_on",
        concentration_fraction=0.05,
        use_amount_per_event=0.5,
        use_amount_unit="g",
        use_events_per_day=2,
    )

    request_global = ExposureScenarioRequest(
        chemical_id="TCM-CHINA-TEST",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=profile,
        population_profile=PopulationProfile(population_group="adult", region="global"),
    )
    request_china = ExposureScenarioRequest(
        chemical_id="TCM-CHINA-TEST",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=profile,
        population_profile=PopulationProfile(population_group="adult", region="china"),
    )

    scenario_global = engine.build(request_global)
    scenario_china = engine.build(request_china)

    # Same external mass, lighter body weight -> higher normalized dose
    assert scenario_china.external_dose.value > scenario_global.external_dose.value
    # Expected ratio: 80 / 63 ≈ 1.27
    ratio = scenario_china.external_dose.value / scenario_global.external_dose.value
    assert ratio == pytest.approx(80.0 / 63.0, rel=1e-6)

    # Verify quality flag is present for China scenario
    china_flag_codes = {qf.code for qf in scenario_china.quality_flags}
    assert "regional_population_override_active" in china_flag_codes

    # Global scenario should NOT have the regional flag
    global_flag_codes = {qf.code for qf in scenario_global.quality_flags}
    assert "regional_population_override_active" not in global_flag_codes


def test_supported_regions_includes_china() -> None:
    registry = DefaultsRegistry.load()
    manifest = registry.manifest()
    assert "china" in manifest["supported_regions"]
    assert "eu" in manifest["supported_regions"]
    assert "global" in manifest["supported_regions"]
