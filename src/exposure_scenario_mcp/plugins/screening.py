"""Deterministic dermal and oral screening plugin."""

from __future__ import annotations

from uuid import uuid4

from exposure_scenario_mcp.errors import ensure
from exposure_scenario_mcp.models import (
    DoseUnit,
    ExposureScenario,
    Route,
    ScenarioClass,
    ScenarioDose,
    TierLevel,
)
from exposure_scenario_mcp.runtime import (
    ScenarioExecutionContext,
    ScenarioPlugin,
    grams_to_mg,
    resolve_population_value,
    resolve_product_mass_g,
)


class ScreeningScenarioPlugin(ScenarioPlugin):
    plugin_id = "screening_scenario_plugin"
    algorithm_id = "screening.external_dose.v1"
    scenario_class = ScenarioClass.SCREENING
    supported_routes = (Route.DERMAL, Route.ORAL)

    def build(self, request, context: ScenarioExecutionContext) -> ExposureScenario:
        ensure(
            request.route in self.supported_routes,
            "screening_route_unsupported",
            (
                f"Route '{request.route.value}' is not supported by the "
                "deterministic screening plugin."
            ),
            suggestion="Use the inhalation-specific tool for inhalation scenarios.",
        )

        tracker = context.tracker
        profile = request.product_use_profile
        population = request.population_profile
        registry = context.registry

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

        body_weight_kg = resolve_population_value(
            field_name="body_weight_kg",
            supplied_value=population.body_weight_kg,
            population_group=population.population_group,
            registry=registry,
            tracker=tracker,
            unit="kg",
            rationale="Body weight was supplied explicitly for dose normalization.",
        )

        if request.route == Route.DERMAL:
            if profile.application_strip_length_cm is not None:
                tracker.add_user(
                    "application_strip_length_cm",
                    profile.application_strip_length_cm,
                    "cm",
                    "Topical strip-length application geometry was supplied explicitly.",
                )
            if profile.application_coverage_context is not None:
                tracker.add_user(
                    "application_coverage_context",
                    profile.application_coverage_context,
                    "context",
                    "Topical application coverage context was supplied explicitly.",
                )
            if profile.retention_factor is not None:
                tracker.add_user(
                    "retention_factor",
                    profile.retention_factor,
                    "fraction",
                    "Dermal retention factor was supplied explicitly.",
                )
                retention_factor = profile.retention_factor
            else:
                retention_factor, source = registry.retention_factor(
                    profile.retention_type,
                    profile.product_category,
                )
                tracker.add_default(
                    "retention_factor",
                    retention_factor,
                    "fraction",
                    source,
                    f"Retention factor defaulted from retention_type='{profile.retention_type}'.",
                )

            if profile.transfer_efficiency is not None:
                tracker.add_user(
                    "transfer_efficiency",
                    profile.transfer_efficiency,
                    "fraction",
                    "Transfer efficiency was supplied explicitly.",
                )
                transfer_efficiency = profile.transfer_efficiency
            else:
                transfer_efficiency, source = registry.transfer_efficiency(
                    profile.application_method,
                    profile.product_category,
                )
                tracker.add_default(
                    "transfer_efficiency",
                    transfer_efficiency,
                    "fraction",
                    source,
                    (
                        "Transfer efficiency defaulted from "
                        f"application_method='{profile.application_method}' and "
                        f"product_category='{profile.product_category}'."
                    ),
                )

            external_mass_mg_day = (
                chemical_mass_mg_event
                * profile.use_events_per_day
                * retention_factor
                * transfer_efficiency
            )
            tracker.add_derived(
                "external_mass_mg_per_day",
                external_mass_mg_day,
                "mg/day",
                (
                    "Dermal external mass = chemical mass per event x "
                    "events/day x retention x transfer efficiency."
                ),
            )
            surface_area_cm2 = resolve_population_value(
                field_name="exposed_surface_area_cm2",
                supplied_value=population.exposed_surface_area_cm2,
                population_group=population.population_group,
                registry=registry,
                tracker=tracker,
                unit="cm2",
                rationale="Exposed surface area was supplied explicitly for route metrics.",
            )
            route_metrics = {
                "chemical_mass_mg_per_event": round(chemical_mass_mg_event, 8),
                "external_mass_mg_per_day": round(external_mass_mg_day, 8),
                "surface_loading_mg_per_cm2_day": round(external_mass_mg_day / surface_area_cm2, 8),
            }
            if profile.application_strip_length_cm is not None:
                route_metrics["application_strip_length_cm"] = round(
                    profile.application_strip_length_cm, 8
                )
            if profile.application_coverage_context is not None:
                route_metrics["application_coverage_context"] = profile.application_coverage_context
            notes = [
                "Deterministic dermal screening scenario using explicit "
                "retention and transfer modifiers."
            ]
        else:
            if profile.ingestion_fraction is not None:
                tracker.add_user(
                    "ingestion_fraction",
                    profile.ingestion_fraction,
                    "fraction",
                    "Oral ingestion fraction was supplied explicitly.",
                )
                ingestion_fraction = profile.ingestion_fraction
            else:
                ingestion_fraction, source = registry.ingestion_fraction(
                    profile.application_method,
                    profile.product_category,
                )
                tracker.add_default(
                    "ingestion_fraction",
                    ingestion_fraction,
                    "fraction",
                    source,
                    (
                        "Ingestion fraction defaulted from "
                        f"application_method='{profile.application_method}' and "
                        f"product_category='{profile.product_category}'."
                    ),
                )

            external_mass_mg_day = (
                chemical_mass_mg_event * profile.use_events_per_day * ingestion_fraction
            )
            tracker.add_derived(
                "external_mass_mg_per_day",
                external_mass_mg_day,
                "mg/day",
                "Oral external mass = chemical mass per event x events/day x ingestion fraction.",
            )
            route_metrics = {
                "chemical_mass_mg_per_event": round(chemical_mass_mg_event, 8),
                "external_mass_mg_per_day": round(external_mass_mg_day, 8),
            }
            notes = ["Deterministic oral screening scenario using explicit ingestion semantics."]

        normalized_dose = external_mass_mg_day / body_weight_kg
        tracker.add_derived(
            "normalized_external_dose_mg_per_kg_day",
            normalized_dose,
            "mg/kg-day",
            "Normalized external dose = external mass per day / body weight.",
        )

        return ExposureScenario(
            scenario_id=f"exp-{uuid4().hex[:12]}",
            chemical_id=request.chemical_id,
            chemical_name=request.chemical_name,
            route=request.route,
            scenario_class=ScenarioClass.SCREENING,
            external_dose=ScenarioDose(
                metric="normalized_external_dose",
                value=round(normalized_dose, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            ),
            product_use_profile=profile,
            population_profile=population.model_copy(update={"body_weight_kg": body_weight_kg}),
            route_metrics=route_metrics,
            assumptions=tracker.assumptions,
            provenance=tracker.provenance(self.plugin_id, self.algorithm_id),
            limitations=tracker.limitations,
            quality_flags=tracker.quality_flags,
            fit_for_purpose=tracker.fit_for_purpose("deterministic_screening"),
            tier_semantics=tracker.tier_semantics(
                tier_claimed=TierLevel.TIER_0,
                tier_rationale=(
                    "Route-specific external exposure is produced with deterministic screening "
                    "equations and may rely on default factor packs."
                ),
                required_caveats=(
                    [
                        "Interpret the result as an external dermal load at the skin boundary; "
                        "it does not include dermal absorption."
                    ]
                    if request.route == Route.DERMAL
                    else [
                        "Interpret the result as external oral intake mass; it does not include "
                        "oral absorption or internal dose translation."
                    ]
                ),
                forbidden_interpretations=(
                    [
                        "Do not interpret this screening result as absorbed dermal dose, "
                        "systemic exposure, or a final risk conclusion."
                    ]
                    if request.route == Route.DERMAL
                    else [
                        "Do not interpret this screening result as absorbed oral dose, "
                        "systemic exposure, or a final risk conclusion."
                    ]
                ),
            ),
            interpretation_notes=notes,
        )
