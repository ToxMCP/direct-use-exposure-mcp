"""Integration tests for the Tier 1 two-zone inhalation builder."""

from __future__ import annotations

import math

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins.inhalation import (
    build_inhalation_tier_1_screening_scenario,
)


def _make_base_request(**overrides) -> InhalationTier1ScenarioRequest:
    defaults = {
        "chemical_id": "test-chem-001",
        "route": Route.INHALATION,
        "scenario_class": ScenarioClass.INHALATION,
        "product_use_profile": ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            concentration_fraction=0.05,
            use_amount_per_event=5.0,
            use_amount_unit="g",
            use_events_per_day=2.0,
            room_volume_m3=30.0,
            air_exchange_rate_per_hour=0.5,
            exposure_duration_hours=1.0,
            aerosolized_fraction=0.2,
        ),
        "population_profile": PopulationProfile(
            population_group="adult",
            body_weight_kg=70.0,
            inhalation_rate_m3_per_hour=0.5,
        ),
        "source_distance_m": 0.35,
        "spray_duration_seconds": 8.0,
        "near_field_volume_m3": 2.0,
        "airflow_directionality": AirflowDirectionality.CROSS_DRAFT,
        "particle_size_regime": ParticleSizeRegime.COARSE_SPRAY,
    }
    defaults.update(overrides)
    return InhalationTier1ScenarioRequest(**defaults)


def test_two_zone_explicit_variant_produces_valid_scenario() -> None:
    request = _make_base_request(solver_variant="two_zone_v1")
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route == Route.INHALATION
    assert scenario.scenario_class == ScenarioClass.INHALATION
    assert scenario.external_dose.unit == "mg/kg-day"
    assert scenario.route_metrics["two_zone_solver_active"] is True
    assert scenario.route_metrics["solver_variant"] == "two_zone_v1"
    assert "mass_balance_residual_mg" in scenario.route_metrics
    assert "near_field_peak_concentration_mg_per_m3" in scenario.route_metrics
    assert "far_field_average_air_concentration_mg_per_m3" in scenario.route_metrics
    assert scenario.provenance.algorithm_id == "inhalation.two_zone.v1"

    mbr = scenario.route_metrics["mass_balance_residual_mg"]
    assert isinstance(mbr, float)
    assert abs(mbr) <= 1e-6


def test_auto_routes_to_heuristic_by_default() -> None:
    request = _make_base_request(solver_variant="auto")
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics.get("two_zone_solver_active") is None
    assert scenario.provenance.algorithm_id == "inhalation.near_field_far_field.v1"


def test_heuristic_variant_unchanged() -> None:
    request = _make_base_request(solver_variant="heuristic_v1")
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics.get("two_zone_solver_active") is None
    assert scenario.provenance.algorithm_id == "inhalation.near_field_far_field.v1"


def test_two_zone_with_beta_override() -> None:
    request = _make_base_request(
        solver_variant="two_zone_v1",
        interzonal_flow_rate_m3_per_hour=150.0,
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics["interzonal_flow_rate_m3_per_hour"] == 150.0
    flag_codes = {qf.code for qf in scenario.quality_flags}
    assert "two_zone_user_beta_override" in flag_codes


def test_two_zone_with_loss_rate_overrides() -> None:
    request = _make_base_request(
        solver_variant="two_zone_v1",
        near_field_loss_rate_per_hour=0.5,
        far_field_loss_rate_per_hour=0.3,
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics["near_field_loss_rate_per_hour"] == 0.5
    assert scenario.route_metrics["far_field_loss_rate_per_hour"] == 0.3


def test_two_zone_source_fraction_override() -> None:
    request = _make_base_request(
        solver_variant="two_zone_v1",
        source_allocation_to_near_field_fraction=0.6,
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics["source_fraction_to_near_field"] == 0.6
    flag_codes = {qf.code for qf in scenario.quality_flags}
    assert "two_zone_source_outside_nf_volume" in flag_codes


def test_two_zone_ventilation_allocation_override() -> None:
    request = _make_base_request(
        solver_variant="two_zone_v1",
        ventilation_allocation_to_near_field_fraction=0.25,
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert scenario.route_metrics["ventilation_fraction_to_near_field"] == 0.25


def test_two_zone_dose_differs_from_heuristic_for_same_inputs() -> None:
    """The two-zone and heuristic models produce different dose estimates because
    the two-zone model resolves transient NF decay after the spray stops, whereas
    the heuristic uses a piecewise average.  We assert they are not identical.
    """
    request_2z = _make_base_request(solver_variant="two_zone_v1")
    request_h = _make_base_request(solver_variant="heuristic_v1")
    registry = DefaultsRegistry.load()

    scenario_2z = build_inhalation_tier_1_screening_scenario(request_2z, registry)
    scenario_h = build_inhalation_tier_1_screening_scenario(request_h, registry)

    dose_2z = scenario_2z.external_dose.value
    dose_h = scenario_h.external_dose.value
    assert dose_2z != pytest.approx(dose_h, rel=1e-3)


def test_two_zone_volatility_warning_when_peak_exceeds_cap() -> None:
    request = _make_base_request(
        solver_variant="two_zone_v1",
        physchem_context={
            "schema_version": "physchemContext.v1",
            "vapor_pressure_mmhg": 1.0,
            "molecular_weight_g_per_mol": 200.0,
        },
        # Very high aerosolized fraction and low ventilation to force high peak
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            concentration_fraction=1.0,
            use_amount_per_event=100.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            room_volume_m3=10.0,
            air_exchange_rate_per_hour=0.1,
            exposure_duration_hours=1.0,
            aerosolized_fraction=1.0,
        ),
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    flag_codes = {qf.code for qf in scenario.quality_flags}
    assert "two_zone_volatility_consistency_warning" in flag_codes


def test_two_zone_far_field_small_volume_warning() -> None:
    p = ProductUseProfile(
        product_category="household_cleaner",
        physical_form="spray",
        application_method="trigger_spray",
        concentration_fraction=0.05,
        use_amount_per_event=5.0,
        use_amount_unit="g",
        use_events_per_day=2.0,
        room_volume_m3=30.0,
        air_exchange_rate_per_hour=0.5,
        exposure_duration_hours=1.0,
        aerosolized_fraction=0.2,
    )
    request = _make_base_request(
        solver_variant="two_zone_v1",
        near_field_volume_m3=29.9,
        product_use_profile=p.model_copy(update={"room_volume_m3": 30.0}),
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    flag_codes = {qf.code for qf in scenario.quality_flags}
    assert "two_zone_far_field_volume_small" in flag_codes


def test_two_zone_mass_balance_with_no_losses() -> None:
    """When deposition and ventilation are both zero, all emitted mass must
    remain in the room at the end of the event.
    """
    request = _make_base_request(
        solver_variant="two_zone_v1",
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            concentration_fraction=0.1,
            use_amount_per_event=10.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            room_volume_m3=50.0,
            air_exchange_rate_per_hour=0.0,
            exposure_duration_hours=1.0,
            aerosolized_fraction=0.5,
        ),
        near_field_loss_rate_per_hour=0.0,
        far_field_loss_rate_per_hour=0.0,
    )
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    mbr = scenario.route_metrics["mass_balance_residual_mg"]
    assert abs(mbr) <= 1e-9


def test_two_zone_pbpk_export_produces_transient_profile() -> None:
    """Two-zone scenarios must expose the metric keys required for PBPK transient export."""
    from exposure_scenario_mcp.runtime import export_pbpk_input
    from exposure_scenario_mcp.models import ExportPbpkScenarioInputRequest

    request = _make_base_request(solver_variant="two_zone_v1")
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    assert "initial_air_concentration_mg_per_m3" in scenario.route_metrics
    assert "air_concentration_at_event_end_mg_per_m3" in scenario.route_metrics

    pbpk = export_pbpk_input(
        ExportPbpkScenarioInputRequest(scenario=scenario, include_transient_concentration_profile=True),
        registry,
    )
    assert len(pbpk.transient_concentration_profile) == 3


def test_auto_fallback_emits_quality_flag() -> None:
    """When auto is forced to heuristic, a quality flag records the fallback."""
    request = _make_base_request(solver_variant="auto")
    registry = DefaultsRegistry.load()
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    flag_codes = {qf.code for qf in scenario.quality_flags}
    assert "two_zone_legacy_fallback_applied" in flag_codes
    assert scenario.provenance.algorithm_id == "inhalation.near_field_far_field.v1"


def test_main_engine_accepts_tier_1() -> None:
    """The main ScenarioEngine must no longer reject Tier 1 inhalation requests."""
    from exposure_scenario_mcp.runtime import (
        PluginRegistry,
        ScenarioEngine,
    )
    from exposure_scenario_mcp.plugins.inhalation import InhalationScreeningPlugin

    registry = DefaultsRegistry.load()
    plugin_registry = PluginRegistry()
    plugin_registry.register(InhalationScreeningPlugin())
    engine = ScenarioEngine(plugin_registry, registry)

    request = _make_base_request(
        requested_tier="tier_1",
        solver_variant="two_zone_v1",
    )
    scenario = engine.build(request)

    assert scenario.provenance.algorithm_id == "inhalation.two_zone.v1"
    assert scenario.route_metrics["solver_variant"] == "two_zone_v1"
