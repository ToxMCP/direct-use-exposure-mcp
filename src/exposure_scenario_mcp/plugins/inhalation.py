"""Deterministic inhalation screening plugin."""

from __future__ import annotations

import math
from uuid import uuid4

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    DoseUnit,
    ExposureScenario,
    InhalationTier1ScenarioRequest,
    Route,
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
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry

TIER_1_SPRAY_METHODS = {"trigger_spray", "pump_spray", "aerosol_spray"}
TIER_1_MODEL_FAMILY = "inhalation_near_field_far_field_screening"
TIER_1_GUIDANCE_RESOURCE = "docs://inhalation-tier-upgrade-guide"
TIER_1_PROFILE_NUMERIC_TOLERANCES = {
    "source_distance_m": 0.35,
    "near_field_volume_m3": 0.35,
    "spray_duration_seconds": 0.4,
}


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


def build_inhalation_tier_1_screening_scenario(
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
        physical_form=request.product_use_profile.physical_form,
        application_method=request.product_use_profile.application_method,
        retention_type=request.product_use_profile.retention_type,
        population_group=request.population_profile.population_group,
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
    )
    matched_profile = matched_profiles[0] if matched_profiles else None
    profile_alignment_status, profile_divergences = _tier_1_profile_alignment(
        request,
        matched_profile,
    )

    product_mass_g_event = resolve_product_mass_g(profile, registry, tracker)
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
        )
        tracker.add_default(
            "aerosolized_fraction",
            aerosolized_fraction,
            "fraction",
            source,
            (
                "Aerosolized fraction defaulted from "
                f"application_method='{profile.application_method}' and "
                f"product_category='{profile.product_category}'."
            ),
        )

    room_defaults, room_source = registry.room_defaults(population.region)
    room_volume_m3 = profile.room_volume_m3
    if room_volume_m3 is None:
        room_volume_m3 = room_defaults["room_volume_m3"]
        tracker.add_default(
            "room_volume_m3",
            room_volume_m3,
            "m3",
            room_source,
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
            room_source,
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
            room_source,
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
    )
    body_weight_kg = resolve_population_value(
        field_name="body_weight_kg",
        supplied_value=population.body_weight_kg,
        population_group=population.population_group,
        registry=registry,
        tracker=tracker,
        unit="kg",
        rationale="Body weight was supplied explicitly for dose normalization.",
    )

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
    initial_room_concentration = released_mass_mg_event / room_volume_m3
    k = max(air_exchange, 0.0)
    if k == 0:
        far_field_average_concentration = initial_room_concentration
    else:
        far_field_average_concentration = initial_room_concentration * (
            (1.0 - math.exp(-k * exposure_duration_hours)) / (k * exposure_duration_hours)
        )

    near_field_exchange_turnover = airflow_profile.exchange_turnover_per_hour
    interzonal_mixing_rate = request.near_field_volume_m3 * (
        near_field_exchange_turnover + max(air_exchange, 0.0)
    )
    distance_factor = max(0.75, min(3.0, 0.75 / request.source_distance_m))
    particle_persistence_factor = particle_profile.persistence_factor
    emission_rate_mg_per_hour = released_mass_mg_event / spray_duration_hours
    near_field_increment = (
        emission_rate_mg_per_hour
        / interzonal_mixing_rate
        * distance_factor
        * particle_persistence_factor
    )
    near_field_active_concentration = far_field_average_concentration + near_field_increment
    inhaled_mass_mg_per_event = (
        near_field_active_concentration * inhalation_rate * spray_duration_hours
    ) + (
        far_field_average_concentration
        * inhalation_rate
        * max(exposure_duration_hours - spray_duration_hours, 0.0)
    )
    inhaled_mass_mg_day = inhaled_mass_mg_per_event * profile.use_events_per_day
    breathing_zone_time_weighted_average = inhaled_mass_mg_per_event / (
        inhalation_rate * exposure_duration_hours
    )
    normalized_dose = inhaled_mass_mg_day / body_weight_kg

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
    tracker.add_default(
        "near_field_exchange_turnover_per_hour",
        near_field_exchange_turnover,
        "1/h",
        tier_1_registry.source_reference(airflow_profile.source_id),
        "Tier 1 screening turnover resolved from the packaged airflow-directionality profile.",
    )
    tracker.add_default(
        "particle_persistence_factor",
        particle_persistence_factor,
        None,
        tier_1_registry.source_reference(particle_profile.source_id),
        "Tier 1 persistence factor resolved from the packaged particle-regime profile.",
    )
    tracker.add_derived(
        "interzonal_mixing_rate_m3_per_hour",
        interzonal_mixing_rate,
        "m3/h",
        "Near-field volume multiplied by the Tier 1 screening exchange turnover plus ventilation.",
    )
    tracker.add_derived(
        "far_field_average_air_concentration_mg_per_m3",
        far_field_average_concentration,
        "mg/m3",
        "Far-field room average derived from the Tier 0 room model over the full exposure window.",
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
        "breathing_zone_time_weighted_average_mg_per_m3",
        breathing_zone_time_weighted_average,
        "mg/m3",
        "Time-weighted breathing-zone average over the full event duration.",
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
    tracker.add_limitation(
        "particle_regime_screening",
        (
            "Particle-size effects use a coarse screening persistence factor and do not model "
            "droplet evaporation, deposition, or full aerosol dynamics."
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
                "method; screening geometry and regime inputs remain fully caller-defined."
            ),
            severity=Severity.INFO,
        )

    return ExposureScenario(
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
            "far_field_average_air_concentration_mg_per_m3": round(
                far_field_average_concentration, 8
            ),
            "near_field_active_spray_concentration_mg_per_m3": round(
                near_field_active_concentration, 8
            ),
            "average_air_concentration_mg_per_m3": round(
                breathing_zone_time_weighted_average, 8
            ),
            "breathing_zone_time_weighted_average_mg_per_m3": round(
                breathing_zone_time_weighted_average, 8
            ),
            "interzonal_mixing_rate_m3_per_hour": round(interzonal_mixing_rate, 8),
            "inhaled_mass_mg_per_day": round(inhaled_mass_mg_day, 8),
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
                    "tier_1_solver_not_implemented",
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
            raise ExposureScenarioError(
                code="inhalation_tier_1_not_implemented",
                message=(
                    "Tier 1 inhalation was requested, but v0.1.0 only implements the Tier-0 "
                    "well-mixed room model."
                ),
                suggestion=(
                    "Use requestedTier=`tier_0` for the current screening model and inspect "
                    "`docs://inhalation-tier-upgrade-guide`, any emitted "
                    "`tierUpgradeAdvisories`, or call "
                    "`exposure_build_inhalation_tier1_screening_scenario` with the "
                    "governed Tier 1 request fields."
                ),
                details={
                    "requestedTier": request.requested_tier.value,
                    "guidanceResource": TIER_1_GUIDANCE_RESOURCE,
                    "stubTool": "exposure_build_inhalation_tier1_screening_scenario",
                },
            )

        product_mass_g_event = resolve_product_mass_g(profile, registry, tracker)
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
            )
            tracker.add_default(
                "aerosolized_fraction",
                aerosolized_fraction,
                "fraction",
                source,
                (
                    "Aerosolized fraction defaulted from "
                    f"application_method='{profile.application_method}' and "
                    f"product_category='{profile.product_category}'."
                ),
            )

        room_defaults, room_source = registry.room_defaults(population.region)
        room_volume_m3 = profile.room_volume_m3
        if room_volume_m3 is None:
            room_volume_m3 = room_defaults["room_volume_m3"]
            tracker.add_default(
                "room_volume_m3",
                room_volume_m3,
                "m3",
                room_source,
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
                room_source,
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
                room_source,
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
        )
        body_weight_kg = resolve_population_value(
            field_name="body_weight_kg",
            supplied_value=population.body_weight_kg,
            population_group=population.population_group,
            registry=registry,
            tracker=tracker,
            unit="kg",
            rationale="Body weight was supplied explicitly for dose normalization.",
        )

        released_mass_mg_event = chemical_mass_mg_event * aerosolized_fraction
        initial_air_concentration = released_mass_mg_event / room_volume_m3
        k = max(air_exchange, 0.0)
        if k == 0:
            average_air_concentration = initial_air_concentration
        else:
            average_air_concentration = initial_air_concentration * (
                (1.0 - math.exp(-k * exposure_duration_hours)) / (k * exposure_duration_hours)
            )
        inhaled_mass_mg_day = (
            average_air_concentration
            * inhalation_rate
            * exposure_duration_hours
            * profile.use_events_per_day
        )
        normalized_dose = inhaled_mass_mg_day / body_weight_kg

        tracker.add_derived(
            "released_mass_mg_per_event",
            released_mass_mg_event,
            "mg/event",
            "Released mass = chemical mass per event x aerosolized fraction.",
        )
        tracker.add_derived(
            "average_air_concentration_mg_per_m3",
            average_air_concentration,
            "mg/m3",
            (
                "Average air concentration derived from a well-mixed room "
                "model with first-order air exchange removal."
            ),
        )
        tracker.add_derived(
            "inhaled_mass_mg_per_day",
            inhaled_mass_mg_day,
            "mg/day",
            "Inhaled mass = average concentration x inhalation rate x event duration x events/day.",
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
                "average_air_concentration_mg_per_m3": round(average_air_concentration, 8),
                "inhaled_mass_mg_per_day": round(inhaled_mass_mg_day, 8),
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
                    "Air exchange is represented as a first-order removal term rather than a "
                    "full airflow or aerosol-dynamics treatment.",
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
