"""Deterministic inhalation screening plugin."""

from __future__ import annotations

import math
from uuid import uuid4

from exposure_scenario_mcp.models import (
    DoseUnit,
    ExposureScenario,
    Route,
    ScenarioClass,
    ScenarioDose,
)
from exposure_scenario_mcp.runtime import (
    ScenarioExecutionContext,
    ScenarioPlugin,
    grams_to_mg,
    resolve_population_value,
    resolve_product_mass_g,
)


class InhalationScreeningPlugin(ScenarioPlugin):
    plugin_id = "inhalation_screening_plugin"
    algorithm_id = "inhalation.room_well_mixed.v1"
    scenario_class = ScenarioClass.INHALATION
    supported_routes = (Route.INHALATION,)

    def build(self, request, context: ScenarioExecutionContext) -> ExposureScenario:
        tracker = context.tracker
        profile = request.product_use_profile
        population = request.population_profile
        registry = context.registry

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
            interpretation_notes=[
                "Deterministic inhalation screening scenario using a well-mixed room assumption.",
                "Air exchange acts as a first-order removal term rather than a full CFD treatment.",
            ],
        )
