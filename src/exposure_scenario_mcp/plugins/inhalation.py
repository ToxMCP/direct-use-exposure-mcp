"""Deterministic inhalation screening plugin."""

from __future__ import annotations

import math
from typing import cast
from uuid import uuid4

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    DoseUnit,
    ExposureScenario,
    InhalationResidualAirReentryScenarioRequest,
    InhalationTier1ScenarioRequest,
    PhyschemContext,
    ResidualAirReentryMode,
    Route,
    ScalarValue,
    ScenarioClass,
    ScenarioDose,
    Severity,
    TierLevel,
    TierUpgradeAdvisory,
    TierUpgradeInputRequirement,
    TierUpgradeStatus,
)
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.runtime import (
    ScenarioExecutionContext,
    ScenarioPlugin,
    grams_to_mg,
    resolve_population_value,
    resolve_product_mass_g,
)
from exposure_scenario_mcp.solvers.two_zone import (
    TwoZoneParams,
    solve_two_zone_piecewise_constant,
)
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.worker_routing import apply_worker_task_semantics

TIER_1_SPRAY_METHODS = {"trigger_spray", "pump_spray", "aerosol_spray"}
TIER_1_MODEL_FAMILY = "inhalation_near_field_far_field_screening"
TIER_1_GUIDANCE_RESOURCE = "docs://inhalation-tier-upgrade-guide"
SUBTYPE_SENSITIVE_SPRAY_FAMILIES = {"pesticide", "pest_control", "biocide", "disinfectant"}
RESIDUAL_AIR_REENTRY_APPLICATION_METHOD = "residual_air_reentry"
TIER_1_PROFILE_NUMERIC_TOLERANCES = {
    "source_distance_m": 0.35,
    "near_field_volume_m3": 0.35,
    "spray_duration_seconds": 0.4,
}
IDEAL_GAS_CONSTANT_J_PER_MOL_K = 8.314462618
STANDARD_TEMPERATURE_K = 298.15
STANDARD_PRESSURE_PA = 101325.0
STANDARD_PRESSURE_MMHG = 760.0

# Hard-coded gate for auto-routing to the two-zone solver.
# Remains False until formal benchmark migration is signed off.
TIER1_TWO_ZONE_AUTO_ENABLED = False


def tier_1_input_requirements() -> list[TierUpgradeInputRequirement]:
    return [
        TierUpgradeInputRequirement(
            fieldName="source_distance_m",
            description="Distance from the breathing zone to the active spray source.",
            reason="Near-field concentration depends on source-to-breathing-zone geometry.",
        ),
        TierUpgradeInputRequirement(
            fieldName="spray_duration_seconds",
            description="Active spray emission duration for each event.",
            reason="Short spray bursts can create transient peaks not captured by room averages.",
        ),
        TierUpgradeInputRequirement(
            fieldName="near_field_volume_m3",
            description="Local near-field control volume around the user.",
            reason="A Tier 1 split requires an explicit near-field compartment size.",
        ),
        TierUpgradeInputRequirement(
            fieldName="airflow_directionality",
            description="Directional airflow or ventilation context near the source.",
            reason="Local airflow governs coupling between near-field and far-field zones.",
        ),
        TierUpgradeInputRequirement(
            fieldName="particle_size_regime",
            description="Spray droplet or aerosol size regime used for screening.",
            reason="Spray behavior and local persistence depend on size-driven transport.",
        ),
    ]


def _relative_difference(actual: float, reference: float) -> float:
    if reference == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - reference) / abs(reference)


def _maybe_flag_missing_product_subtype(tracker: AssumptionTracker, profile) -> None:
    if profile.product_subtype is not None:
        return
    if profile.application_method not in TIER_1_SPRAY_METHODS:
        return
    if profile.product_category.lower() not in SUBTYPE_SENSITIVE_SPRAY_FAMILIES:
        return
    tracker.add_quality_flag(
        "product_subtype_missing_for_spray_family",
        (
            "The current spray scenario uses a broad product_category without a "
            "product_subtype. Provide a narrower subtype such as "
            "`indoor_surface_insecticide`, `crack_and_crevice_insecticide`, "
            "`air_space_insecticide`, or `surface_trigger_spray_disinfectant` to unlock "
            "more specific ConsExpo-aligned screening branches."
        ),
        severity=Severity.WARNING,
    )


def _first_order_average_concentration(
    initial_concentration_mg_per_m3: float,
    loss_rate_per_hour: float,
    duration_hours: float,
) -> float:
    if loss_rate_per_hour <= 0.0:
        return initial_concentration_mg_per_m3
    return initial_concentration_mg_per_m3 * (
        (1.0 - math.exp(-loss_rate_per_hour * duration_hours))
        / (loss_rate_per_hour * duration_hours)
    )


def _first_order_end_concentration(
    initial_concentration_mg_per_m3: float,
    loss_rate_per_hour: float,
    duration_hours: float,
) -> float:
    if loss_rate_per_hour <= 0.0:
        return initial_concentration_mg_per_m3
    return initial_concentration_mg_per_m3 * math.exp(-loss_rate_per_hour * duration_hours)


def _record_physchem_context(
    tracker: AssumptionTracker,
    physchem_context: PhyschemContext | None,
) -> None:
    if physchem_context is None:
        return
    if physchem_context.vapor_pressure_mmhg is not None:
        tracker.add_user(
            "vapor_pressure_mmhg",
            physchem_context.vapor_pressure_mmhg,
            "mmHg",
            (
                "Vapor pressure was supplied explicitly for bounded volatility-aware "
                "inhalation screening."
            ),
        )
    if physchem_context.molecular_weight_g_per_mol is not None:
        tracker.add_user(
            "molecular_weight_g_per_mol",
            physchem_context.molecular_weight_g_per_mol,
            "g/mol",
            (
                "Molecular weight was supplied explicitly for bounded volatility-aware "
                "inhalation screening."
            ),
        )
    if physchem_context.log_kow is not None:
        tracker.add_user(
            "log_kow",
            physchem_context.log_kow,
            "log10",
            "logKow was supplied explicitly for chemistry-aware screening context.",
        )
    if physchem_context.water_solubility_mg_per_l is not None:
        tracker.add_user(
            "water_solubility_mg_per_l",
            physchem_context.water_solubility_mg_per_l,
            "mg/L",
            "Water solubility was supplied explicitly for chemistry-aware screening context.",
        )


def _inhalation_saturation_cap_mg_per_m3(
    *,
    physchem_context: PhyschemContext | None,
    profile,
    registry: DefaultsRegistry,
    tracker: AssumptionTracker,
) -> float | None:
    if physchem_context is None:
        return None
    policy, source = registry.inhalation_saturation_cap_policy()
    if policy["skip_when_particle_material_context_present"] and (
        profile.particle_material_context is not None
    ):
        return None
    vapor_pressure = physchem_context.vapor_pressure_mmhg
    molecular_weight = physchem_context.molecular_weight_g_per_mol
    if vapor_pressure is None:
        return None
    if molecular_weight is None:
        tracker.add_quality_flag(
            "saturation_cap_molecular_weight_missing",
            (
                "physchemContext includes vaporPressureMmhg but not molecularWeightGPerMol, "
                "so the volatility saturation cap could not be activated."
            ),
            severity=Severity.WARNING,
        )
        return None

    reference_temperature_c = policy["reference_temperature_c"]
    saturation_cap = (
        (vapor_pressure / STANDARD_PRESSURE_MMHG)
        * STANDARD_PRESSURE_PA
        * molecular_weight
        / (IDEAL_GAS_CONSTANT_J_PER_MOL_K * STANDARD_TEMPERATURE_K)
        * 1000.0
    )
    tracker.add_default(
        "saturation_cap_reference_temperature_c",
        reference_temperature_c,
        "C",
        source,
        "Volatility saturation cap uses the governed room-temperature screening policy.",
    )
    tracker.add_default(
        "saturation_cap_mg_per_m3",
        saturation_cap,
        "mg/m3",
        source,
        (
            "Thermodynamic saturation ceiling derived from vapor pressure, molecular "
            "weight, and the governed room-temperature policy."
        ),
    )
    return saturation_cap


def _apply_saturation_cap(
    *,
    concentration_mg_per_m3: float,
    saturation_cap_mg_per_m3: float | None,
) -> tuple[float, bool]:
    if saturation_cap_mg_per_m3 is None:
        return concentration_mg_per_m3, False
    capped = min(concentration_mg_per_m3, saturation_cap_mg_per_m3)
    return capped, not math.isclose(capped, concentration_mg_per_m3, rel_tol=1e-9, abs_tol=1e-12)


def _extrathoracic_swallow_fraction(
    *,
    profile,
    registry: DefaultsRegistry,
    tracker: AssumptionTracker,
    particle_size_regime: str | None = None,
) -> float:
    if profile.application_method not in TIER_1_SPRAY_METHODS:
        return 0.0
    swallow_fraction, swallow_source = registry.inhalation_extrathoracic_swallow_fraction(
        particle_size_regime=particle_size_regime,
        application_method=profile.application_method,
        product_subtype=profile.product_subtype,
    )
    tracker.add_default(
        "extrathoracic_swallow_fraction",
        swallow_fraction,
        "fraction",
        swallow_source,
        (
            "Extrathoracic swallowed fraction defaulted from the bounded spray "
            "physiology handoff pack."
        ),
    )
    if swallow_fraction > 0.0:
        tracker.add_limitation(
            "extrathoracic_oral_handoff_screening",
            (
                "Spray inhalation includes a bounded extrathoracic swallowed-fraction "
                "estimate. This is not a full regional deposition model or an automatic "
                "oral handoff into a separate ingestion scenario."
            ),
        )
    return swallow_fraction


def _surface_emission_air_concentration(
    *,
    initial_surface_mass_mg: float,
    surface_emission_rate_per_hour: float,
    total_loss_rate_per_hour: float,
    room_volume_m3: float,
    elapsed_hours: float,
) -> float:
    if (
        initial_surface_mass_mg <= 0.0
        or surface_emission_rate_per_hour <= 0.0
        or room_volume_m3 <= 0.0
        or elapsed_hours <= 0.0
    ):
        return 0.0

    source_strength = surface_emission_rate_per_hour * initial_surface_mass_mg / room_volume_m3
    if math.isclose(
        surface_emission_rate_per_hour,
        total_loss_rate_per_hour,
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        return source_strength * elapsed_hours * math.exp(
            -surface_emission_rate_per_hour * elapsed_hours
        )

    return source_strength / (total_loss_rate_per_hour - surface_emission_rate_per_hour) * (
        math.exp(-surface_emission_rate_per_hour * elapsed_hours)
        - math.exp(-total_loss_rate_per_hour * elapsed_hours)
    )


def _surface_emission_average_concentration(
    *,
    initial_surface_mass_mg: float,
    surface_emission_rate_per_hour: float,
    total_loss_rate_per_hour: float,
    room_volume_m3: float,
    start_hours: float,
    duration_hours: float,
) -> float:
    if duration_hours <= 0.0:
        return _surface_emission_air_concentration(
            initial_surface_mass_mg=initial_surface_mass_mg,
            surface_emission_rate_per_hour=surface_emission_rate_per_hour,
            total_loss_rate_per_hour=total_loss_rate_per_hour,
            room_volume_m3=room_volume_m3,
            elapsed_hours=start_hours,
        )
    if (
        initial_surface_mass_mg <= 0.0
        or surface_emission_rate_per_hour <= 0.0
        or room_volume_m3 <= 0.0
    ):
        return 0.0

    end_hours = start_hours + duration_hours
    source_strength = surface_emission_rate_per_hour * initial_surface_mass_mg / room_volume_m3

    if math.isclose(total_loss_rate_per_hour, 0.0, abs_tol=1e-12):
        integral = initial_surface_mass_mg / room_volume_m3 * (
            duration_hours
            + (
                math.exp(-surface_emission_rate_per_hour * end_hours)
                - math.exp(-surface_emission_rate_per_hour * start_hours)
            )
            / surface_emission_rate_per_hour
        )
        return integral / duration_hours

    if math.isclose(
        surface_emission_rate_per_hour,
        total_loss_rate_per_hour,
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        def _primitive(time_hours: float) -> float:
            return -source_strength * (
                time_hours / surface_emission_rate_per_hour
                + 1.0 / (surface_emission_rate_per_hour**2)
            ) * math.exp(-surface_emission_rate_per_hour * time_hours)

        return (_primitive(end_hours) - _primitive(start_hours)) / duration_hours

    integral = source_strength / (total_loss_rate_per_hour - surface_emission_rate_per_hour) * (
        (
            math.exp(-surface_emission_rate_per_hour * start_hours)
            - math.exp(-surface_emission_rate_per_hour * end_hours)
        )
        / surface_emission_rate_per_hour
        - (
            math.exp(-total_loss_rate_per_hour * start_hours)
            - math.exp(-total_loss_rate_per_hour * end_hours)
        )
        / total_loss_rate_per_hour
    )
    return integral / duration_hours


def _tier_1_profile_alignment(
    request: InhalationTier1ScenarioRequest,
    matched_profile,
) -> tuple[str, list[str]]:
    if matched_profile is None:
        return "no_profile_match", []

    divergences: list[str] = []

    if request.airflow_directionality != matched_profile.recommended_airflow_directionality:
        divergences.append(
            "airflow_directionality="
            f"{request.airflow_directionality.value} differs from recommended "
            f"{matched_profile.recommended_airflow_directionality.value}"
        )
    if request.particle_size_regime != matched_profile.recommended_particle_size_regime:
        divergences.append(
            "particle_size_regime="
            f"{request.particle_size_regime.value} differs from recommended "
            f"{matched_profile.recommended_particle_size_regime.value}"
        )

    numeric_pairs = (
        (
            "source_distance_m",
            request.source_distance_m,
            matched_profile.default_source_distance_m,
            "m",
        ),
        (
            "near_field_volume_m3",
            request.near_field_volume_m3,
            matched_profile.recommended_near_field_volume_m3,
            "m3",
        ),
        (
            "spray_duration_seconds",
            request.spray_duration_seconds,
            matched_profile.default_spray_duration_seconds,
            "s",
        ),
    )
    for name, actual, recommended, unit in numeric_pairs:
        tolerance = TIER_1_PROFILE_NUMERIC_TOLERANCES[name]
        if _relative_difference(actual, recommended) > tolerance:
            divergences.append(
                f"{name}={actual:g} {unit} differs materially from recommended "
                f"{recommended:g} {unit}"
            )

    return ("divergent" if divergences else "aligned"), divergences


def _build_inhalation_tier_1_two_zone_scenario(
    request: InhalationTier1ScenarioRequest,
    registry: DefaultsRegistry,
    *,
    profile_registry: Tier1InhalationProfileRegistry | None = None,
    generated_at: str | None = None,
) -> ExposureScenario:
    tracker = AssumptionTracker(registry=registry)
    tracker.set_context(
        route=request.route.value,
        scenario_class=request.scenario_class.value,
        product_category=request.product_use_profile.product_category,
        product_subtype=request.product_use_profile.product_subtype,
        physical_form=request.product_use_profile.physical_form,
        application_method=request.product_use_profile.application_method,
        retention_type=request.product_use_profile.retention_type,
        population_group=request.population_profile.population_group,
        demographic_tags=",".join(request.population_profile.demographic_tags),
        region=request.population_profile.region,
    )
    profile = request.product_use_profile
    population = request.population_profile
    tier_1_registry = profile_registry or Tier1InhalationProfileRegistry.load()
    airflow_profile = tier_1_registry.airflow_profile(request.airflow_directionality)
    matched_profiles = tier_1_registry.matching_profiles(
        product_family=profile.product_category,
        application_method=profile.application_method,
        product_subtype=profile.product_subtype,
    )
    matched_profile = matched_profiles[0] if matched_profiles else None
    profile_alignment_status, profile_divergences = _tier_1_profile_alignment(
        request,
        matched_profile,
    )

    product_mass_g_event = resolve_product_mass_g(
        profile,
        registry,
        tracker,
        physchem_context=request.physchem_context,
    )
    chemical_mass_mg_event = grams_to_mg(product_mass_g_event) * profile.concentration_fraction
    tracker.add_user(
        "concentration_fraction",
        profile.concentration_fraction,
        "fraction",
        "Chemical fraction in the product was supplied explicitly.",
    )
    tracker.add_user(
        "use_events_per_day",
        profile.use_events_per_day,
        "events/day",
        "Use frequency was supplied explicitly.",
    )
    tracker.add_derived(
        "chemical_mass_mg_per_event",
        chemical_mass_mg_event,
        "mg/event",
        "Product mass per event multiplied by concentration fraction.",
    )

    if profile.aerosolized_fraction is not None:
        aerosolized_fraction = profile.aerosolized_fraction
        tracker.add_user(
            "aerosolized_fraction",
            aerosolized_fraction,
            "fraction",
            "Aerosolized fraction was supplied explicitly.",
        )
    else:
        aerosolized_fraction, source = registry.aerosolized_fraction(
            profile.application_method,
            profile.product_category,
            profile.product_subtype,
        )
        tracker.add_default(
            "aerosolized_fraction",
            aerosolized_fraction,
            "fraction",
            source,
            (
                "Aerosolized fraction defaulted from "
                f"application_method='{profile.application_method}' and "
                f"product_category='{profile.product_category}'"
                + (
                    f" and product_subtype='{profile.product_subtype}'."
                    if profile.product_subtype
                    else "."
                )
            ),
        )
    _maybe_flag_missing_product_subtype(tracker, profile)

    room_defaults, room_sources = registry.room_defaults(
        population.region,
        product_category=profile.product_category,
        product_subtype=profile.product_subtype,
        application_method=profile.application_method,
    )
    room_volume_m3 = profile.room_volume_m3
    if room_volume_m3 is None:
        room_volume_m3 = room_defaults["room_volume_m3"]
        tracker.add_default(
            "room_volume_m3",
            room_volume_m3,
            "m3",
            room_sources["room_volume_m3"],
            "Room volume defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "room_volume_m3", room_volume_m3, "m3", "Room volume was supplied explicitly."
        )

    air_exchange = profile.air_exchange_rate_per_hour
    if air_exchange is None:
        air_exchange = room_defaults["air_exchange_rate_per_hour"]
        tracker.add_default(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            room_sources["air_exchange_rate_per_hour"],
            "Air exchange rate defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            "Air exchange rate was supplied explicitly.",
        )

    exposure_duration_hours = profile.exposure_duration_hours
    if exposure_duration_hours is None:
        exposure_duration_hours = room_defaults["exposure_duration_hours"]
        tracker.add_default(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            room_sources["exposure_duration_hours"],
            "Exposure duration defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            "Exposure duration was supplied explicitly.",
        )

    inhalation_rate = resolve_population_value(
        field_name="inhalation_rate_m3_per_hour",
        supplied_value=population.inhalation_rate_m3_per_hour,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="m3/h",
        rationale="Inhalation rate was supplied explicitly.",
        gt=0.0,
    )
    body_weight_kg = resolve_population_value(
        field_name="body_weight_kg",
        supplied_value=population.body_weight_kg,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="kg",
        rationale="Body weight was supplied explicitly for dose normalization.",
        gt=0.0,
    )
    _record_physchem_context(tracker, request.physchem_context)

    tracker.add_user(
        "source_distance_m",
        request.source_distance_m,
        "m",
        "Tier 1 source distance was supplied explicitly.",
    )
    tracker.add_user(
        "spray_duration_seconds",
        request.spray_duration_seconds,
        "s",
        "Tier 1 active spray duration was supplied explicitly.",
    )
    tracker.add_user(
        "near_field_volume_m3",
        request.near_field_volume_m3,
        "m3",
        "Tier 1 near-field volume was supplied explicitly.",
    )
    tracker.add_user(
        "airflow_directionality",
        request.airflow_directionality.value,
        None,
        "Tier 1 airflow directionality class was supplied explicitly.",
    )
    tracker.add_user(
        "particle_size_regime",
        request.particle_size_regime.value,
        None,
        "Tier 1 particle-size regime was supplied explicitly.",
    )

    spray_duration_hours = request.spray_duration_seconds / 3600.0
    if spray_duration_hours > exposure_duration_hours:
        raise ExposureScenarioError(
            code="inhalation_tier_1_duration_inconsistent",
            message=(
                "Tier 1 spray_duration_seconds cannot exceed the resolved exposure duration."
            ),
            suggestion=(
                "Shorten spray_duration_seconds or provide a longer exposure_duration_hours "
                "for the inhalation event."
            ),
            details={
                "sprayDurationSeconds": request.spray_duration_seconds,
                "exposureDurationHours": exposure_duration_hours,
            },
        )
    if request.near_field_volume_m3 >= room_volume_m3:
        raise ExposureScenarioError(
            code="inhalation_tier_1_near_field_volume_invalid",
            message=(
                "Tier 1 near_field_volume_m3 must be smaller than the resolved room volume."
            ),
            suggestion=(
                "Provide a near-field compartment smaller than room_volume_m3 so a far-field "
                "zone remains available."
            ),
            details={
                "nearFieldVolumeM3": request.near_field_volume_m3,
                "roomVolumeM3": room_volume_m3,
            },
        )

    released_mass_mg_event = chemical_mass_mg_event * aerosolized_fraction
    far_field_volume_m3 = room_volume_m3 - request.near_field_volume_m3

    deposition_rate, deposition_source = registry.inhalation_deposition_rate_per_hour(
        particle_size_regime=request.particle_size_regime.value,
        application_method=profile.application_method,
        physical_form=profile.physical_form,
        product_subtype=profile.product_subtype,
    )
    tracker.add_default(
        "deposition_rate_per_hour",
        deposition_rate,
        "1/h",
        deposition_source,
        "Deposition sink defaulted from the bounded inhalation physical-caps pack.",
    )

    if request.near_field_loss_rate_per_hour is not None:
        k_nf = request.near_field_loss_rate_per_hour
        tracker.add_user(
            "near_field_loss_rate_per_hour",
            k_nf,
            "1/h",
            "Near-field loss rate was supplied explicitly.",
        )
    else:
        k_nf = deposition_rate
        tracker.add_default(
            "near_field_loss_rate_per_hour",
            k_nf,
            "1/h",
            deposition_source,
            "Near-field loss rate defaulted to the packaged deposition rate.",
        )

    if request.far_field_loss_rate_per_hour is not None:
        k_ff = request.far_field_loss_rate_per_hour
        tracker.add_user(
            "far_field_loss_rate_per_hour",
            k_ff,
            "1/h",
            "Far-field loss rate was supplied explicitly.",
        )
    else:
        k_ff = deposition_rate
        tracker.add_default(
            "far_field_loss_rate_per_hour",
            k_ff,
            "1/h",
            deposition_source,
            "Far-field loss rate defaulted to the packaged deposition rate.",
        )

    q_room = air_exchange * room_volume_m3
    tracker.add_derived(
        "room_ventilation_flow_rate_m3_per_hour",
        q_room,
        "m3/h",
        "Room ventilation flow = air_exchange_rate_per_hour x room_volume_m3.",
    )

    phi = request.ventilation_allocation_to_near_field_fraction
    if phi is None:
        phi = 0.0
        tracker.add_default(
            "ventilation_allocation_to_near_field_fraction",
            phi,
            "fraction",
            tier_1_registry.source_reference(airflow_profile.source_id),
            (
                "Default production simplification assigns all room ventilation "
                "to the far-field (phi = 0.0)."
            ),
        )
    else:
        tracker.add_user(
            "ventilation_allocation_to_near_field_fraction",
            phi,
            "fraction",
            "Ventilation allocation to the near-field was supplied explicitly.",
        )

    lambda_nf = k_nf + phi * q_room / request.near_field_volume_m3
    lambda_ff = k_ff + (1.0 - phi) * q_room / far_field_volume_m3

    near_field_exchange_turnover = airflow_profile.exchange_turnover_per_hour
    local_entrainment_rates, local_entrainment_sources = registry.tier1_local_entrainment_rates(
        application_method=profile.application_method
    )
    thermal_plume_rate = local_entrainment_rates["thermal_plume_rate_m3_per_hour"]
    spray_jet_rate = local_entrainment_rates["spray_jet_rate_m3_per_hour"]
    local_entrainment_rate = local_entrainment_rates["local_entrainment_rate_m3_per_hour"]

    if request.interzonal_flow_rate_m3_per_hour is not None:
        beta = request.interzonal_flow_rate_m3_per_hour
        tracker.add_user(
            "interzonal_flow_rate_m3_per_hour",
            beta,
            "m3/h",
            "Interzonal flow rate was supplied explicitly.",
        )
        interzonal_mixing_floor_applied = False
    else:
        static_interzonal_mixing_rate = request.near_field_volume_m3 * near_field_exchange_turnover
        interzonal_mixing_floor_applied = static_interzonal_mixing_rate < local_entrainment_rate
        beta = max(static_interzonal_mixing_rate, local_entrainment_rate)
        tracker.add_default(
            "near_field_exchange_turnover_per_hour",
            near_field_exchange_turnover,
            "1/h",
            tier_1_registry.source_reference(airflow_profile.source_id),
            "Tier 1 screening turnover resolved from the packaged airflow-directionality profile.",
        )
        tracker.add_default(
            "thermal_plume_rate_m3_per_hour",
            thermal_plume_rate,
            "m3/h",
            local_entrainment_sources["thermal_plume_rate_m3_per_hour"],
            "Tier 1 local entrainment floor includes a bounded thermal-plume entrainment term.",
        )
        tracker.add_default(
            "spray_jet_rate_m3_per_hour",
            spray_jet_rate,
            "m3/h",
            local_entrainment_sources["spray_jet_rate_m3_per_hour"],
            (
                "Tier 1 local entrainment floor includes a bounded spray-jet entrainment term "
                "resolved from application method."
            ),
        )
        tracker.add_derived(
            "static_interzonal_mixing_rate_m3_per_hour",
            static_interzonal_mixing_rate,
            "m3/h",
            "Static interzonal mixing rate = near-field volume x screening exchange turnover.",
        )
        tracker.add_derived(
            "local_entrainment_rate_m3_per_hour",
            local_entrainment_rate,
            "m3/h",
            (
                "Bounded local entrainment floor = thermal-plume entrainment + "
                "application-method spray-jet entrainment."
            ),
        )
        tracker.add_derived(
            "interzonal_mixing_floor_applied",
            interzonal_mixing_floor_applied,
            None,
            "Whether the bounded local entrainment floor exceeded the static Tier 1 "
            "interzonal rate.",
        )

    tracker.add_derived(
        "interzonal_flow_rate_m3_per_hour",
        beta,
        "m3/h",
        "Resolved bidirectional interzonal airflow for the two-zone model.",
    )

    source_fraction_to_nf = request.source_allocation_to_near_field_fraction
    if source_fraction_to_nf is None:
        if (
            matched_profile is not None
            and matched_profile.source_fraction_to_nf_default is not None
        ):
            source_fraction_to_nf = matched_profile.source_fraction_to_nf_default
            tracker.add_default(
                "source_fraction_to_near_field",
                source_fraction_to_nf,
                "fraction",
                tier_1_registry.source_reference(matched_profile.source_id),
                "Default source-to-NF fraction from the matched product profile.",
            )
        else:
            source_fraction_to_nf = 1.0
            tracker.add_default(
                "source_fraction_to_near_field",
                1.0,
                "fraction",
                tier_1_registry.source_reference(airflow_profile.source_id),
                "Default production simplification places the entire source in the "
                "near-field (eta = 1.0).",
            )
    else:
        tracker.add_user(
            "source_fraction_to_near_field",
            source_fraction_to_nf,
            "fraction",
            "Source allocation to the near-field was supplied explicitly.",
        )

    saturation_cap_mg_per_m3 = _inhalation_saturation_cap_mg_per_m3(
        physchem_context=request.physchem_context,
        profile=profile,
        registry=registry,
        tracker=tracker,
    )
    saturation_cap_applied = False

    emission_rate_mg_per_hour = released_mass_mg_event / spray_duration_hours
    tz_params = TwoZoneParams(
        v_nf_m3=request.near_field_volume_m3,
        v_ff_m3=far_field_volume_m3,
        beta_m3_per_hour=beta,
        lambda_nf_per_hour=lambda_nf,
        lambda_ff_per_hour=lambda_ff,
        source_fraction_to_nf=source_fraction_to_nf,
    )
    tz_result = solve_two_zone_piecewise_constant(
        params=tz_params,
        emission_rate_mg_per_hour=emission_rate_mg_per_hour,
        spray_duration_hours=spray_duration_hours,
        total_duration_hours=exposure_duration_hours,
        q_room_m3_per_hour=q_room,
        k_nf_per_hour=k_nf,
        k_ff_per_hour=k_ff,
        ventilation_allocation_to_near_field_fraction=phi,
    )

    if (
        saturation_cap_mg_per_m3 is not None
        and tz_result.near_field_peak_concentration_mg_per_m3 > saturation_cap_mg_per_m3
    ):
        tracker.add_quality_flag(
            "two_zone_volatility_consistency_warning",
            (
                f"The uncapped near-field peak concentration "
                f"({tz_result.near_field_peak_concentration_mg_per_m3:.4f} mg/m3) exceeds the "
                f"thermodynamic saturation ceiling ({saturation_cap_mg_per_m3:.4f} mg/m3)."
            ),
            severity=Severity.WARNING,
        )

    inhaled_mass_mg_per_event = inhalation_rate * tz_result.near_field_time_integral_mg_h_per_m3
    inhaled_mass_mg_day = inhaled_mass_mg_per_event * profile.use_events_per_day
    extrathoracic_swallow_fraction = _extrathoracic_swallow_fraction(
        profile=profile,
        registry=registry,
        tracker=tracker,
        particle_size_regime=request.particle_size_regime.value,
    )
    swallowed_extrathoracic_mass_mg_day = inhaled_mass_mg_day * extrathoracic_swallow_fraction
    lower_respiratory_inhaled_mass_mg_day = (
        inhaled_mass_mg_day - swallowed_extrathoracic_mass_mg_day
    )
    normalized_dose = inhaled_mass_mg_day / body_weight_kg

    if far_field_volume_m3 / room_volume_m3 < 0.01:
        tracker.add_quality_flag(
            "two_zone_far_field_volume_small",
            (
                "The far-field control volume is less than 1% of the room volume, "
                "which can make the two-zone partitioning numerically sensitive."
            ),
            severity=Severity.WARNING,
        )

    route_metrics: dict[str, float | str | bool | None] = {
        "chemical_mass_mg_per_event": round(chemical_mass_mg_event, 8),
        "released_mass_mg_per_event": round(released_mass_mg_event, 8),
        "far_field_volume_m3": round(far_field_volume_m3, 8),
        "room_ventilation_flow_rate_m3_per_hour": round(q_room, 8),
        "interzonal_flow_rate_m3_per_hour": round(beta, 8),
        "near_field_loss_rate_per_hour": round(k_nf, 8),
        "far_field_loss_rate_per_hour": round(k_ff, 8),
        "source_fraction_to_near_field": round(source_fraction_to_nf, 8),
        "ventilation_fraction_to_near_field": round(phi, 8),
        "deposition_rate_per_hour": round(deposition_rate, 8),
        "saturation_cap_mg_per_m3": (
            round(saturation_cap_mg_per_m3, 8) if saturation_cap_mg_per_m3 is not None else None
        ),
        "saturation_cap_applied": saturation_cap_applied,
        "far_field_average_air_concentration_mg_per_m3": round(
            tz_result.far_field_average_concentration_mg_per_m3, 8
        ),
        "uncapped_far_field_average_air_concentration_mg_per_m3": round(
            tz_result.far_field_average_concentration_mg_per_m3, 8
        ),
        "near_field_average_concentration_mg_per_m3": round(
            tz_result.near_field_average_concentration_mg_per_m3, 8
        ),
        "near_field_peak_concentration_mg_per_m3": round(
            tz_result.near_field_peak_concentration_mg_per_m3, 8
        ),
        "near_field_end_concentration_mg_per_m3": round(
            tz_result.near_field_end_concentration_mg_per_m3, 8
        ),
        "far_field_peak_concentration_mg_per_m3": round(
            tz_result.far_field_peak_concentration_mg_per_m3, 8
        ),
        "far_field_end_concentration_mg_per_m3": round(
            tz_result.far_field_end_concentration_mg_per_m3, 8
        ),
        "initial_air_concentration_mg_per_m3": 0.0,
        "air_concentration_at_event_end_mg_per_m3": round(
            tz_result.near_field_end_concentration_mg_per_m3, 8
        ),
        "near_field_time_integral_mg_h_per_m3": round(
            tz_result.near_field_time_integral_mg_h_per_m3, 8
        ),
        "far_field_time_integral_mg_h_per_m3": round(
            tz_result.far_field_time_integral_mg_h_per_m3, 8
        ),
        "average_air_concentration_mg_per_m3": round(
            tz_result.near_field_average_concentration_mg_per_m3, 8
        ),
        "uncapped_average_air_concentration_mg_per_m3": round(
            tz_result.near_field_average_concentration_mg_per_m3, 8
        ),
        "breathing_zone_time_weighted_average_mg_per_m3": round(
            tz_result.near_field_average_concentration_mg_per_m3, 8
        ),
        "mass_balance_residual_mg": round(tz_result.mass_balance_residual_mg, 8),
        "inhaled_mass_mg_per_event": round(inhaled_mass_mg_per_event, 8),
        "inhaled_mass_mg_per_day": round(inhaled_mass_mg_day, 8),
        "extrathoracic_swallow_fraction": round(extrathoracic_swallow_fraction, 8),
        "swallowed_extrathoracic_mass_mg_per_day": round(
            swallowed_extrathoracic_mass_mg_day, 8
        ),
        "lower_respiratory_inhaled_mass_mg_per_day": round(
            lower_respiratory_inhaled_mass_mg_day, 8
        ),
        "tier1_product_profile_id": matched_profile.profile_id if matched_profile else None,
        "tier1_profile_alignment_status": profile_alignment_status,
        "tier1_profile_divergence_count": len(profile_divergences),
        "two_zone_solver_active": True,
        "solver_variant": "two_zone_v1",
    }
    if request.physchem_context is not None:
        if request.physchem_context.vapor_pressure_mmhg is not None:
            route_metrics["vapor_pressure_mmhg"] = round(
                request.physchem_context.vapor_pressure_mmhg, 8
            )
        if request.physchem_context.molecular_weight_g_per_mol is not None:
            route_metrics["molecular_weight_g_per_mol"] = round(
                request.physchem_context.molecular_weight_g_per_mol, 8
            )

    tracker.add_derived(
        "released_mass_mg_per_event",
        released_mass_mg_event,
        "mg/event",
        "Released mass = chemical mass per event x aerosolized fraction.",
    )
    tracker.add_derived(
        "spray_duration_hours",
        spray_duration_hours,
        "h",
        "Converted Tier 1 spray duration from seconds into hours.",
    )
    tracker.add_derived(
        "far_field_volume_m3",
        far_field_volume_m3,
        "m3",
        "Far-field volume = room volume minus near-field volume.",
    )
    tracker.add_derived(
        "emission_rate_mg_per_hour",
        emission_rate_mg_per_hour,
        "mg/h",
        "Constant mass emission rate into air during the active spray phase.",
    )
    tracker.add_derived(
        "lambda_nf_per_hour",
        lambda_nf,
        "1/h",
        "Near-field total loss rate = deposition + allocated ventilation.",
    )
    tracker.add_derived(
        "lambda_ff_per_hour",
        lambda_ff,
        "1/h",
        "Far-field total loss rate = deposition + allocated ventilation.",
    )
    tracker.add_derived(
        "far_field_average_air_concentration_mg_per_m3",
        tz_result.far_field_average_concentration_mg_per_m3,
        "mg/m3",
        "Far-field time-average concentration from the two-zone solver.",
    )
    tracker.add_derived(
        "near_field_average_concentration_mg_per_m3",
        tz_result.near_field_average_concentration_mg_per_m3,
        "mg/m3",
        "Near-field time-average concentration from the two-zone solver.",
    )
    tracker.add_derived(
        "near_field_peak_concentration_mg_per_m3",
        tz_result.near_field_peak_concentration_mg_per_m3,
        "mg/m3",
        "Near-field peak concentration at end-of-spray from the two-zone solver.",
    )
    tracker.add_derived(
        "near_field_end_concentration_mg_per_m3",
        tz_result.near_field_end_concentration_mg_per_m3,
        "mg/m3",
        "Near-field concentration at end-of-event from the two-zone solver.",
    )
    tracker.add_derived(
        "far_field_peak_concentration_mg_per_m3",
        tz_result.far_field_peak_concentration_mg_per_m3,
        "mg/m3",
        "Far-field peak concentration at end-of-spray from the two-zone solver.",
    )
    tracker.add_derived(
        "far_field_end_concentration_mg_per_m3",
        tz_result.far_field_end_concentration_mg_per_m3,
        "mg/m3",
        "Far-field concentration at end-of-event from the two-zone solver.",
    )
    tracker.add_derived(
        "near_field_time_integral_mg_h_per_m3",
        tz_result.near_field_time_integral_mg_h_per_m3,
        "mg*h/m3",
        "Time-integrated near-field concentration from the two-zone solver.",
    )
    tracker.add_derived(
        "far_field_time_integral_mg_h_per_m3",
        tz_result.far_field_time_integral_mg_h_per_m3,
        "mg*h/m3",
        "Time-integrated far-field concentration from the two-zone solver.",
    )
    tracker.add_derived(
        "mass_balance_residual_mg",
        tz_result.mass_balance_residual_mg,
        "mg",
        "Algebraic mass-balance residual checked against emitted, final, ventilation, "
        "and deposition masses.",
    )
    tracker.add_derived(
        "inhaled_mass_mg_per_event",
        inhaled_mass_mg_per_event,
        "mg/event",
        "Inhaled mass per event = inhalation rate x near-field time integral.",
    )
    tracker.add_derived(
        "inhaled_mass_mg_per_day",
        inhaled_mass_mg_day,
        "mg/day",
        "Daily inhaled mass equals inhaled mass per event multiplied by events/day.",
    )
    tracker.add_derived(
        "swallowed_extrathoracic_mass_mg_per_day",
        swallowed_extrathoracic_mass_mg_day,
        "mg/day",
        "Extrathoracic swallowed mass per day derived from the bounded swallowed fraction.",
    )
    tracker.add_derived(
        "lower_respiratory_inhaled_mass_mg_per_day",
        lower_respiratory_inhaled_mass_mg_day,
        "mg/day",
        "Lower-respiratory inhaled mass per day after subtracting the extrathoractic "
        "swallowed share.",
    )
    tracker.add_derived(
        "normalized_external_dose_mg_per_kg_day",
        normalized_dose,
        "mg/kg-day",
        "Normalized external dose = inhaled mass per day / body weight.",
    )

    tracker.add_quality_flag(
        "two_zone_mass_balance_active",
        "Tier 1 inhalation was executed with a deterministic two-zone mass-balance solver.",
        severity=Severity.INFO,
    )
    if request.interzonal_flow_rate_m3_per_hour is not None:
        tracker.add_quality_flag(
            "two_zone_user_beta_override",
            "The user supplied an explicit interzonal_flow_rate_m3_per_hour override.",
            severity=Severity.INFO,
        )
    if source_fraction_to_nf < 1.0:
        tracker.add_quality_flag(
            "two_zone_source_outside_nf_volume",
            "A fraction of the source was allocated to the far-field (eta < 1.0).",
            severity=Severity.INFO,
        )
    if matched_profile is not None and profile_divergences:
        tracker.add_quality_flag(
            "tier1_profile_anchor_divergence",
            (
                "Caller-supplied Tier 1 inputs diverge materially from the matched packaged "
                f"profile `{matched_profile.profile_id}`: " + "; ".join(profile_divergences) + "."
            ),
            severity=Severity.WARNING,
        )
    if matched_profile is None:
        tracker.add_quality_flag(
            "tier1_profile_no_packaged_match",
            (
                "No packaged Tier 1 profile matched the current product family and application "
                "method"
                + (
                    f" for product_subtype='{profile.product_subtype}'"
                    if profile.product_subtype
                    else ""
                )
                + "; screening geometry and regime inputs remain fully caller-defined."
            ),
            severity=Severity.INFO,
        )

    tracker.add_limitation(
        "two_zone_deterministic_solver",
        (
            "Tier 1 two-zone uses an exact analytical solution to a deterministic 2x2 linear "
            "ODE system. It does not resolve droplet evaporation, polydisperse aerosol dynamics, "
            "or directional jet geometry."
        ),
    )
    if interzonal_mixing_floor_applied:
        tracker.add_limitation(
            "tier1_local_entrainment_floor_screening",
            (
                "Tier 1 NF/FF applied a bounded local entrainment floor from thermal-plume and "
                "spray-jet heuristics because the static interzonal rate was weaker. This is a "
                "screening lower bound on local mixing, not a measured plume or jet-resolved "
                "airflow profile."
            ),
        )
    tracker.add_limitation(
        "particle_regime_screening",
        (
            "Particle-size effects use bounded screening persistence and deposition terms and "
            "do not model droplet evaporation or full aerosol dynamics."
        ),
    )

    scenario = ExposureScenario(
        scenario_id=f"inh-tier1-2z-{uuid4().hex[:10]}",
        chemical_id=request.chemical_id,
        chemical_name=request.chemical_name,
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        external_dose=ScenarioDose(
            metric="normalized_external_dose",
            value=round(normalized_dose, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        ),
        product_use_profile=profile.model_copy(
            update={"exposure_duration_hours": exposure_duration_hours}
        ),
        population_profile=population.model_copy(
            update={
                "body_weight_kg": body_weight_kg,
                "inhalation_rate_m3_per_hour": inhalation_rate,
            }
        ),
        route_metrics=route_metrics,
        assumptions=tracker.assumptions,
        provenance=tracker.provenance(
            plugin_id="inhalation_tier_1_two_zone_service",
            algorithm_id="inhalation.two_zone.v1",
            generated_at=generated_at,
        ),
        limitations=tracker.limitations,
        quality_flags=tracker.quality_flags,
        fit_for_purpose=tracker.fit_for_purpose("inhalation_tier_1_two_zone"),
        tier_semantics=tracker.tier_semantics(
            tier_claimed=TierLevel.TIER_1,
            tier_rationale=(
                "Inhalation output uses a deterministic mass-conserving two-zone "
                "near-field/far-field solver for spray events with explicit geometry and "
                "airflow-class inputs."
            ),
            required_caveats=[
                "Interpret the near-field compartment as a governed screening construct rather "
                "than a measured CFD domain.",
                "The airflow directionality and particle regime terms remain screening "
                "classifications, not measured aerosol dynamics.",
                "Very weak static interzonal mixing can be bounded upward by a local "
                "entrainment floor from thermal-plume and spray-jet heuristics.",
                "The two-zone solver assumes a well-mixed near-field control volume and does "
                "not resolve directional jet cones or body wakes.",
            ],
            forbidden_interpretations=[
                "Do not interpret this result as deposited dose, absorbed dose, or a PBPK state.",
                "Do not treat the screening exchange mapping as a validated transient aerosol "
                "dispersion model.",
                "Do not treat the result as a final risk conclusion.",
            ],
        ),
        interpretation_notes=[
            "Deterministic Tier 1 inhalation scenario with a mass-conserving two-zone "
            "near-field/far-field model.",
            "The breathing-zone concentration equals the near-field concentration for the full "
            "event duration.",
            *(
                [
                    "Matched packaged Tier 1 screening profile "
                    f"`{matched_profile.profile_id}`; caller-supplied Tier 1 geometry and "
                    "regime inputs remain authoritative."
                ]
                if matched_profile is not None
                else []
            ),
            *(
                [
                    "Tier 1 profile alignment warning: " + "; ".join(profile_divergences) + "."
                ]
                if profile_divergences
                else []
            ),
            *(
                [
                    "No packaged Tier 1 profile matched this product family/application "
                    "method combination."
                ]
                if matched_profile is None
                else []
            ),
        ],
        tierUpgradeAdvisories=[],
    )
    return apply_worker_task_semantics(scenario, request, registry=registry)


def _can_auto_select_two_zone(
    request: InhalationTier1ScenarioRequest,
    matched_profile,
    saturation_cap_applied: bool,
) -> bool:
    """Return True only when all migration gating conditions are satisfied."""
    if request.product_use_profile.application_method not in TIER_1_SPRAY_METHODS:
        return False
    if saturation_cap_applied:
        return False
    return matched_profile is not None and matched_profile.supports_two_zone


def build_inhalation_tier_1_screening_scenario(
    request: InhalationTier1ScenarioRequest,
    registry: DefaultsRegistry,
    *,
    profile_registry: Tier1InhalationProfileRegistry | None = None,
    generated_at: str | None = None,
) -> ExposureScenario:
    variant = request.solver_variant
    if variant == "auto":
        tier_1_registry = profile_registry or Tier1InhalationProfileRegistry.load()
        matched_profiles = tier_1_registry.matching_profiles(
            product_family=request.product_use_profile.product_category,
            application_method=request.product_use_profile.application_method,
            product_subtype=request.product_use_profile.product_subtype,
        )
        matched_profile = matched_profiles[0] if matched_profiles else None
        # Note: saturation_cap_applied is not known yet here; we conservatively
        # assume False for the auto gate. The two-zone builder will re-evaluate.
        if TIER1_TWO_ZONE_AUTO_ENABLED and _can_auto_select_two_zone(
            request, matched_profile, saturation_cap_applied=False
        ):
            variant = "two_zone_v1"
        else:
            variant = "heuristic_v1"
    if variant == "two_zone_v1":
        return _build_inhalation_tier_1_two_zone_scenario(
            request, registry, profile_registry=profile_registry, generated_at=generated_at
        )
    return _build_inhalation_tier_1_heuristic_scenario(
        request,
        registry,
        profile_registry=profile_registry,
        generated_at=generated_at,
        fallback_variant="auto" if request.solver_variant == "auto" else None,
    )


def _build_inhalation_tier_1_heuristic_scenario(
    request: InhalationTier1ScenarioRequest,
    registry: DefaultsRegistry,
    *,
    profile_registry: Tier1InhalationProfileRegistry | None = None,
    generated_at: str | None = None,
    fallback_variant: str | None = None,
) -> ExposureScenario:
    tracker = AssumptionTracker(registry=registry)
    tracker.set_context(
        route=request.route.value,
        scenario_class=request.scenario_class.value,
        product_category=request.product_use_profile.product_category,
        product_subtype=request.product_use_profile.product_subtype,
        physical_form=request.product_use_profile.physical_form,
        application_method=request.product_use_profile.application_method,
        retention_type=request.product_use_profile.retention_type,
        population_group=request.population_profile.population_group,
        demographic_tags=",".join(request.population_profile.demographic_tags),
        region=request.population_profile.region,
    )
    profile = request.product_use_profile
    population = request.population_profile
    tier_1_registry = profile_registry or Tier1InhalationProfileRegistry.load()
    airflow_profile = tier_1_registry.airflow_profile(request.airflow_directionality)
    particle_profile = tier_1_registry.particle_profile(request.particle_size_regime)
    matched_profiles = tier_1_registry.matching_profiles(
        product_family=profile.product_category,
        application_method=profile.application_method,
        product_subtype=profile.product_subtype,
    )
    matched_profile = matched_profiles[0] if matched_profiles else None
    profile_alignment_status, profile_divergences = _tier_1_profile_alignment(
        request,
        matched_profile,
    )

    product_mass_g_event = resolve_product_mass_g(
        profile,
        registry,
        tracker,
        physchem_context=request.physchem_context,
    )
    chemical_mass_mg_event = grams_to_mg(product_mass_g_event) * profile.concentration_fraction
    tracker.add_user(
        "concentration_fraction",
        profile.concentration_fraction,
        "fraction",
        "Chemical fraction in the product was supplied explicitly.",
    )
    tracker.add_user(
        "use_events_per_day",
        profile.use_events_per_day,
        "events/day",
        "Use frequency was supplied explicitly.",
    )
    tracker.add_derived(
        "chemical_mass_mg_per_event",
        chemical_mass_mg_event,
        "mg/event",
        "Product mass per event multiplied by concentration fraction.",
    )

    if profile.aerosolized_fraction is not None:
        aerosolized_fraction = profile.aerosolized_fraction
        tracker.add_user(
            "aerosolized_fraction",
            aerosolized_fraction,
            "fraction",
            "Aerosolized fraction was supplied explicitly.",
        )
    else:
        aerosolized_fraction, source = registry.aerosolized_fraction(
            profile.application_method,
            profile.product_category,
            profile.product_subtype,
        )
        tracker.add_default(
            "aerosolized_fraction",
            aerosolized_fraction,
            "fraction",
            source,
            (
                "Aerosolized fraction defaulted from "
                f"application_method='{profile.application_method}' and "
                f"product_category='{profile.product_category}'"
                + (
                    f" and product_subtype='{profile.product_subtype}'."
                    if profile.product_subtype
                    else "."
                )
            ),
        )
    _maybe_flag_missing_product_subtype(tracker, profile)

    room_defaults, room_sources = registry.room_defaults(
        population.region,
        product_category=profile.product_category,
        product_subtype=profile.product_subtype,
        application_method=profile.application_method,
    )
    room_volume_m3 = profile.room_volume_m3
    if room_volume_m3 is None:
        room_volume_m3 = room_defaults["room_volume_m3"]
        tracker.add_default(
            "room_volume_m3",
            room_volume_m3,
            "m3",
            room_sources["room_volume_m3"],
            "Room volume defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "room_volume_m3", room_volume_m3, "m3", "Room volume was supplied explicitly."
        )

    air_exchange = profile.air_exchange_rate_per_hour
    if air_exchange is None:
        air_exchange = room_defaults["air_exchange_rate_per_hour"]
        tracker.add_default(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            room_sources["air_exchange_rate_per_hour"],
            "Air exchange rate defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            "Air exchange rate was supplied explicitly.",
        )

    exposure_duration_hours = profile.exposure_duration_hours
    if exposure_duration_hours is None:
        exposure_duration_hours = room_defaults["exposure_duration_hours"]
        tracker.add_default(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            room_sources["exposure_duration_hours"],
            "Exposure duration defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            "Exposure duration was supplied explicitly.",
        )

    inhalation_rate = resolve_population_value(
        field_name="inhalation_rate_m3_per_hour",
        supplied_value=population.inhalation_rate_m3_per_hour,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="m3/h",
        rationale="Inhalation rate was supplied explicitly.",
        gt=0.0,
    )
    body_weight_kg = resolve_population_value(
        field_name="body_weight_kg",
        supplied_value=population.body_weight_kg,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="kg",
        rationale="Body weight was supplied explicitly for dose normalization.",
        gt=0.0,
    )
    _record_physchem_context(tracker, request.physchem_context)

    tracker.add_user(
        "source_distance_m",
        request.source_distance_m,
        "m",
        "Tier 1 source distance was supplied explicitly.",
    )
    tracker.add_user(
        "spray_duration_seconds",
        request.spray_duration_seconds,
        "s",
        "Tier 1 active spray duration was supplied explicitly.",
    )
    tracker.add_user(
        "near_field_volume_m3",
        request.near_field_volume_m3,
        "m3",
        "Tier 1 near-field volume was supplied explicitly.",
    )
    tracker.add_user(
        "airflow_directionality",
        request.airflow_directionality.value,
        None,
        "Tier 1 airflow directionality class was supplied explicitly.",
    )
    tracker.add_user(
        "particle_size_regime",
        request.particle_size_regime.value,
        None,
        "Tier 1 particle-size regime was supplied explicitly.",
    )

    spray_duration_hours = request.spray_duration_seconds / 3600.0
    if spray_duration_hours > exposure_duration_hours:
        raise ExposureScenarioError(
            code="inhalation_tier_1_duration_inconsistent",
            message=(
                "Tier 1 spray_duration_seconds cannot exceed the resolved exposure duration."
            ),
            suggestion=(
                "Shorten spray_duration_seconds or provide a longer exposure_duration_hours "
                "for the inhalation event."
            ),
            details={
                "sprayDurationSeconds": request.spray_duration_seconds,
                "exposureDurationHours": exposure_duration_hours,
            },
        )
    if request.near_field_volume_m3 >= room_volume_m3:
        raise ExposureScenarioError(
            code="inhalation_tier_1_near_field_volume_invalid",
            message=(
                "Tier 1 near_field_volume_m3 must be smaller than the resolved room volume."
            ),
            suggestion=(
                "Provide a near-field compartment smaller than room_volume_m3 so a far-field "
                "zone remains available."
            ),
            details={
                "nearFieldVolumeM3": request.near_field_volume_m3,
                "roomVolumeM3": room_volume_m3,
            },
        )

    released_mass_mg_event = chemical_mass_mg_event * aerosolized_fraction
    far_field_volume_m3 = room_volume_m3 - request.near_field_volume_m3
    initial_room_concentration_uncapped = released_mass_mg_event / room_volume_m3
    deposition_rate, deposition_source = registry.inhalation_deposition_rate_per_hour(
        particle_size_regime=request.particle_size_regime.value,
        application_method=profile.application_method,
        physical_form=profile.physical_form,
        product_subtype=profile.product_subtype,
    )
    tracker.add_default(
        "deposition_rate_per_hour",
        deposition_rate,
        "1/h",
        deposition_source,
        "Deposition sink defaulted from the bounded inhalation physical-caps pack.",
    )
    total_loss_rate = max(air_exchange, 0.0) + max(deposition_rate, 0.0)
    saturation_cap_mg_per_m3 = _inhalation_saturation_cap_mg_per_m3(
        physchem_context=request.physchem_context,
        profile=profile,
        registry=registry,
        tracker=tracker,
    )
    initial_room_concentration, initial_cap_applied = _apply_saturation_cap(
        concentration_mg_per_m3=initial_room_concentration_uncapped,
        saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
    )
    far_field_average_concentration_uncapped = _first_order_average_concentration(
        initial_room_concentration_uncapped,
        total_loss_rate,
        exposure_duration_hours,
    )
    far_field_average_concentration, far_field_cap_applied = _apply_saturation_cap(
        concentration_mg_per_m3=far_field_average_concentration_uncapped,
        saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
    )

    near_field_exchange_turnover = airflow_profile.exchange_turnover_per_hour
    static_interzonal_mixing_rate = request.near_field_volume_m3 * (
        near_field_exchange_turnover + max(air_exchange, 0.0)
    )
    local_entrainment_rates, local_entrainment_sources = registry.tier1_local_entrainment_rates(
        application_method=profile.application_method
    )
    thermal_plume_rate = local_entrainment_rates["thermal_plume_rate_m3_per_hour"]
    spray_jet_rate = local_entrainment_rates["spray_jet_rate_m3_per_hour"]
    local_entrainment_rate = local_entrainment_rates["local_entrainment_rate_m3_per_hour"]
    interzonal_mixing_floor_applied = static_interzonal_mixing_rate < local_entrainment_rate
    interzonal_mixing_rate = max(static_interzonal_mixing_rate, local_entrainment_rate)
    distance_factor = max(0.75, min(3.0, 0.75 / request.source_distance_m))
    particle_persistence_factor = particle_profile.persistence_factor
    emission_rate_mg_per_hour = released_mass_mg_event / spray_duration_hours
    near_field_increment = (
        emission_rate_mg_per_hour
        / interzonal_mixing_rate
        * distance_factor
        * particle_persistence_factor
    )
    near_field_active_concentration_uncapped = (
        far_field_average_concentration_uncapped + near_field_increment
    )
    near_field_active_concentration, near_field_cap_applied = _apply_saturation_cap(
        concentration_mg_per_m3=near_field_active_concentration_uncapped,
        saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
    )
    inhaled_mass_mg_per_event = (
        near_field_active_concentration * inhalation_rate * spray_duration_hours
    ) + (
        far_field_average_concentration
        * inhalation_rate
        * max(exposure_duration_hours - spray_duration_hours, 0.0)
    )
    inhaled_mass_mg_day = inhaled_mass_mg_per_event * profile.use_events_per_day
    extrathoracic_swallow_fraction = _extrathoracic_swallow_fraction(
        profile=profile,
        registry=registry,
        tracker=tracker,
        particle_size_regime=request.particle_size_regime.value,
    )
    swallowed_extrathoracic_mass_mg_day = inhaled_mass_mg_day * extrathoracic_swallow_fraction
    lower_respiratory_inhaled_mass_mg_day = (
        inhaled_mass_mg_day - swallowed_extrathoracic_mass_mg_day
    )
    breathing_zone_time_weighted_average = inhaled_mass_mg_per_event / (
        inhalation_rate * exposure_duration_hours
    )
    breathing_zone_time_weighted_average_uncapped = (
        (
            near_field_active_concentration_uncapped * inhalation_rate * spray_duration_hours
        )
        + (
            far_field_average_concentration_uncapped
            * inhalation_rate
            * max(exposure_duration_hours - spray_duration_hours, 0.0)
        )
    ) / (inhalation_rate * exposure_duration_hours)
    normalized_dose = inhaled_mass_mg_day / body_weight_kg
    room_air_decay_half_life_hours = (
        math.log(2.0) / total_loss_rate if total_loss_rate > 0.0 else None
    )
    saturation_cap_applied = (
        initial_cap_applied or far_field_cap_applied or near_field_cap_applied
    )

    tracker.add_derived(
        "released_mass_mg_per_event",
        released_mass_mg_event,
        "mg/event",
        "Released mass = chemical mass per event x aerosolized fraction.",
    )
    tracker.add_derived(
        "total_loss_rate_per_hour",
        total_loss_rate,
        "1/h",
        "Total room-air loss rate = air exchange rate + deposition sink.",
    )
    tracker.add_derived(
        "spray_duration_hours",
        spray_duration_hours,
        "h",
        "Converted Tier 1 spray duration from seconds into hours.",
    )
    tracker.add_derived(
        "far_field_volume_m3",
        far_field_volume_m3,
        "m3",
        "Far-field volume = room volume minus near-field volume.",
    )
    tracker.add_default(
        "near_field_exchange_turnover_per_hour",
        near_field_exchange_turnover,
        "1/h",
        tier_1_registry.source_reference(airflow_profile.source_id),
        "Tier 1 screening turnover resolved from the packaged airflow-directionality profile.",
    )
    tracker.add_default(
        "thermal_plume_rate_m3_per_hour",
        thermal_plume_rate,
        "m3/h",
        local_entrainment_sources["thermal_plume_rate_m3_per_hour"],
        "Tier 1 local entrainment floor includes a bounded thermal-plume entrainment term.",
    )
    tracker.add_default(
        "spray_jet_rate_m3_per_hour",
        spray_jet_rate,
        "m3/h",
        local_entrainment_sources["spray_jet_rate_m3_per_hour"],
        (
            "Tier 1 local entrainment floor includes a bounded spray-jet entrainment term "
            "resolved from application method."
        ),
    )
    tracker.add_default(
        "particle_persistence_factor",
        particle_persistence_factor,
        None,
        tier_1_registry.source_reference(particle_profile.source_id),
        "Tier 1 persistence factor resolved from the packaged particle-regime profile.",
    )
    tracker.add_derived(
        "static_interzonal_mixing_rate_m3_per_hour",
        static_interzonal_mixing_rate,
        "m3/h",
        (
            "Static interzonal mixing rate = near-field volume x "
            "(screening exchange turnover + room ventilation)."
        ),
    )
    tracker.add_derived(
        "local_entrainment_rate_m3_per_hour",
        local_entrainment_rate,
        "m3/h",
        (
            "Bounded local entrainment floor = thermal-plume entrainment + application-method "
            "spray-jet entrainment."
        ),
    )
    tracker.add_derived(
        "interzonal_mixing_rate_m3_per_hour",
        interzonal_mixing_rate,
        "m3/h",
        (
            "Interzonal mixing rate equals the greater of the static Tier 1 exchange estimate "
            "and the bounded local entrainment floor."
        ),
    )
    tracker.add_derived(
        "interzonal_mixing_floor_applied",
        interzonal_mixing_floor_applied,
        None,
        "Whether the bounded local entrainment floor exceeded the static Tier 1 interzonal rate.",
    )
    tracker.add_derived(
        "far_field_average_air_concentration_mg_per_m3",
        far_field_average_concentration,
        "mg/m3",
        (
            "Far-field room average derived from the Tier 1 room model over the full "
            "exposure window after bounded loss terms are applied."
        ),
    )
    tracker.add_derived(
        "uncapped_far_field_average_air_concentration_mg_per_m3",
        far_field_average_concentration_uncapped,
        "mg/m3",
        "Uncapped far-field room average before any volatility saturation cap is applied.",
    )
    tracker.add_derived(
        "near_field_active_spray_concentration_mg_per_m3",
        near_field_active_concentration,
        "mg/m3",
        (
            "Active spray breathing-zone concentration derived from a screening near-field "
            "increment added to the far-field room average."
        ),
    )
    tracker.add_derived(
        "uncapped_near_field_active_spray_concentration_mg_per_m3",
        near_field_active_concentration_uncapped,
        "mg/m3",
        (
            "Uncapped active-spray breathing-zone concentration before any volatility "
            "saturation cap is applied."
        ),
    )
    tracker.add_derived(
        "breathing_zone_time_weighted_average_mg_per_m3",
        breathing_zone_time_weighted_average,
        "mg/m3",
        "Time-weighted breathing-zone average over the full event duration.",
    )
    tracker.add_derived(
        "uncapped_average_air_concentration_mg_per_m3",
        breathing_zone_time_weighted_average_uncapped,
        "mg/m3",
        (
            "Uncapped breathing-zone time-weighted average before any volatility "
            "saturation cap is applied."
        ),
    )
    if room_air_decay_half_life_hours is not None:
        tracker.add_derived(
            "room_air_decay_half_life_hours",
            room_air_decay_half_life_hours,
            "h",
            "Room-air decay half-life implied by air exchange plus the bounded deposition sink.",
        )
    if saturation_cap_mg_per_m3 is not None:
        tracker.add_derived(
            "saturation_cap_applied",
            saturation_cap_applied,
            None,
            (
                "Whether the volatility saturation cap constrained one or more modeled "
                "Tier 1 room-air concentrations."
            ),
        )
        if saturation_cap_applied:
            tracker.add_quality_flag(
                "saturation_cap_applied",
                (
                    "Tier 1 inhalation concentrations were capped at the bounded volatility "
                    "saturation ceiling because the uncapped screening concentration exceeded "
                    "the thermodynamic limit."
                ),
                severity=Severity.WARNING,
            )
    tracker.add_derived(
        "inhaled_mass_mg_per_event",
        inhaled_mass_mg_per_event,
        "mg/event",
        "Inhaled mass per event combines active-spray near-field and remaining far-field periods.",
    )
    tracker.add_derived(
        "inhaled_mass_mg_per_day",
        inhaled_mass_mg_day,
        "mg/day",
        "Daily inhaled mass equals inhaled mass per event multiplied by events/day.",
    )
    tracker.add_derived(
        "swallowed_extrathoracic_mass_mg_per_day",
        swallowed_extrathoracic_mass_mg_day,
        "mg/day",
        (
            "Extrathoracic swallowed mass per day derived from the bounded swallowed "
            "fraction applied to the screening inhaled mass."
        ),
    )
    tracker.add_derived(
        "lower_respiratory_inhaled_mass_mg_per_day",
        lower_respiratory_inhaled_mass_mg_day,
        "mg/day",
        (
            "Lower-respiratory inhaled mass per day after subtracting the bounded "
            "extrathoracic swallowed share from the screening inhaled mass."
        ),
    )
    tracker.add_derived(
        "normalized_external_dose_mg_per_kg_day",
        normalized_dose,
        "mg/kg-day",
        "Normalized external dose = inhaled mass per day / body weight.",
    )

    tracker.add_limitation(
        "near_field_exchange_screening",
        (
            "Tier 1 NF/FF uses a deterministic screening exchange-rate mapping from "
            "airflow_directionality rather than measured interzonal airflow."
        ),
    )
    if interzonal_mixing_floor_applied:
        tracker.add_limitation(
            "tier1_local_entrainment_floor_screening",
            (
                "Tier 1 NF/FF applied a bounded local entrainment floor from thermal-plume "
                "and spray-jet heuristics because the static interzonal rate was weaker. "
                "This is a screening lower bound on local mixing, not a measured plume or "
                "jet-resolved airflow profile."
            ),
        )
    tracker.add_limitation(
        "particle_regime_screening",
        (
            "Particle-size effects use bounded screening persistence and deposition terms and "
            "do not model droplet evaporation or full aerosol dynamics."
        ),
    )
    tracker.add_quality_flag(
        "tier_1_nf_ff_screening",
        (
            "Tier 1 inhalation resolves a screening near-field/far-field split, but remains a "
            "deterministic external-dose model rather than a calibrated aerosol simulator."
        ),
        severity=Severity.INFO,
    )
    if matched_profile is not None and profile_divergences:
        tracker.add_quality_flag(
            "tier1_profile_anchor_divergence",
            (
                "Caller-supplied Tier 1 inputs diverge materially from the matched packaged "
                f"profile `{matched_profile.profile_id}`: " + "; ".join(profile_divergences) + "."
            ),
            severity=Severity.WARNING,
        )
    if matched_profile is None:
        tracker.add_quality_flag(
            "tier1_profile_no_packaged_match",
            (
                "No packaged Tier 1 profile matched the current product family and application "
                "method"
                + (
                    f" for product_subtype='{profile.product_subtype}'"
                    if profile.product_subtype
                    else ""
                )
                + "; screening geometry and regime inputs remain fully caller-defined."
            ),
            severity=Severity.INFO,
        )
    if fallback_variant == "auto":
        tracker.add_quality_flag(
            "two_zone_legacy_fallback_applied",
            (
                "Auto routing fell back to heuristic_v1 because two-zone auto-enable "
                "conditions were not met."
            ),
            severity=Severity.INFO,
        )

    scenario = ExposureScenario(
        scenario_id=f"inh-tier1-{uuid4().hex[:10]}",
        chemical_id=request.chemical_id,
        chemical_name=request.chemical_name,
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        external_dose=ScenarioDose(
            metric="normalized_external_dose",
            value=round(normalized_dose, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        ),
        product_use_profile=profile.model_copy(
            update={"exposure_duration_hours": exposure_duration_hours}
        ),
        population_profile=population.model_copy(
            update={
                "body_weight_kg": body_weight_kg,
                "inhalation_rate_m3_per_hour": inhalation_rate,
            }
        ),
        route_metrics={
            "chemical_mass_mg_per_event": round(chemical_mass_mg_event, 8),
            "released_mass_mg_per_event": round(released_mass_mg_event, 8),
            "initial_air_concentration_mg_per_m3": round(initial_room_concentration, 8),
            "uncapped_initial_air_concentration_mg_per_m3": round(
                initial_room_concentration_uncapped, 8
            ),
            "far_field_average_air_concentration_mg_per_m3": round(
                far_field_average_concentration, 8
            ),
            "uncapped_far_field_average_air_concentration_mg_per_m3": round(
                far_field_average_concentration_uncapped, 8
            ),
            "near_field_active_spray_concentration_mg_per_m3": round(
                near_field_active_concentration, 8
            ),
            "uncapped_near_field_active_spray_concentration_mg_per_m3": round(
                near_field_active_concentration_uncapped, 8
            ),
            "average_air_concentration_mg_per_m3": round(
                breathing_zone_time_weighted_average, 8
            ),
            "uncapped_average_air_concentration_mg_per_m3": round(
                breathing_zone_time_weighted_average_uncapped, 8
            ),
            "breathing_zone_time_weighted_average_mg_per_m3": round(
                breathing_zone_time_weighted_average, 8
            ),
            "static_interzonal_mixing_rate_m3_per_hour": round(
                static_interzonal_mixing_rate, 8
            ),
            "thermal_plume_rate_m3_per_hour": round(thermal_plume_rate, 8),
            "spray_jet_rate_m3_per_hour": round(spray_jet_rate, 8),
            "local_entrainment_rate_m3_per_hour": round(local_entrainment_rate, 8),
            "interzonal_mixing_rate_m3_per_hour": round(interzonal_mixing_rate, 8),
            "interzonal_mixing_floor_applied": interzonal_mixing_floor_applied,
            "deposition_rate_per_hour": round(deposition_rate, 8),
            "total_loss_rate_per_hour": round(total_loss_rate, 8),
            "room_air_decay_half_life_hours": (
                round(room_air_decay_half_life_hours, 8)
                if room_air_decay_half_life_hours is not None
                else None
            ),
            "saturation_cap_mg_per_m3": (
                round(saturation_cap_mg_per_m3, 8)
                if saturation_cap_mg_per_m3 is not None
                else None
            ),
            "saturation_cap_applied": saturation_cap_applied,
            "vapor_pressure_mmhg": (
                round(request.physchem_context.vapor_pressure_mmhg, 8)
                if request.physchem_context is not None
                and request.physchem_context.vapor_pressure_mmhg is not None
                else None
            ),
            "molecular_weight_g_per_mol": (
                round(request.physchem_context.molecular_weight_g_per_mol, 8)
                if request.physchem_context is not None
                and request.physchem_context.molecular_weight_g_per_mol is not None
                else None
            ),
            "inhaled_mass_mg_per_day": round(inhaled_mass_mg_day, 8),
            "extrathoracic_swallow_fraction": round(extrathoracic_swallow_fraction, 8),
            "swallowed_extrathoracic_mass_mg_per_day": round(
                swallowed_extrathoracic_mass_mg_day,
                8,
            ),
            "lower_respiratory_inhaled_mass_mg_per_day": round(
                lower_respiratory_inhaled_mass_mg_day,
                8,
            ),
            "tier1_product_profile_id": matched_profile.profile_id if matched_profile else None,
            "tier1_profile_alignment_status": profile_alignment_status,
            "tier1_profile_divergence_count": len(profile_divergences),
        },
        assumptions=tracker.assumptions,
        provenance=tracker.provenance(
            plugin_id="inhalation_tier_1_nf_ff_service",
            algorithm_id="inhalation.near_field_far_field.v1",
            generated_at=generated_at,
        ),
        limitations=tracker.limitations,
        quality_flags=tracker.quality_flags,
        fit_for_purpose=tracker.fit_for_purpose("inhalation_tier_1_screening"),
        tier_semantics=tracker.tier_semantics(
            tier_claimed=TierLevel.TIER_1,
            tier_rationale=(
                "Inhalation output uses a deterministic near-field/far-field screening split "
                "for spray events with explicit geometry and airflow-class inputs."
            ),
            required_caveats=[
                "Interpret the near-field compartment as a governed screening construct rather "
                "than a measured CFD domain.",
                "The airflow directionality and particle regime terms remain screening "
                "classifications, not measured aerosol dynamics.",
                "Very weak static interzonal mixing can be bounded upward by a local "
                "entrainment floor from thermal-plume and spray-jet heuristics.",
                "Bounded deposition and volatility caps improve physical realism but do not "
                "turn the model into a transient aerosol transport solver.",
            ],
            forbidden_interpretations=[
                "Do not interpret this result as deposited dose, absorbed dose, or a PBPK state.",
                "Do not treat the screening exchange mapping as a validated transient aerosol "
                "dispersion model.",
                "Do not treat the result as a final risk conclusion.",
            ],
        ),
        interpretation_notes=[
            "Deterministic Tier 1 inhalation scenario with a screening near-field/far-field split.",
            "The near-field increment is active during spray duration only and reverts to the "
            "far-field room average for the remainder of the event.",
            *(
                [
                    "Matched packaged Tier 1 screening profile "
                    f"`{matched_profile.profile_id}`; caller-supplied Tier 1 geometry and "
                    "regime inputs remain authoritative."
                ]
                if matched_profile is not None
                else []
            ),
            *(
                [
                    "Tier 1 profile alignment warning: " + "; ".join(profile_divergences) + "."
                ]
                if profile_divergences
                else []
            ),
            *(
                [
                    "No packaged Tier 1 profile matched this product family/application "
                    "method combination."
                ]
                if matched_profile is None
                else []
            ),
        ],
        tierUpgradeAdvisories=[],
    )
    return apply_worker_task_semantics(scenario, request, registry=registry)


def build_inhalation_residual_air_reentry_scenario(
    request: InhalationResidualAirReentryScenarioRequest,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ExposureScenario:
    tracker = AssumptionTracker(registry=registry)
    tracker.set_context(
        route=request.route.value,
        scenario_class=request.scenario_class.value,
        product_category=request.product_use_profile.product_category,
        product_subtype=request.product_use_profile.product_subtype,
        physical_form=request.product_use_profile.physical_form,
        application_method=request.product_use_profile.application_method,
        retention_type=request.product_use_profile.retention_type,
        population_group=request.population_profile.population_group,
        demographic_tags=",".join(request.population_profile.demographic_tags),
        region=request.population_profile.region,
    )
    profile = request.product_use_profile
    population = request.population_profile
    physchem_context = request.physchem_context

    if profile.application_method != RESIDUAL_AIR_REENTRY_APPLICATION_METHOD:
        raise ExposureScenarioError(
            code="inhalation_residual_air_reentry_method_invalid",
            message=(
                "Residual-air reentry scenarios require "
                "product_use_profile.application_method='residual_air_reentry'."
            ),
            suggestion=(
                "Set application_method to 'residual_air_reentry' and preserve the treated "
                "product family in product_category and product_subtype."
            ),
            details={"applicationMethod": profile.application_method},
        )

    _record_physchem_context(tracker, physchem_context)

    room_defaults, room_sources = registry.room_defaults(
        population.region,
        product_category=profile.product_category,
        product_subtype=profile.product_subtype,
        application_method=profile.application_method,
    )
    room_volume_m3 = profile.room_volume_m3
    if room_volume_m3 is None:
        room_volume_m3 = room_defaults["room_volume_m3"]
        tracker.add_default(
            "room_volume_m3",
            room_volume_m3,
            "m3",
            room_sources["room_volume_m3"],
            "Room volume defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "room_volume_m3",
            room_volume_m3,
            "m3",
            "Room volume was supplied explicitly.",
        )

    air_exchange = profile.air_exchange_rate_per_hour
    if air_exchange is None:
        air_exchange = room_defaults["air_exchange_rate_per_hour"]
        tracker.add_default(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            room_sources["air_exchange_rate_per_hour"],
            "Air exchange rate defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "air_exchange_rate_per_hour",
            air_exchange,
            "1/h",
            "Air exchange rate was supplied explicitly.",
        )

    exposure_duration_hours = profile.exposure_duration_hours
    if exposure_duration_hours is None:
        exposure_duration_hours = room_defaults["exposure_duration_hours"]
        tracker.add_default(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            room_sources["exposure_duration_hours"],
            "Exposure duration defaulted from the shared inhalation defaults pack.",
        )
    else:
        tracker.add_user(
            "exposure_duration_hours",
            exposure_duration_hours,
            "h",
            "Exposure duration was supplied explicitly.",
        )

    inhalation_rate = resolve_population_value(
        field_name="inhalation_rate_m3_per_hour",
        supplied_value=population.inhalation_rate_m3_per_hour,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="m3/h",
        rationale="Inhalation rate was supplied explicitly.",
        gt=0.0,
    )
    body_weight_kg = resolve_population_value(
        field_name="body_weight_kg",
        supplied_value=population.body_weight_kg,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="kg",
        rationale="Body weight was supplied explicitly for dose normalization.",
        gt=0.0,
    )

    tracker.add_user(
        "reentry_mode",
        request.reentry_mode.value,
        "mode",
        "Residual-air reentry mode was supplied explicitly or defaulted by schema.",
    )
    tracker.add_user(
        "use_events_per_day",
        profile.use_events_per_day,
        "events/day",
        "Reentry event frequency was supplied explicitly.",
    )

    if request.additional_decay_rate_per_hour is None:
        additional_decay_rate = 0.0
        tracker.add_derived(
            "additional_decay_rate_per_hour",
            additional_decay_rate,
            "1/h",
            (
                "No additional residual-air decay term was supplied beyond the resolved "
                "air exchange rate."
            ),
        )
        tracker.add_quality_flag(
            "additional_decay_rate_unspecified",
            (
                "Residual-air reentry was evaluated using air exchange only because no "
                "additional decay-rate term was supplied."
            ),
            severity=Severity.WARNING,
        )
    else:
        additional_decay_rate = request.additional_decay_rate_per_hour
        tracker.add_user(
            "additional_decay_rate_per_hour",
            additional_decay_rate,
            "1/h",
            "Additional residual-air decay rate was supplied explicitly.",
        )

    if request.post_application_delay_hours is None:
        post_application_delay = 0.0
        tracker.add_derived(
            "post_application_delay_hours",
            post_application_delay,
            "h",
            (
                "No explicit post-application delay was supplied; the scenario starts at "
                "the provided reentry-start concentration."
            ),
        )
        tracker.add_quality_flag(
            "post_application_delay_unspecified",
            (
                "The delay between application end and reentry start was not supplied. "
                "Interpret the scenario as beginning at the stated reentry-start air "
                "concentration."
            ),
            severity=Severity.WARNING,
        )
    else:
        post_application_delay = request.post_application_delay_hours
        tracker.add_user(
            "post_application_delay_hours",
            post_application_delay,
            "h",
            "Post-application delay was supplied explicitly.",
        )

    deposition_rate, deposition_source = registry.inhalation_deposition_rate_per_hour(
        application_method=profile.application_method,
        physical_form=profile.physical_form,
        product_subtype=profile.product_subtype,
    )
    tracker.add_default(
        "deposition_rate_per_hour",
        deposition_rate,
        "1/h",
        deposition_source,
        "Deposition sink defaulted from the bounded inhalation physical-caps pack.",
    )
    total_decay_rate = air_exchange + additional_decay_rate + max(deposition_rate, 0.0)
    saturation_cap_mg_per_m3 = _inhalation_saturation_cap_mg_per_m3(
        physchem_context=physchem_context,
        profile=profile,
        registry=registry,
        tracker=tracker,
    )

    saturation_cap_applied = False
    route_metrics: dict[str, ScalarValue] = {
        "reentry_mode": request.reentry_mode.value,
        "deposition_rate_per_hour": round(deposition_rate, 8),
        "total_decay_rate_per_hour": round(total_decay_rate, 8),
        "post_application_delay_hours": round(post_application_delay, 8),
        "saturation_cap_applied": False,
    }
    if saturation_cap_mg_per_m3 is not None:
        route_metrics["saturation_cap_mg_per_m3"] = round(saturation_cap_mg_per_m3, 8)

    interpretation_notes = []
    tier_caveats = []
    tier_forbidden = [
        "Do not interpret the result as absorbed dose, internal dose, or a final risk conclusion."
    ]
    tier_rationale = ""

    if request.reentry_mode == ResidualAirReentryMode.ANCHORED_REENTRY:
        reentry_start_concentration = cast(
            float, request.air_concentration_at_reentry_start_mg_per_m3
        )
        tracker.add_user(
            "air_concentration_at_reentry_start_mg_per_m3",
            reentry_start_concentration,
            "mg/m3",
            (
                "Residual-air reentry starts from a concentration anchored at the start of "
                "the reentry window."
            ),
        )

        uncapped_average_air_concentration = _first_order_average_concentration(
            reentry_start_concentration,
            total_decay_rate,
            exposure_duration_hours,
        )
        uncapped_air_concentration_at_reentry_end = _first_order_end_concentration(
            reentry_start_concentration,
            total_decay_rate,
            exposure_duration_hours,
        )
        average_air_concentration, average_capped = _apply_saturation_cap(
            concentration_mg_per_m3=uncapped_average_air_concentration,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        air_concentration_at_reentry_start, start_capped = _apply_saturation_cap(
            concentration_mg_per_m3=reentry_start_concentration,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        air_concentration_at_reentry_end, end_capped = _apply_saturation_cap(
            concentration_mg_per_m3=uncapped_air_concentration_at_reentry_end,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        saturation_cap_applied = average_capped or start_capped or end_capped

        tracker.add_derived(
            "average_air_concentration_mg_per_m3",
            average_air_concentration,
            "mg/m3",
            (
                "Average reentry air concentration derived from a first-order decay model "
                "starting at the supplied reentry-start concentration."
            ),
        )
        tracker.add_derived(
            "air_concentration_at_reentry_end_mg_per_m3",
            air_concentration_at_reentry_end,
            "mg/m3",
            "End-of-window reentry air concentration after first-order decay.",
        )
        tracker.add_quality_flag(
            "residual_air_reentry_screening",
            (
                "Residual-air reentry uses a caller-anchored starting air concentration and "
                "a bounded first-order decay model with air exchange and deposition rather "
                "than a treated-surface emission solver."
            ),
            severity=Severity.WARNING,
        )
        tracker.add_limitation(
            "treated_surface_emission_not_modeled",
            (
                "Residual-air reentry does not model treated-surface volatilization or "
                "application-phase emission; it starts from the supplied concentration at "
                "reentry start."
            ),
        )
        tracker.add_limitation(
            "reentry_air_anchor_required",
            (
                "Interpret the result only in the context of the supplied or externally "
                "estimated reentry-start air concentration."
            ),
        )
        interpretation_notes.extend(
            [
                (
                    "Deterministic residual-air reentry scenario starting from a supplied "
                    "room-air concentration."
                ),
                (
                    "The bounded decay model is intended for post-application room-air "
                    "screening, not for reconstructing the original application plume."
                ),
            ]
        )
        tier_rationale = (
            "Inhalation output uses a bounded residual-air reentry calculation that "
            "starts from a supplied concentration and applies first-order decay."
        )
        tier_caveats.extend(
            [
                (
                    "Interpret the reported air concentration as a residual-air reentry "
                    "value, not an application plume."
                ),
                (
                    "The result depends on the supplied reentry-start concentration and any "
                    "decay term."
                ),
                "Treated-surface volatilization is not solved mechanistically.",
            ]
        )
        tier_forbidden.extend(
            [
                (
                    "Do not interpret this result as an application-phase breathing-zone "
                    "peak concentration."
                ),
                (
                    "Do not treat the result as a treated-surface emission model or a "
                    "substitute for chamber decay data."
                ),
            ]
        )
        route_metrics.update(
            {
                "air_concentration_at_reentry_start_mg_per_m3": round(
                    air_concentration_at_reentry_start, 8
                ),
                "uncapped_air_concentration_at_reentry_start_mg_per_m3": round(
                    reentry_start_concentration, 8
                ),
                "average_air_concentration_mg_per_m3": round(average_air_concentration, 8),
                "uncapped_average_air_concentration_mg_per_m3": round(
                    uncapped_average_air_concentration, 8
                ),
                "air_concentration_at_reentry_end_mg_per_m3": round(
                    air_concentration_at_reentry_end, 8
                ),
                "uncapped_air_concentration_at_reentry_end_mg_per_m3": round(
                    uncapped_air_concentration_at_reentry_end, 8
                ),
            }
        )
    else:
        if request.air_concentration_at_reentry_start_mg_per_m3 is not None:
            tracker.add_quality_flag(
                "native_reentry_air_anchor_ignored",
                (
                    "airConcentrationAtReentryStartMgPerM3 was supplied, but native treated-"
                    "surface reentry derives the reentry air profile from the treated-surface "
                    "source term instead of the caller-provided anchor."
                ),
                severity=Severity.WARNING,
            )

        product_mass_g_event = resolve_product_mass_g(
            profile,
            registry,
            tracker,
            physchem_context=request.physchem_context,
        )
        chemical_mass_mg_event = grams_to_mg(product_mass_g_event) * profile.concentration_fraction
        tracker.add_user(
            "concentration_fraction",
            profile.concentration_fraction,
            "fraction",
            "Chemical fraction in the product was supplied explicitly.",
        )
        tracker.add_derived(
            "chemical_mass_mg_per_event",
            chemical_mass_mg_event,
            "mg/event",
            "Product mass per event multiplied by concentration fraction.",
        )

        if request.treated_surface_chemical_mass_mg is not None:
            treated_surface_chemical_mass_initial = request.treated_surface_chemical_mass_mg
            tracker.add_user(
                "treated_surface_chemical_mass_mg_initial",
                treated_surface_chemical_mass_initial,
                "mg",
                "Native treated-surface reentry uses the supplied treated-surface chemical mass.",
            )
        else:
            if request.treated_surface_residue_fraction is not None:
                treated_surface_residue_fraction = request.treated_surface_residue_fraction
                tracker.add_user(
                    "treated_surface_residue_fraction",
                    treated_surface_residue_fraction,
                    "fraction",
                    "Treated-surface residue fraction was supplied explicitly.",
                )
            elif profile.aerosolized_fraction is not None:
                treated_surface_residue_fraction = max(0.0, 1.0 - profile.aerosolized_fraction)
                tracker.add_derived(
                    "treated_surface_residue_fraction",
                    treated_surface_residue_fraction,
                    "fraction",
                    "Native treated-surface residue fraction derived as 1 - aerosolized_fraction.",
                )
            else:
                treated_surface_residue_fraction, residue_source = (
                    registry.native_residual_air_reentry_surface_residue_fraction(
                        profile.product_subtype
                    )
                )
                tracker.add_default(
                    "treated_surface_residue_fraction",
                    treated_surface_residue_fraction,
                    "fraction",
                    residue_source,
                    (
                        "Treated-surface residue fraction defaulted from the bounded native "
                        "residual-air reentry heuristics."
                    ),
                )
            treated_surface_chemical_mass_initial = (
                chemical_mass_mg_event * treated_surface_residue_fraction
            )
            tracker.add_derived(
                "treated_surface_chemical_mass_mg_initial",
                treated_surface_chemical_mass_initial,
                "mg",
                "Initial treated-surface source mass derived from per-event chemical mass.",
            )

        if request.surface_emission_rate_per_hour is not None:
            surface_emission_rate = request.surface_emission_rate_per_hour
            tracker.add_user(
                "surface_emission_rate_per_hour",
                surface_emission_rate,
                "1/h",
                "Treated-surface emission rate was supplied explicitly.",
            )
        else:
            vapor_pressure_mmhg = (
                physchem_context.vapor_pressure_mmhg if physchem_context is not None else None
            )
            surface_emission_rate, surface_emission_source = (
                registry.native_residual_air_reentry_surface_emission_rate_per_hour(
                    vapor_pressure_mmhg=vapor_pressure_mmhg,
                    product_subtype=profile.product_subtype,
                )
            )
            tracker.add_default(
                "surface_emission_rate_per_hour",
                surface_emission_rate,
                "1/h",
                surface_emission_source,
                (
                    "Treated-surface emission rate defaulted from the bounded native residual-"
                    "air reentry heuristics."
                ),
            )
            if vapor_pressure_mmhg is None:
                tracker.add_quality_flag(
                    "native_reentry_emission_rate_physchem_missing",
                    (
                        "Native treated-surface reentry used a generic surface-emission rate "
                        "default because physchemContext.vaporPressureMmhg was not supplied."
                    ),
                    severity=Severity.WARNING,
                )

        treated_surface_chemical_mass_at_reentry_start = (
            treated_surface_chemical_mass_initial
            * math.exp(-surface_emission_rate * post_application_delay)
        )
        air_concentration_at_reentry_start_uncapped = _surface_emission_air_concentration(
            initial_surface_mass_mg=treated_surface_chemical_mass_initial,
            surface_emission_rate_per_hour=surface_emission_rate,
            total_loss_rate_per_hour=total_decay_rate,
            room_volume_m3=room_volume_m3,
            elapsed_hours=post_application_delay,
        )
        average_air_concentration_uncapped = _surface_emission_average_concentration(
            initial_surface_mass_mg=treated_surface_chemical_mass_initial,
            surface_emission_rate_per_hour=surface_emission_rate,
            total_loss_rate_per_hour=total_decay_rate,
            room_volume_m3=room_volume_m3,
            start_hours=post_application_delay,
            duration_hours=exposure_duration_hours,
        )
        air_concentration_at_reentry_end_uncapped = _surface_emission_air_concentration(
            initial_surface_mass_mg=treated_surface_chemical_mass_initial,
            surface_emission_rate_per_hour=surface_emission_rate,
            total_loss_rate_per_hour=total_decay_rate,
            room_volume_m3=room_volume_m3,
            elapsed_hours=post_application_delay + exposure_duration_hours,
        )

        air_concentration_at_reentry_start, start_capped = _apply_saturation_cap(
            concentration_mg_per_m3=air_concentration_at_reentry_start_uncapped,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        average_air_concentration, average_capped = _apply_saturation_cap(
            concentration_mg_per_m3=average_air_concentration_uncapped,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        air_concentration_at_reentry_end, end_capped = _apply_saturation_cap(
            concentration_mg_per_m3=air_concentration_at_reentry_end_uncapped,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        saturation_cap_applied = start_capped or average_capped or end_capped

        tracker.add_derived(
            "treated_surface_chemical_mass_mg_at_reentry_start",
            treated_surface_chemical_mass_at_reentry_start,
            "mg",
            "Residual source mass remaining on the treated surface at the start of reentry.",
        )
        tracker.add_derived(
            "air_concentration_at_reentry_start_mg_per_m3",
            air_concentration_at_reentry_start,
            "mg/m3",
            (
                "Reentry-start room-air concentration derived from the native treated-surface "
                "emission source term."
            ),
        )
        tracker.add_derived(
            "average_air_concentration_mg_per_m3",
            average_air_concentration,
            "mg/m3",
            "Average reentry air concentration derived from the native treated-surface source.",
        )
        tracker.add_derived(
            "air_concentration_at_reentry_end_mg_per_m3",
            air_concentration_at_reentry_end,
            "mg/m3",
            "End-of-window reentry air concentration after bounded treated-surface emission.",
        )
        tracker.add_derived(
            "surface_emission_half_life_hours",
            math.log(2.0) / surface_emission_rate if surface_emission_rate > 0.0 else 0.0,
            "h",
            "Surface-emission half-life implied by the bounded native first-order source term.",
        )
        tracker.add_quality_flag(
            "native_treated_surface_reentry_screening",
            (
                "Native treated-surface residual-air reentry uses a bounded first-order "
                "surface-emission source term plus room-loss terms. It is intended for "
                "microenvironment screening, not as a full SVOC partitioning model."
            ),
            severity=Severity.WARNING,
        )
        tracker.add_limitation(
            "native_treated_surface_emission_bounded",
            (
                "Native treated-surface residual-air reentry does not solve sorption, "
                "furnishing uptake, multilayer residue behavior, or heterogeneous indoor "
                "surfaces. It uses a bounded first-order source term."
            ),
        )
        interpretation_notes.extend(
            [
                (
                    "Deterministic residual-air reentry scenario derived from treated-surface "
                    "chemical mass and a bounded first-order surface-emission source term."
                ),
                (
                    "The bounded native mode is intended for same-room post-application "
                    "screening when no external reentry-start concentration anchor is available."
                ),
            ]
        )
        tier_rationale = (
            "Inhalation output uses a bounded treated-surface residual-air source term with "
            "room-loss terms to derive the reentry air profile."
        )
        tier_caveats.extend(
            [
                (
                    "Interpret the reported air concentration as a same-room residual-air "
                    "screening value derived from treated-surface mass."
                ),
                (
                    "The result depends on the resolved treated-surface source mass, emission "
                    "rate, room volume, and loss terms."
                ),
                (
                    "Indoor sorption and heterogeneous surface partitioning are not solved "
                    "mechanistically."
                ),
            ]
        )
        tier_forbidden.extend(
            [
                (
                    "Do not treat the result as a chamber-validated treated-surface emission "
                    "model across arbitrary indoor materials."
                ),
                (
                    "Do not treat the result as a substitute for measured post-application room-"
                    "air monitoring when those data exist."
                ),
            ]
        )
        route_metrics.update(
            {
                "treated_surface_chemical_mass_mg_initial": round(
                    treated_surface_chemical_mass_initial, 8
                ),
                "treated_surface_chemical_mass_mg_at_reentry_start": round(
                    treated_surface_chemical_mass_at_reentry_start, 8
                ),
                "surface_emission_rate_per_hour": round(surface_emission_rate, 8),
                "surface_emission_half_life_hours": round(
                    math.log(2.0) / surface_emission_rate if surface_emission_rate > 0.0 else 0.0,
                    8,
                ),
                "air_concentration_at_reentry_start_mg_per_m3": round(
                    air_concentration_at_reentry_start, 8
                ),
                "uncapped_air_concentration_at_reentry_start_mg_per_m3": round(
                    air_concentration_at_reentry_start_uncapped, 8
                ),
                "average_air_concentration_mg_per_m3": round(average_air_concentration, 8),
                "uncapped_average_air_concentration_mg_per_m3": round(
                    average_air_concentration_uncapped, 8
                ),
                "air_concentration_at_reentry_end_mg_per_m3": round(
                    air_concentration_at_reentry_end, 8
                ),
                "uncapped_air_concentration_at_reentry_end_mg_per_m3": round(
                    air_concentration_at_reentry_end_uncapped, 8
                ),
            }
        )

    route_metrics["saturation_cap_applied"] = saturation_cap_applied
    if saturation_cap_applied:
        tracker.add_quality_flag(
            "saturation_cap_applied",
            (
                "Residual-air reentry concentration outputs were capped at the bounded "
                "thermodynamic saturation ceiling."
            ),
            severity=Severity.WARNING,
        )

    inhaled_mass_mg_per_day = (
        average_air_concentration
        * inhalation_rate
        * exposure_duration_hours
        * profile.use_events_per_day
    )
    normalized_dose = inhaled_mass_mg_per_day / body_weight_kg

    tracker.add_derived(
        "total_decay_rate_per_hour",
        total_decay_rate,
        "1/h",
        (
            "Total decay rate = air exchange rate + additional residual-air decay rate "
            "+ deposition sink."
        ),
    )
    tracker.add_derived(
        "average_air_concentration_mg_per_m3",
        average_air_concentration,
        "mg/m3",
        (
            "Average reentry air concentration derived from a first-order decay model "
            "starting at the supplied reentry-start concentration."
        ),
    )
    tracker.add_derived(
        "air_concentration_at_reentry_end_mg_per_m3",
        air_concentration_at_reentry_end,
        "mg/m3",
        "End-of-window reentry air concentration after first-order decay.",
    )
    tracker.add_derived(
        "inhaled_mass_mg_per_day",
        inhaled_mass_mg_per_day,
        "mg/day",
        (
            "Inhaled mass = average reentry air concentration x inhalation rate x "
            "exposure duration x events/day."
        ),
    )
    tracker.add_derived(
        "normalized_external_dose_mg_per_kg_day",
        normalized_dose,
        "mg/kg-day",
        "Normalized external dose = inhaled mass per day / body weight.",
    )
    if profile.product_subtype != "indoor_surface_insecticide":
        tracker.add_quality_flag(
            "residual_air_reentry_product_subtype_unusual",
            (
                "Residual-air reentry is most strongly anchored today for "
                "`indoor_surface_insecticide` scenarios. Other product_subtype values "
                "should be reviewed carefully."
            ),
            severity=Severity.WARNING,
        )

    room_air_decay_half_life_hours = (
        math.log(2.0) / total_decay_rate if total_decay_rate > 0.0 else float("inf")
    )
    route_metrics["inhaled_mass_mg_per_day"] = round(inhaled_mass_mg_per_day, 8)
    route_metrics["room_air_decay_half_life_hours"] = round(room_air_decay_half_life_hours, 8)

    return ExposureScenario(
        scenario_id=f"inh-reentry-{uuid4().hex[:12]}",
        chemical_id=request.chemical_id,
        chemical_name=request.chemical_name,
        route=Route.INHALATION,
        scenario_class=ScenarioClass.INHALATION,
        external_dose=ScenarioDose(
            metric="normalized_external_dose",
            value=round(normalized_dose, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        ),
        product_use_profile=profile.model_copy(
            update={"exposure_duration_hours": exposure_duration_hours}
        ),
        population_profile=population.model_copy(
            update={
                "body_weight_kg": body_weight_kg,
                "inhalation_rate_m3_per_hour": inhalation_rate,
            }
        ),
        route_metrics=route_metrics,
        assumptions=tracker.assumptions,
        provenance=tracker.provenance(
            plugin_id="inhalation_residual_air_reentry_plugin",
            algorithm_id="inhalation.residual_air_reentry.v1",
            generated_at=generated_at,
        ),
        limitations=tracker.limitations,
        quality_flags=tracker.quality_flags,
        fit_for_purpose=tracker.fit_for_purpose("inhalation_residual_air_reentry_screening"),
        tier_semantics=tracker.tier_semantics(
            tier_claimed=TierLevel.TIER_0,
            tier_rationale=tier_rationale,
            required_caveats=tier_caveats,
            forbidden_interpretations=tier_forbidden,
        ),
        interpretation_notes=interpretation_notes,
        tierUpgradeAdvisories=[],
    )


class InhalationScreeningPlugin(ScenarioPlugin):
    plugin_id = "inhalation_screening_plugin"
    algorithm_id = "inhalation.room_well_mixed.v1"
    scenario_class = ScenarioClass.INHALATION
    supported_routes = (Route.INHALATION,)

    def _tier_1_upgrade_advisories(
        self,
        *,
        application_method: str,
        exposure_duration_hours: float,
    ) -> list[TierUpgradeAdvisory]:
        if application_method not in TIER_1_SPRAY_METHODS:
            return []
        trigger_codes = ["spray_application", "breathing_zone_peak_relevant"]
        if exposure_duration_hours <= 0.5:
            trigger_codes.append("short_duration_event")
        return [
            TierUpgradeAdvisory(
                advisoryId="inh-tier1-upgrade-spray",
                route=Route.INHALATION,
                currentTier=TierLevel.TIER_0,
                targetTier=TierLevel.TIER_1,
                status=TierUpgradeStatus.RECOMMENDED_NOT_IMPLEMENTED,
                recommendedModelFamily=TIER_1_MODEL_FAMILY,
                triggerCodes=trigger_codes,
                requiredInputs=tier_1_input_requirements(),
                blockingGaps=[
                    "tier_1_validation_evidence_incomplete",
                ],
                guidanceResource=TIER_1_GUIDANCE_RESOURCE,
                rationale=(
                    "Spray events can produce short-duration breathing-zone peaks that are not "
                    "resolved by the Tier-0 well-mixed room model."
                ),
            )
        ]

    def build(self, request, context: ScenarioExecutionContext) -> ExposureScenario:
        tracker = context.tracker
        profile = request.product_use_profile
        population = request.population_profile
        registry = context.registry

        if request.requested_tier == TierLevel.TIER_1:
            if not isinstance(request, InhalationTier1ScenarioRequest):
                raise ExposureScenarioError(
                    code="inhalation_tier_1_requires_specialized_request",
                    message=(
                        "Tier 1 inhalation screening requires an InhalationTier1ScenarioRequest."
                    ),
                    suggestion=(
                        "Construct an InhalationTier1ScenarioRequest with the required "
                        "Tier-1 fields (source_distance_m, near_field_volume_m3, etc.), or "
                        "use the dedicated exposure_build_inhalation_tier1_screening_scenario tool."
                    ),
                )
            return build_inhalation_tier_1_screening_scenario(
                request,
                registry,
                generated_at=None,
            )

        product_mass_g_event = resolve_product_mass_g(
            profile,
            registry,
            tracker,
            physchem_context=request.physchem_context,
        )
        chemical_mass_mg_event = grams_to_mg(product_mass_g_event) * profile.concentration_fraction
        tracker.add_user(
            "concentration_fraction",
            profile.concentration_fraction,
            "fraction",
            "Chemical fraction in the product was supplied explicitly.",
        )
        tracker.add_user(
            "use_events_per_day",
            profile.use_events_per_day,
            "events/day",
            "Use frequency was supplied explicitly.",
        )
        tracker.add_derived(
            "chemical_mass_mg_per_event",
            chemical_mass_mg_event,
            "mg/event",
            "Product mass per event multiplied by concentration fraction.",
        )

        if profile.aerosolized_fraction is not None:
            aerosolized_fraction = profile.aerosolized_fraction
            tracker.add_user(
                "aerosolized_fraction",
                aerosolized_fraction,
                "fraction",
                "Aerosolized fraction was supplied explicitly.",
            )
        else:
            aerosolized_fraction, source = registry.aerosolized_fraction(
                profile.application_method,
                profile.product_category,
                profile.product_subtype,
            )
            tracker.add_default(
                "aerosolized_fraction",
                aerosolized_fraction,
                "fraction",
                source,
                (
                    "Aerosolized fraction defaulted from "
                    f"application_method='{profile.application_method}' and "
                    f"product_category='{profile.product_category}'"
                    + (
                        f" and product_subtype='{profile.product_subtype}'."
                        if profile.product_subtype
                        else "."
                    )
                ),
            )
        _maybe_flag_missing_product_subtype(tracker, profile)

        room_defaults, room_sources = registry.room_defaults(
            population.region,
            product_category=profile.product_category,
            product_subtype=profile.product_subtype,
            application_method=profile.application_method,
        )
        room_volume_m3 = profile.room_volume_m3
        if room_volume_m3 is None:
            room_volume_m3 = room_defaults["room_volume_m3"]
            tracker.add_default(
                "room_volume_m3",
                room_volume_m3,
                "m3",
                room_sources["room_volume_m3"],
                "Room volume defaulted from the shared inhalation defaults pack.",
            )
        else:
            tracker.add_user(
                "room_volume_m3", room_volume_m3, "m3", "Room volume was supplied explicitly."
            )

        air_exchange = profile.air_exchange_rate_per_hour
        if air_exchange is None:
            air_exchange = room_defaults["air_exchange_rate_per_hour"]
            tracker.add_default(
                "air_exchange_rate_per_hour",
                air_exchange,
                "1/h",
                room_sources["air_exchange_rate_per_hour"],
                "Air exchange rate defaulted from the shared inhalation defaults pack.",
            )
        else:
            tracker.add_user(
                "air_exchange_rate_per_hour",
                air_exchange,
                "1/h",
                "Air exchange rate was supplied explicitly.",
            )

        exposure_duration_hours = profile.exposure_duration_hours
        if exposure_duration_hours is None:
            exposure_duration_hours = room_defaults["exposure_duration_hours"]
            tracker.add_default(
                "exposure_duration_hours",
                exposure_duration_hours,
                "h",
                room_sources["exposure_duration_hours"],
                "Exposure duration defaulted from the shared inhalation defaults pack.",
            )
        else:
            tracker.add_user(
                "exposure_duration_hours",
                exposure_duration_hours,
                "h",
                "Exposure duration was supplied explicitly.",
            )

        inhalation_rate = resolve_population_value(
            field_name="inhalation_rate_m3_per_hour",
            supplied_value=population.inhalation_rate_m3_per_hour,
            population_group=population.population_group,
            registry=registry,
            tracker=tracker,
            unit="m3/h",
            rationale="Inhalation rate was supplied explicitly.",
            gt=0.0,
        )
        body_weight_kg = resolve_population_value(
            field_name="body_weight_kg",
            supplied_value=population.body_weight_kg,
            population_group=population.population_group,
            registry=registry,
            tracker=tracker,
            unit="kg",
            rationale="Body weight was supplied explicitly for dose normalization.",
            gt=0.0,
        )
        _record_physchem_context(tracker, request.physchem_context)

        released_mass_mg_event = chemical_mass_mg_event * aerosolized_fraction
        initial_air_concentration_uncapped = released_mass_mg_event / room_volume_m3
        deposition_rate, deposition_source = registry.inhalation_deposition_rate_per_hour(
            application_method=profile.application_method,
            physical_form=profile.physical_form,
            product_subtype=profile.product_subtype,
        )
        tracker.add_default(
            "deposition_rate_per_hour",
            deposition_rate,
            "1/h",
            deposition_source,
            "Deposition sink defaulted from the bounded inhalation physical-caps pack.",
        )
        total_loss_rate = max(air_exchange, 0.0) + max(deposition_rate, 0.0)
        saturation_cap_mg_per_m3 = _inhalation_saturation_cap_mg_per_m3(
            physchem_context=request.physchem_context,
            profile=profile,
            registry=registry,
            tracker=tracker,
        )
        initial_air_concentration, initial_cap_applied = _apply_saturation_cap(
            concentration_mg_per_m3=initial_air_concentration_uncapped,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        average_air_concentration_uncapped = _first_order_average_concentration(
            initial_air_concentration_uncapped,
            total_loss_rate,
            exposure_duration_hours,
        )
        average_air_concentration, average_cap_applied = _apply_saturation_cap(
            concentration_mg_per_m3=average_air_concentration_uncapped,
            saturation_cap_mg_per_m3=saturation_cap_mg_per_m3,
        )
        air_concentration_at_event_end = _first_order_end_concentration(
            initial_air_concentration,
            total_loss_rate,
            exposure_duration_hours,
        )
        room_air_decay_half_life_hours = (
            math.log(2.0) / total_loss_rate if total_loss_rate > 0.0 else None
        )
        inhaled_mass_mg_day = (
            average_air_concentration
            * inhalation_rate
            * exposure_duration_hours
            * profile.use_events_per_day
        )
        extrathoracic_swallow_fraction = _extrathoracic_swallow_fraction(
            profile=profile,
            registry=registry,
            tracker=tracker,
        )
        swallowed_extrathoracic_mass_mg_day = (
            inhaled_mass_mg_day * extrathoracic_swallow_fraction
        )
        lower_respiratory_inhaled_mass_mg_day = (
            inhaled_mass_mg_day - swallowed_extrathoracic_mass_mg_day
        )
        normalized_dose = inhaled_mass_mg_day / body_weight_kg
        saturation_cap_applied = initial_cap_applied or average_cap_applied

        tracker.add_derived(
            "released_mass_mg_per_event",
            released_mass_mg_event,
            "mg/event",
            "Released mass = chemical mass per event x aerosolized fraction.",
        )
        tracker.add_derived(
            "total_loss_rate_per_hour",
            total_loss_rate,
            "1/h",
            "Total room-air loss rate = air exchange rate + deposition sink.",
        )
        tracker.add_derived(
            "average_air_concentration_mg_per_m3",
            average_air_concentration,
            "mg/m3",
            (
                "Average air concentration derived from a well-mixed room "
                "model with bounded air exchange and deposition removal."
            ),
        )
        tracker.add_derived(
            "uncapped_average_air_concentration_mg_per_m3",
            average_air_concentration_uncapped,
            "mg/m3",
            (
                "Uncapped room-average air concentration before any volatility "
                "saturation cap is applied."
            ),
        )
        tracker.add_derived(
            "initial_air_concentration_mg_per_m3",
            initial_air_concentration,
            "mg/m3",
            (
                "Initial room concentration immediately after release in the well-mixed "
                "single-zone model."
            ),
        )
        tracker.add_derived(
            "uncapped_initial_air_concentration_mg_per_m3",
            initial_air_concentration_uncapped,
            "mg/m3",
            "Uncapped initial room concentration before any volatility saturation cap is applied.",
        )
        tracker.add_derived(
            "air_concentration_at_event_end_mg_per_m3",
            air_concentration_at_event_end,
            "mg/m3",
            (
                "End-of-window room concentration after first-order air exchange and "
                "deposition removal in the well-mixed single-zone model."
            ),
        )
        if room_air_decay_half_life_hours is not None:
            tracker.add_derived(
                "room_air_decay_half_life_hours",
                room_air_decay_half_life_hours,
                "h",
                (
                    "Room-air decay half-life implied by air exchange plus the bounded "
                    "deposition sink in the well-mixed single-zone model."
                ),
            )
        if saturation_cap_mg_per_m3 is not None:
            tracker.add_derived(
                "saturation_cap_applied",
                saturation_cap_applied,
                None,
                (
                    "Whether the volatility saturation cap constrained one or more "
                    "modeled Tier 0 room-air concentrations."
                ),
            )
            if saturation_cap_applied:
                tracker.add_quality_flag(
                    "saturation_cap_applied",
                    (
                        "Tier 0 inhalation concentrations were capped at the bounded volatility "
                        "saturation ceiling because the uncapped screening concentration exceeded "
                        "the thermodynamic limit."
                    ),
                    severity=Severity.WARNING,
                )
        tracker.add_derived(
            "inhaled_mass_mg_per_day",
            inhaled_mass_mg_day,
            "mg/day",
            "Inhaled mass = average concentration x inhalation rate x event duration x events/day.",
        )
        tracker.add_derived(
            "swallowed_extrathoracic_mass_mg_per_day",
            swallowed_extrathoracic_mass_mg_day,
            "mg/day",
            (
                "Extrathoracic swallowed mass per day derived from the bounded swallowed "
                "fraction applied to the screening inhaled mass."
            ),
        )
        tracker.add_derived(
            "lower_respiratory_inhaled_mass_mg_per_day",
            lower_respiratory_inhaled_mass_mg_day,
            "mg/day",
            (
                "Lower-respiratory inhaled mass per day after subtracting the bounded "
                "extrathoracic swallowed share from the screening inhaled mass."
            ),
        )
        tracker.add_derived(
            "normalized_external_dose_mg_per_kg_day",
            normalized_dose,
            "mg/kg-day",
            "Normalized external dose = inhaled mass per day / body weight.",
        )
        if profile.application_method in TIER_1_SPRAY_METHODS:
            tracker.add_limitation(
                "breathing_zone_not_modeled",
                (
                    "Tier-0 inhalation uses a well-mixed room average and does not resolve "
                    "near-field breathing-zone peaks for spray events."
                ),
            )
            tracker.add_quality_flag(
                "tier_0_spray_screening",
                (
                    "Spray event was evaluated with the Tier-0 well-mixed screening model; "
                    "consider a near-field/far-field tier for directed or short-duration sprays."
                ),
                severity=Severity.WARNING,
            )
        tier_upgrade_advisories = self._tier_1_upgrade_advisories(
            application_method=profile.application_method,
            exposure_duration_hours=exposure_duration_hours,
        )

        return ExposureScenario(
            scenario_id=f"inh-{uuid4().hex[:12]}",
            chemical_id=request.chemical_id,
            chemical_name=request.chemical_name,
            route=Route.INHALATION,
            scenario_class=ScenarioClass.INHALATION,
            external_dose=ScenarioDose(
                metric="normalized_external_dose",
                value=round(normalized_dose, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            ),
            product_use_profile=profile.model_copy(
                update={"exposure_duration_hours": exposure_duration_hours}
            ),
            population_profile=population.model_copy(
                update={
                    "body_weight_kg": body_weight_kg,
                    "inhalation_rate_m3_per_hour": inhalation_rate,
                }
            ),
            route_metrics={
                "chemical_mass_mg_per_event": round(chemical_mass_mg_event, 8),
                "released_mass_mg_per_event": round(released_mass_mg_event, 8),
                "initial_air_concentration_mg_per_m3": round(initial_air_concentration, 8),
                "uncapped_initial_air_concentration_mg_per_m3": round(
                    initial_air_concentration_uncapped, 8
                ),
                "average_air_concentration_mg_per_m3": round(average_air_concentration, 8),
                "uncapped_average_air_concentration_mg_per_m3": round(
                    average_air_concentration_uncapped, 8
                ),
                "air_concentration_at_event_end_mg_per_m3": round(
                    air_concentration_at_event_end, 8
                ),
                "deposition_rate_per_hour": round(deposition_rate, 8),
                "total_loss_rate_per_hour": round(total_loss_rate, 8),
                "room_air_decay_half_life_hours": (
                    round(room_air_decay_half_life_hours, 8)
                    if room_air_decay_half_life_hours is not None
                    else None
                ),
                "saturation_cap_mg_per_m3": (
                    round(saturation_cap_mg_per_m3, 8)
                    if saturation_cap_mg_per_m3 is not None
                    else None
                ),
                "saturation_cap_applied": saturation_cap_applied,
                "vapor_pressure_mmhg": (
                    round(request.physchem_context.vapor_pressure_mmhg, 8)
                    if request.physchem_context is not None
                    and request.physchem_context.vapor_pressure_mmhg is not None
                    else None
                ),
                "molecular_weight_g_per_mol": (
                    round(request.physchem_context.molecular_weight_g_per_mol, 8)
                    if request.physchem_context is not None
                    and request.physchem_context.molecular_weight_g_per_mol is not None
                    else None
                ),
                "inhaled_mass_mg_per_day": round(inhaled_mass_mg_day, 8),
                "extrathoracic_swallow_fraction": round(extrathoracic_swallow_fraction, 8),
                "swallowed_extrathoracic_mass_mg_per_day": round(
                    swallowed_extrathoracic_mass_mg_day,
                    8,
                ),
                "lower_respiratory_inhaled_mass_mg_per_day": round(
                    lower_respiratory_inhaled_mass_mg_day,
                    8,
                ),
            },
            assumptions=tracker.assumptions,
            provenance=tracker.provenance(self.plugin_id, self.algorithm_id),
            limitations=tracker.limitations,
            quality_flags=tracker.quality_flags,
            fit_for_purpose=tracker.fit_for_purpose("inhalation_screening"),
            tier_semantics=tracker.tier_semantics(
                tier_claimed=TierLevel.TIER_0,
                tier_rationale=(
                    "Inhalation output uses a deterministic single-zone, well-mixed room model "
                    "with first-order air exchange removal."
                ),
                required_caveats=[
                    "Interpret the reported air concentration as a room-average screening value.",
                    "Air exchange and deposition are represented as bounded first-order loss "
                    "terms rather than a full airflow or aerosol-dynamics treatment.",
                ],
                forbidden_interpretations=[
                    "Do not interpret this result as a breathing-zone peak concentration.",
                    "Do not treat directed or source-proximal spray events as near-field resolved.",
                    "Do not interpret the result as deposited dose, absorbed dose, or a final "
                    "risk conclusion.",
                ],
            ),
            interpretation_notes=[
                "Deterministic inhalation screening scenario using a well-mixed room assumption.",
                "Air exchange acts as a first-order removal term rather than a full CFD treatment.",
            ],
            tierUpgradeAdvisories=tier_upgrade_advisories,
        )
