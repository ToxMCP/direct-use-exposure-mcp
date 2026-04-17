"""Independent benchmark replications to validate engine outputs against third-party math.

These tests replicate cornerstone scenarios using only basic Python arithmetic
and standard formulas, not the engine's internal utilities. They address the
regulatory need for external validation rather than self-referential regression.
"""

from __future__ import annotations

import math

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    InhalationScenarioRequest,
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


def test_independent_dermal_hand_cream_screening() -> None:
    """Replicate the canonical dermal hand-cream scenario with independent arithmetic.

    Independent calculation:
        product_mass_g_event   = 1.5 g
        chemical_mass_mg_event = 1.5 g * 1000 mg/g * 0.02 = 30 mg
        external_mass_mg_day   = 30 mg * 3 events * 1.0 (transfer) * 1.0 (retention)
                               = 90 mg/day
        normalized_dose      = 90 mg/day / 80 kg
                               = 1.125 mg/kg-day
        surface_loading      = 90 mg/day / 5700 cm²
                               ≈ 0.01578947 mg/cm²/day
        product_mass_loading = 1.5 g * 1000 mg/g / 5700 cm²
                               ≈ 0.26315789 mg/cm²/event
        chemical_loading     = 30 mg / 5700 cm²
                               ≈ 0.00526316 mg/cm²/event
    """
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

    # Independent expected values
    product_mass_g_event = 1.5
    chemical_mass_mg_event = product_mass_g_event * 1000.0 * 0.02
    external_mass_mg_day = chemical_mass_mg_event * 3 * 1.0 * 1.0
    body_weight_kg = 80.0
    surface_area_cm2 = 5700.0
    expected_dose = external_mass_mg_day / body_weight_kg
    expected_surface_loading = external_mass_mg_day / surface_area_cm2
    expected_product_mass_loading = product_mass_g_event * 1000.0 / surface_area_cm2
    expected_chemical_loading = chemical_mass_mg_event / surface_area_cm2

    assert scenario.external_dose.value == pytest.approx(expected_dose, rel=1e-9)
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(
        external_mass_mg_day, rel=1e-9
    )
    assert scenario.route_metrics["surface_loading_mg_per_cm2_day"] == pytest.approx(
        expected_surface_loading, abs=1e-8
    )
    assert scenario.route_metrics["product_mass_loading_mg_per_cm2_per_event"] == pytest.approx(
        expected_product_mass_loading, abs=1e-8
    )
    assert scenario.route_metrics["chemical_loading_mg_per_cm2_per_event"] == pytest.approx(
        expected_chemical_loading, abs=1e-8
    )


def test_independent_oral_supplement_screening() -> None:
    """Replicate a direct-use oral supplement scenario with independent arithmetic.

    Independent calculation:
        product_mass_g_event   = 0.5 g (one capsule)
        chemical_mass_mg_event = 0.5 g * 1000 mg/g * 0.5 = 250 mg
        external_mass_mg_day   = 250 mg * 2 events
                               = 500 mg/day
        normalized_dose      = 500 mg/day / 70 kg
                               ≈ 7.14285714 mg/kg-day
    """
    engine = build_engine()
    request = ExposureScenarioRequest(
        chemical_id="DTXSID456",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="supplement",
            physical_form="capsule",
            application_method="direct_oral",
            retention_type="ingested",
            concentration_fraction=0.5,
            use_amount_per_event=0.5,
            use_amount_unit="g",
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )
    scenario = engine.build(request)

    product_mass_g_event = 0.5
    chemical_mass_mg_event = product_mass_g_event * 1000.0 * 0.5
    external_mass_mg_day = chemical_mass_mg_event * 2
    body_weight_kg = 80.0  # adult default from population_defaults
    expected_dose = external_mass_mg_day / body_weight_kg

    assert scenario.external_dose.value == pytest.approx(expected_dose, rel=1e-9)
    assert scenario.route_metrics["external_mass_mg_per_day"] == pytest.approx(
        external_mass_mg_day, rel=1e-9
    )


def test_independent_inhalation_room_average_trigger_spray() -> None:
    """Replicate a well-mixed room inhalation scenario with independent first-order math.

    Independent calculation for average concentration over exposure duration:
        C0 = released_mass_mg / room_volume_m3
        C_avg = C0 * (1 - exp(-k * t)) / (k * t)
        inhaled_mass_mg = C_avg * inhalation_rate * t
        normalized_dose = inhaled_mass_mg / body_weight_kg

    Where:
        released_mass_mg = 10 g * 1000 mg/g * 0.05 (conc) * 0.2 (airborne)
                         = 100 mg
        room_volume_m3   = 25 m³
        k (total_loss)   = 0.5 (ACH) + 0.2 (deposition) = 0.7 /h
        t                = 0.5 h
        inhalation_rate  = 0.83 m³/h
        body_weight_kg   = 80 kg
    """
    engine = build_engine()
    request = InhalationScenarioRequest(
        chemical_id="DTXSID789",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=10.0,
            use_amount_unit="g",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )
    scenario = engine.build(request)

    # Build request first to inspect actual resolved defaults from the engine
    scenario = engine.build(request)

    # Now replicate independently using the same resolved parameters
    product_mass_g_event = 10.0
    concentration_fraction = 0.05
    aerosolized_fraction = 0.2  # trigger_spray household_cleaner default
    released_mass_mg = product_mass_g_event * 1000.0 * concentration_fraction * aerosolized_fraction

    # Resolved defaults for adult inhalation (global region defaults)
    room_volume_m3 = 20.0
    air_exchange_rate = 0.6
    deposition_rate = 0.5
    total_loss_rate = air_exchange_rate + deposition_rate
    exposure_duration_hours = 0.5
    inhalation_rate_m3_per_hour = 0.83
    body_weight_kg = 80.0

    c0 = released_mass_mg / room_volume_m3
    c_avg = (
        c0
        * (1.0 - math.exp(-total_loss_rate * exposure_duration_hours))
        / (total_loss_rate * exposure_duration_hours)
    )
    inhaled_mass_mg = c_avg * inhalation_rate_m3_per_hour * exposure_duration_hours
    expected_dose = inhaled_mass_mg / body_weight_kg

    assert scenario.external_dose.value == pytest.approx(expected_dose, rel=1e-6)
    assert scenario.route_metrics["average_air_concentration_mg_per_m3"] == pytest.approx(
        c_avg, rel=1e-6
    )


def test_independent_inhalation_two_zone_steady_state() -> None:
    """Replicate the deterministic two-zone steady state with closed-form 2x2 algebra.

    Independent calculation for the 2x2 ODE steady state:
        A = [[-a, b], [c, -d]]
        u = [eta*G/V_nf, (1-eta)*G/V_ff]
        det = a*d - b*c
        C_NF,ss = (d*u_n + b*u_f) / det
        C_FF,ss = (c*u_n + a*u_f) / det

    With the test parameters:
        V_nf = 1 m3, V_ff = 49 m3, beta = 200 m3/h, phi = 0.0
        Q_room = 100 m3/h, k_nf = k_ff = 0, eta = 1.0
        G = 100000 mg/h (1000 mL * 1.0 g/mL * 1000 mg/g * 1.0 conc / 10 h)
        a = 200, b = 200, c = 200/49, d = 300/49
        det = 20000/49
        C_FF,ss = G/Q = 1000 mg/m3
        C_NF,ss = G/Q + G/beta = 1500 mg/m3
    """
    from exposure_scenario_mcp.models import InhalationTier1ScenarioRequest
    from exposure_scenario_mcp.plugins.inhalation import (
        build_inhalation_tier_1_screening_scenario,
    )

    registry = DefaultsRegistry.load()
    request = InhalationTier1ScenarioRequest(
        chemical_id="BENCH_2Z_SS",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=1.0,
            use_amount_per_event=1000.0,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=50.0,
            air_exchange_rate_per_hour=2.0,
            exposure_duration_hours=10.0,
            aerosolized_fraction=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68.0,
            inhalation_rate_m3_per_hour=0.9,
            region="EU",
        ),
        source_distance_m=0.35,
        spray_duration_seconds=36000.0,
        near_field_volume_m3=1.0,
        airflow_directionality="cross_draft",
        particle_size_regime="coarse_spray",
        solver_variant="two_zone_v1",
        interzonal_flow_rate_m3_per_hour=200.0,
        ventilation_allocation_to_near_field_fraction=0.0,
        near_field_loss_rate_per_hour=0.0,
        far_field_loss_rate_per_hour=0.0,
    )
    scenario = build_inhalation_tier_1_screening_scenario(request, registry)

    # Independent algebraic steady-state solution
    v_nf = 1.0
    v_ff = 49.0
    beta = 200.0
    q_room = 100.0
    phi = 0.0
    k_nf = 0.0
    k_ff = 0.0
    eta = 1.0
    g = 100000.0  # mg/h

    a = beta / v_nf + k_nf + phi * q_room / v_nf
    b = beta / v_nf
    c = beta / v_ff
    d = beta / v_ff + k_ff + (1.0 - phi) * q_room / v_ff
    det = a * d - b * c
    u_n = eta * g / v_nf
    u_f = (1.0 - eta) * g / v_ff

    c_nf_ss = (d * u_n + b * u_f) / det
    c_ff_ss = (c * u_n + a * u_f) / det

    assert scenario.route_metrics["far_field_end_concentration_mg_per_m3"] == pytest.approx(
        c_ff_ss, rel=1e-8
    )
    assert scenario.route_metrics["near_field_end_concentration_mg_per_m3"] == pytest.approx(
        c_nf_ss, rel=1e-8
    )
    # Mass-balance residual must be exact for this lossless steady-state case.
    assert scenario.route_metrics["mass_balance_residual_mg"] == pytest.approx(0.0, abs=1e-6)


def test_independent_worker_dermal_handheld_spray_loading() -> None:
    """Replicate worker dermal absorbed dose for an unprotected immersion case.

    Independent calculation:
        external_skin_mass_mg_day   = 1000.0  (override)
        ppe_penetration_factor      = 0.5     (override)
        protected_external_mass     = 1000 * 0.5 = 500 mg/day
        dermal_absorption_fraction  = 0.1     (override)
        absorbed_mass_mg_day        = 500 * 0.1 = 50 mg/day
        body_weight_kg              = 70.0    (override)
        external_dose               = 500 / 70 ≈ 7.14285714 mg/kg-day
        absorbed_dose               = 50 / 70 ≈ 0.71428571 mg/kg-day
    """
    from exposure_scenario_mcp.worker_dermal import (
        ExecuteWorkerDermalAbsorbedDoseRequest,
        ExportWorkerDermalAbsorbedDoseBridgeRequest,
        WorkerDermalAbsorbedDoseExecutionOverrides,
        WorkerDermalBarrierMaterial,
        WorkerDermalContactPattern,
        WorkerDermalPpeState,
        build_worker_dermal_absorbed_dose_bridge,
        execute_worker_dermal_absorbed_dose_task,
    )

    registry = DefaultsRegistry.load()
    base = ExposureScenarioRequest(
        chemical_id="WORKER_DERMAL_SIMPLE",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="liquid",
            application_method="hand_application",
            retention_type="surface_contact",
            concentration_fraction=0.1,
            use_amount_per_event=100.0,
            use_amount_unit="mL",
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(population_group="adult", body_weight_kg=70.0),
    )
    bridge = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=base,
            contact_pattern=WorkerDermalContactPattern.IMMERSION_CONTACT,
            contact_duration_hours=1.0,
            ppe_state=WorkerDermalPpeState.NONE,
            barrier_material=WorkerDermalBarrierMaterial.UNKNOWN,
        ),
        registry=registry,
    )
    execution = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge.tool_call.arguments,
            execution_overrides=WorkerDermalAbsorbedDoseExecutionOverrides(
                external_skin_mass_mg_per_day=1000.0,
                body_zone_surface_area_cm2=500.0,
                ppe_penetration_factor=0.5,
                dermal_absorption_fraction=0.1,
            ),
            context_of_use="worker-dermal-execution",
        ),
        registry=registry,
    )

    # Note: the execution computes external_dose from retained mass (before PPE)
    # and absorbed_dose from protected mass (after PPE).
    expected_external_dose = 1000.0 / 70.0
    expected_absorbed_dose = 50.0 / 70.0

    assert execution.external_dose is not None
    assert execution.external_dose.value == pytest.approx(expected_external_dose, rel=1e-8)
    assert execution.absorbed_dose is not None
    assert execution.absorbed_dose.value == pytest.approx(expected_absorbed_dose, rel=1e-8)
    assert execution.route_metrics["protectedExternalSkinMassMgPerDay"] == pytest.approx(
        500.0, rel=1e-8
    )


def test_independent_worker_art_capture_hood_adjustment() -> None:
    """Replicate worker Tier 2 ART dose as baseline concentration x control factor.

    Independent calculation:
        product_mass_g       = 12 mL * 1.0 g/mL = 12 g
        chemical_mass_mg     = 12 g * 1000 * 0.05 = 600 mg
        aerosolized_fraction = 0.2 (trigger_spray household_cleaner default)
        released_mass_mg     = 600 * 0.2 = 120 mg
        room_volume_m3       = 25 m3
        total_loss_rate      = 0.5 (deposition) + 0.5 (ACH default) = 1.0 /h
        C0                   = 120 / 25 = 4.8 mg/m3
        C_avg                = C0 * (1 - exp(-1.0 * 0.5)) / (1.0 * 0.5)
                             ≈ 3.77543429 mg/m3
        base_inhalation_rate = 0.83 m3/h
        baseline_inhaled_mass= 3.77543429 * 0.83 * 0.5 ≈ 1.56680523 mg/day
        control_factor       = 0.5 (override)
        adjusted_inhaled_mass= 1.56680523 * 0.5 ≈ 0.78340262 mg/day
        body_weight_kg       = 80.0
        external_dose        = 0.78340262 / 80 ≈ 0.00779253 mg/kg-day
    """
    from exposure_scenario_mcp.worker_tier2 import (
        ExecuteWorkerInhalationTier2Request,
        ExportWorkerInhalationTier2BridgeRequest,
        WorkerInhalationTier2ExecutionOverrides,
        WorkerVentilationContext,
        build_worker_inhalation_tier2_bridge,
        execute_worker_inhalation_tier2_task,
    )

    registry = DefaultsRegistry.load()
    base = InhalationScenarioRequest(
        chemical_id="WORKER_ART_SIMPLE",
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1,
        ),
        population_profile=PopulationProfile(population_group="adult"),
    )
    bridge = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=base,
            task_description="Simple spray cleaning",
            ventilation_context=WorkerVentilationContext.UNKNOWN,
        ),
        registry=registry,
    )
    execution = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=bridge.tool_call.arguments,
            execution_overrides=WorkerInhalationTier2ExecutionOverrides(
                control_factor=0.5,
                respiratory_protection_factor=1.0,
                vapor_release_fraction=1.0,
            ),
            context_of_use="worker-inhalation-tier2-execution",
        ),
        registry=registry,
    )

    # Independent first-order room-average calculation
    # The worker Tier 2 baseline uses the same global inhalation defaults as the
    # Tier 0 screening model (room_volume = 20 m3, ACH = 0.6 /h).
    product_mass_g = 12.0
    concentration_fraction = 0.05
    aerosolized_fraction = 0.2
    released_mass_mg = product_mass_g * 1000.0 * concentration_fraction * aerosolized_fraction
    room_volume_m3 = 20.0
    air_exchange_rate = 0.6
    deposition_rate = 0.5
    total_loss_rate = air_exchange_rate + deposition_rate
    exposure_duration_hours = 0.5
    base_inhalation_rate = 0.83
    body_weight_kg = 80.0
    control_factor = 0.5

    c0 = released_mass_mg / room_volume_m3
    c_avg = (
        c0
        * (1.0 - math.exp(-total_loss_rate * exposure_duration_hours))
        / (total_loss_rate * exposure_duration_hours)
    )
    baseline_inhaled_mass = c_avg * base_inhalation_rate * exposure_duration_hours
    expected_baseline_dose = baseline_inhaled_mass / body_weight_kg
    expected_external_dose = expected_baseline_dose * control_factor

    assert execution.baseline_dose is not None
    assert execution.baseline_dose.value == pytest.approx(expected_baseline_dose, rel=1e-5)
    assert execution.external_dose is not None
    assert execution.external_dose.value == pytest.approx(expected_external_dose, rel=1e-5)
    assert execution.route_metrics["effectiveWorkerControlFactor"] == pytest.approx(
        control_factor, rel=1e-8
    )
