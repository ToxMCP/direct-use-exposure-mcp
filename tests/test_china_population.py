"""Tests for China population regionalization."""

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenario,
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


def _dermal_request(population_profile: PopulationProfile) -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="TCM-CHINA-DERMAL",
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
        population_profile=population_profile,
    )


def _regional_flags(scenario: ExposureScenario) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}
    for flag in scenario.quality_flags:
        if flag.code.startswith("regional_population_override_"):
            flags.setdefault(flag.code, []).append(flag.message)
    return flags


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

    # The China override is flagged, alongside the global default it replaced.
    assert _regional_flags(scenario_china) == {
        "regional_population_override_active": [
            "Population default 'body_weight_kg' uses the region='china' override "
            "(63.0 kg); the global default is 80.0 kg."
        ]
    }

    # Global scenario should NOT have any regional flag
    assert _regional_flags(scenario_global) == {}


@pytest.mark.parametrize("region", ["EU", "US", "CN"])
def test_region_without_population_override_flags_global_fallback(region: str) -> None:
    """Regions without a population override resolve the global defaults, not an override."""
    engine = _build_engine()
    scenario = engine.build(
        _dermal_request(PopulationProfile(population_group="adult", region=region))
    )

    assumptions = {item.name: item.value for item in scenario.assumptions}
    assert assumptions["body_weight_kg"] == pytest.approx(80.0, rel=1e-6)
    assert assumptions["exposed_surface_area_cm2"] == pytest.approx(5700.0, rel=1e-6)

    flags = _regional_flags(scenario)
    assert "regional_population_override_active" not in flags
    assert flags["regional_population_override_unavailable"] == [
        "Population default 'body_weight_kg' uses the global default (80.0 kg) because no "
        f"'adult' population override exists for region='{region}'. Regions with 'adult' "
        "population overrides: china.",
        "Population default 'exposed_surface_area_cm2' uses the global default (5700.0 cm2) "
        f"because no 'adult' population override exists for region='{region}'. Regions with "
        "'adult' population overrides: china.",
    ]


def test_population_override_region_matching_is_case_insensitive() -> None:
    engine = _build_engine()

    china_scenario = engine.build(
        _dermal_request(PopulationProfile(population_group="adult", region="China"))
    )
    china_flags = _regional_flags(china_scenario)
    assert list(china_flags) == ["regional_population_override_active"]
    assert len(china_flags["regional_population_override_active"]) == 2
    assumptions = {item.name: item.value for item in china_scenario.assumptions}
    assert assumptions["exposed_surface_area_cm2"] == pytest.approx(16500.0, rel=1e-6)

    global_scenario = engine.build(
        _dermal_request(PopulationProfile(population_group="adult", region="Global"))
    )
    assert _regional_flags(global_scenario) == {}


def test_supplied_population_values_do_not_raise_regional_flags() -> None:
    engine = _build_engine()
    for region in ("china", "EU"):
        scenario = engine.build(
            _dermal_request(
                PopulationProfile(
                    population_group="adult",
                    region=region,
                    body_weight_kg=70.0,
                    exposed_surface_area_cm2=2000.0,
                )
            )
        )
        assert _regional_flags(scenario) == {}


def test_population_override_regions_lists_only_regions_with_the_group() -> None:
    registry = DefaultsRegistry.load()
    assert registry.population_override_regions("adult") == ["china"]
    assert registry.population_override_regions("Infant") == ["china"]
    assert "eu" in registry.manifest()["supported_regions"]
    assert "eu" not in registry.population_override_regions("adult")


def test_china_dermal_surface_area_warning_uses_regional_value() -> None:
    engine = _build_engine()
    request = _dermal_request(PopulationProfile(population_group="adult", region="china"))

    scenario = engine.build(request)
    warning_messages = [
        qf.message
        for qf in scenario.quality_flags
        if qf.code == "dermal_surface_area_defaulted_hands_forearms_anchor"
    ]

    assert warning_messages
    assert "16500 cm" in warning_messages[0]
    assert "region='china'" in warning_messages[0]


def test_supported_regions_includes_china() -> None:
    registry = DefaultsRegistry.load()
    manifest = registry.manifest()
    assert "china" in manifest["supported_regions"]
    assert "eu" in manifest["supported_regions"]
    assert "global" in manifest["supported_regions"]
