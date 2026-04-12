"""Tier A/B uncertainty helpers for deterministic scenario outputs."""

from __future__ import annotations

import math
from statistics import median
from typing import Literal
from uuid import uuid4

from exposure_scenario_mcp.archetypes import (
    ArchetypeLibraryRegistry,
    build_envelope_input_from_library,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError, ensure
from exposure_scenario_mcp.models import (
    ArchetypeLibrarySet,
    BiasDirection,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    BuildParameterBoundsInput,
    DependencyDescriptor,
    DependencyHandlingStrategy,
    DependencyRelationship,
    EnvelopeArchetypeResult,
    EnvelopeDriverAttribution,
    ExposureEnvelopeSummary,
    ExposureScenario,
    ExposureScenarioRequest,
    InhalationResidualAirReentryScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    MonotonicDirection,
    MonotonicityCheck,
    ParameterBoundInput,
    ParameterBoundsSummary,
    Route,
    ScenarioDose,
    SensitivityDirection,
    SensitivityRankingEntry,
    TierLevel,
    UncertaintyQuantificationStatus,
    UncertaintyRegisterEntry,
    UncertaintyTier,
    UncertaintyType,
    ValidationEvidenceReadiness,
    ValidationStatus,
    ValidationSummary,
)
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.validation import build_validation_summary

PERTURBATION_FRACTION = 0.1
SENSITIVITY_FIELD_MAP = {
    "concentration_fraction": ("product_use_profile", "concentration_fraction"),
    "use_amount_per_event": ("product_use_profile", "use_amount_per_event"),
    "use_events_per_day": ("product_use_profile", "use_events_per_day"),
    "density_g_per_ml": ("product_use_profile", "density_g_per_ml"),
    "retention_factor": ("product_use_profile", "retention_factor"),
    "transfer_efficiency": ("product_use_profile", "transfer_efficiency"),
    "ingestion_fraction": ("product_use_profile", "ingestion_fraction"),
    "aerosolized_fraction": ("product_use_profile", "aerosolized_fraction"),
    "room_volume_m3": ("product_use_profile", "room_volume_m3"),
    "air_exchange_rate_per_hour": ("product_use_profile", "air_exchange_rate_per_hour"),
    "exposure_duration_hours": ("product_use_profile", "exposure_duration_hours"),
    "body_weight_kg": ("population_profile", "body_weight_kg"),
    "inhalation_rate_m3_per_hour": ("population_profile", "inhalation_rate_m3_per_hour"),
    "air_concentration_at_reentry_start_mg_per_m3": (
        "request",
        "air_concentration_at_reentry_start_mg_per_m3",
    ),
    "additional_decay_rate_per_hour": ("request", "additional_decay_rate_per_hour"),
    "source_distance_m": ("request", "source_distance_m"),
    "spray_duration_seconds": ("request", "spray_duration_seconds"),
    "near_field_volume_m3": ("request", "near_field_volume_m3"),
}
BOUNDS_PARAMETER_CONFIG: dict[
    str, dict[str, set[Route] | MonotonicDirection | bool]
] = {
    "concentration_fraction": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL, Route.ORAL, Route.INHALATION},
    },
    "use_amount_per_event": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL, Route.ORAL, Route.INHALATION},
    },
    "use_events_per_day": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL, Route.ORAL, Route.INHALATION},
    },
    "density_g_per_ml": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL, Route.ORAL, Route.INHALATION},
        "requires_ml_amount": True,
    },
    "retention_factor": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL},
    },
    "transfer_efficiency": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.DERMAL},
    },
    "ingestion_fraction": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.ORAL},
    },
    "aerosolized_fraction": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "room_volume_m3": {
        "direction": MonotonicDirection.INCREASE_DECREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "air_exchange_rate_per_hour": {
        "direction": MonotonicDirection.INCREASE_DECREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "exposure_duration_hours": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "body_weight_kg": {
        "direction": MonotonicDirection.INCREASE_DECREASES_DOSE,
        "routes": {Route.DERMAL, Route.ORAL, Route.INHALATION},
    },
    "inhalation_rate_m3_per_hour": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "air_concentration_at_reentry_start_mg_per_m3": {
        "direction": MonotonicDirection.INCREASE_INCREASES_DOSE,
        "routes": {Route.INHALATION},
    },
    "additional_decay_rate_per_hour": {
        "direction": MonotonicDirection.INCREASE_DECREASES_DOSE,
        "routes": {Route.INHALATION},
    },
}

LIMITATION_UNCERTAINTY_MAP = {
    "breathing_zone_not_modeled": (
        [UncertaintyType.MODEL_UNCERTAINTY, UncertaintyType.SCENARIO_UNCERTAINTY],
        BiasDirection.LIKELY_UNDER,
        "high",
    ),
    "near_field_exchange_screening": (
        [UncertaintyType.MODEL_UNCERTAINTY, UncertaintyType.SCENARIO_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "high",
    ),
    "particle_regime_screening": (
        [UncertaintyType.MODEL_UNCERTAINTY, UncertaintyType.PARAMETER_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "medium",
    ),
    "cross_route_aggregate": (
        [UncertaintyType.MODEL_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "high",
    ),
    "pbpk_event_duration_missing": (
        [UncertaintyType.SCENARIO_UNCERTAINTY],
        BiasDirection.UNKNOWN,
        "medium",
    ),
    "treated_surface_emission_not_modeled": (
        [UncertaintyType.MODEL_UNCERTAINTY, UncertaintyType.SCENARIO_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "high",
    ),
    "reentry_air_anchor_required": (
        [UncertaintyType.SCENARIO_UNCERTAINTY, UncertaintyType.PARAMETER_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "high",
    ),
    "extrathoracic_oral_handoff_screening": (
        [UncertaintyType.MODEL_UNCERTAINTY, UncertaintyType.PARAMETER_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "medium",
    ),
    "worker_task_intensity_screening": (
        [UncertaintyType.SCENARIO_UNCERTAINTY, UncertaintyType.PARAMETER_UNCERTAINTY],
        BiasDirection.BIDIRECTIONAL,
        "medium",
    ),
}


def request_from_scenario(scenario: ExposureScenario) -> ExposureScenarioRequest:
    assumption_values = {item.name: item.value for item in scenario.assumptions}
    if (
        scenario.route == Route.INHALATION
        and scenario.tier_semantics.tier_claimed == TierLevel.TIER_1
    ):
        return InhalationTier1ScenarioRequest(
            chemical_id=scenario.chemical_id,
            chemical_name=scenario.chemical_name,
            route=scenario.route,
            scenario_class=scenario.scenario_class,
            product_use_profile=scenario.product_use_profile,
            population_profile=scenario.population_profile,
            source_distance_m=float(assumption_values["source_distance_m"]),
            spray_duration_seconds=float(assumption_values["spray_duration_seconds"]),
            near_field_volume_m3=float(assumption_values["near_field_volume_m3"]),
            airflow_directionality=str(assumption_values["airflow_directionality"]),
            particle_size_regime=str(assumption_values["particle_size_regime"]),
            assumption_overrides={},
        )
    if (
        scenario.route == Route.INHALATION
        and scenario.product_use_profile.application_method == "residual_air_reentry"
    ):
        return InhalationResidualAirReentryScenarioRequest(
            chemical_id=scenario.chemical_id,
            chemical_name=scenario.chemical_name,
            route=scenario.route,
            scenario_class=scenario.scenario_class,
            product_use_profile=scenario.product_use_profile,
            population_profile=scenario.population_profile,
            air_concentration_at_reentry_start_mg_per_m3=float(
                assumption_values["air_concentration_at_reentry_start_mg_per_m3"]
            ),
            additional_decay_rate_per_hour=float(
                assumption_values["additional_decay_rate_per_hour"]
            ),
            post_application_delay_hours=float(assumption_values["post_application_delay_hours"]),
            assumption_overrides={},
        )
    request_cls = (
        InhalationScenarioRequest if scenario.route == Route.INHALATION else ExposureScenarioRequest
    )
    return request_cls(
        chemical_id=scenario.chemical_id,
        chemical_name=scenario.chemical_name,
        route=scenario.route,
        scenario_class=scenario.scenario_class,
        product_use_profile=scenario.product_use_profile,
        population_profile=scenario.population_profile,
        assumption_overrides={},
    )


def _with_override(
    request: ExposureScenarioRequest,
    assumption_name: str,
    value: float,
) -> ExposureScenarioRequest:
    target = SENSITIVITY_FIELD_MAP[assumption_name]
    if target[0] == "request":
        return request.model_copy(update={target[1]: value})
    if target[0] == "product_use_profile":
        return request.model_copy(
            update={
                "product_use_profile": request.product_use_profile.model_copy(
                    update={target[1]: value}
                )
            }
        )
    return request.model_copy(
        update={
            "population_profile": request.population_profile.model_copy(update={target[1]: value})
        }
    )


def _build_request_scenario(engine, request: ExposureScenarioRequest) -> ExposureScenario:
    if isinstance(request, InhalationTier1ScenarioRequest):
        from exposure_scenario_mcp.plugins.inhalation import (
            build_inhalation_tier_1_screening_scenario,
        )

        return build_inhalation_tier_1_screening_scenario(request, engine.defaults_registry)
    if isinstance(request, InhalationResidualAirReentryScenarioRequest):
        from exposure_scenario_mcp.plugins.inhalation import (
            build_inhalation_residual_air_reentry_scenario,
        )

        return build_inhalation_residual_air_reentry_scenario(
            request,
            engine.defaults_registry,
        )
    return engine.build(request, include_diagnostics=False)


def _bound_config(parameter_name: str) -> dict[str, set[Route] | MonotonicDirection | bool]:
    ensure(
        parameter_name in BOUNDS_PARAMETER_CONFIG,
        "bounds_parameter_unsupported",
        f"Parameter `{parameter_name}` is not supported for bounds propagation.",
        suggestion=(
            "Use one of: "
            + ", ".join(f"`{name}`" for name in sorted(BOUNDS_PARAMETER_CONFIG))
            + "."
        ),
    )
    return BOUNDS_PARAMETER_CONFIG[parameter_name]


def _validate_bound_input(
    base_request: ExposureScenarioRequest,
    bound: ParameterBoundInput,
) -> dict[str, set[Route] | MonotonicDirection | bool]:
    config = _bound_config(bound.parameter_name)
    supported_routes = config["routes"]
    ensure(
        base_request.route in supported_routes,
        "bounds_parameter_route_mismatch",
        (
            f"Parameter `{bound.parameter_name}` is not valid for route "
            f"`{base_request.route.value}`."
        ),
        suggestion="Choose parameter bounds that are route-relevant for the base request.",
    )
    if config.get("requires_ml_amount"):
        ensure(
            base_request.product_use_profile.use_amount_unit.value == "mL",
            "bounds_parameter_context_mismatch",
            (
                f"Parameter `{bound.parameter_name}` requires a volume-based use amount "
                "so density can affect the scenario."
            ),
            suggestion="Use an mL-based scenario or bound a different parameter.",
        )
    return config


def _bounds_requests(
    base_request: ExposureScenarioRequest,
    bounded_parameters: list[ParameterBoundInput],
) -> tuple[ExposureScenarioRequest, ExposureScenarioRequest]:
    min_request = base_request
    max_request = base_request
    for bound in bounded_parameters:
        config = _validate_bound_input(base_request, bound)
        direction = config["direction"]
        if direction == MonotonicDirection.INCREASE_INCREASES_DOSE:
            min_value, max_value = bound.lower_value, bound.upper_value
        else:
            min_value, max_value = bound.upper_value, bound.lower_value
        min_request = _with_override(min_request, bound.parameter_name, min_value)
        max_request = _with_override(max_request, bound.parameter_name, max_value)
    return min_request, max_request


def _monotonicity_checks(
    base_request: ExposureScenarioRequest,
    bounded_parameters: list[ParameterBoundInput],
    engine,
) -> list[MonotonicityCheck]:
    checks: list[MonotonicityCheck] = []
    for bound in bounded_parameters:
        config = _validate_bound_input(base_request, bound)
        lower_request = _with_override(base_request, bound.parameter_name, bound.lower_value)
        upper_request = _with_override(base_request, bound.parameter_name, bound.upper_value)
        lower_scenario = engine.build(lower_request, include_diagnostics=False)
        upper_scenario = engine.build(upper_request, include_diagnostics=False)
        direction = config["direction"]
        if direction == MonotonicDirection.INCREASE_INCREASES_DOSE:
            status = (
                "pass"
                if upper_scenario.external_dose.value >= lower_scenario.external_dose.value
                else "blocked"
            )
        else:
            status = (
                "pass"
                if upper_scenario.external_dose.value <= lower_scenario.external_dose.value
                else "blocked"
            )
        checks.append(
            MonotonicityCheck(
                parameter_name=bound.parameter_name,
                expected_direction=direction,
                lower_dose=round(lower_scenario.external_dose.value, 8),
                upper_dose=round(upper_scenario.external_dose.value, 8),
                status=status,
                note=(
                    "Monotonicity check compares single-parameter lower and upper bounds "
                    "against the deterministic base scenario."
                ),
            )
        )
    return checks


def build_sensitivity_ranking(engine, scenario: ExposureScenario) -> list[SensitivityRankingEntry]:
    base_value = scenario.external_dose.value
    request = request_from_scenario(scenario)
    ranking: list[SensitivityRankingEntry] = []
    for assumption in scenario.assumptions:
        if assumption.name not in SENSITIVITY_FIELD_MAP:
            continue
        if not isinstance(assumption.value, (int, float)):
            continue
        baseline_value = float(assumption.value)
        if baseline_value <= 0:
            continue
        perturbed_value = round(baseline_value * (1.0 + PERTURBATION_FRACTION), 8)
        try:
            perturbed_request = _with_override(request, assumption.name, perturbed_value)
            perturbed_scenario = _build_request_scenario(engine, perturbed_request)
        except (ExposureScenarioError, ValueError):
            continue
        absolute_delta = round(perturbed_scenario.external_dose.value - base_value, 8)
        percent_delta = (
            None
            if math.isclose(base_value, 0.0)
            else round((absolute_delta / base_value) * 100.0, 6)
        )
        elasticity = (
            None
            if math.isclose(base_value, 0.0)
            else round((absolute_delta / base_value) / PERTURBATION_FRACTION, 6)
        )
        direction = (
            SensitivityDirection.POSITIVE
            if absolute_delta > 0
            else SensitivityDirection.NEGATIVE
            if absolute_delta < 0
            else SensitivityDirection.NEUTRAL
        )
        ranking.append(
            SensitivityRankingEntry(
                parameter_name=assumption.name,
                source_kind=assumption.source_kind,
                baseline_value=round(baseline_value, 8),
                perturbed_value=perturbed_value,
                unit=assumption.unit,
                perturbation_fraction=PERTURBATION_FRACTION,
                response_metric=scenario.external_dose.metric,
                absolute_delta=absolute_delta,
                percent_delta=percent_delta,
                elasticity=elasticity,
                direction=direction,
            )
        )
    ranking.sort(
        key=lambda item: (
            abs(item.elasticity or 0.0),
            abs(item.absolute_delta),
            item.parameter_name,
        ),
        reverse=True,
    )
    return ranking[:8]


def build_dependency_metadata(scenario: ExposureScenario) -> list[DependencyDescriptor]:
    profile = scenario.product_use_profile
    population = scenario.population_profile
    items: list[DependencyDescriptor] = [
        DependencyDescriptor(
            dependency_id="use-intensity-cluster",
            title="Use amount and frequency should be treated as a behavioral package",
            relationship_type=DependencyRelationship.BEHAVIORAL,
            assumption_names=["use_amount_per_event", "use_events_per_day"],
            handling_strategy=DependencyHandlingStrategy.SCENARIO_PACKAGED,
            note=(
                "Tier A/B keeps use amount and use frequency in named scenario packages instead "
                "of sampling them independently."
            ),
        )
    ]
    if population.body_weight_kg is not None and (
        population.exposed_surface_area_cm2 is not None
        or population.inhalation_rate_m3_per_hour is not None
    ):
        items.append(
            DependencyDescriptor(
                dependency_id="body-size-scaling-cluster",
                title="Body size and physiology should scale together",
                relationship_type=DependencyRelationship.PHYSIOLOGICAL,
                assumption_names=[
                    name
                    for name in [
                        "body_weight_kg",
                        "exposed_surface_area_cm2",
                        "inhalation_rate_m3_per_hour",
                    ]
                    if any(record.name == name for record in scenario.assumptions)
                ],
                handling_strategy=DependencyHandlingStrategy.JOINT_MODEL_REQUIRED,
                note=(
                    "Future probabilistic tiers should use a joint physiological model rather "
                    "than independent sampling."
                ),
            )
        )
    if scenario.route == Route.INHALATION:
        items.append(
            DependencyDescriptor(
                dependency_id="room-context-cluster",
                title="Room size, ventilation, and duration form one scenario context",
                relationship_type=DependencyRelationship.SCENARIO_PACKAGE,
                assumption_names=[
                    "room_volume_m3",
                    "air_exchange_rate_per_hour",
                    "exposure_duration_hours",
                ],
                handling_strategy=DependencyHandlingStrategy.SCENARIO_PACKAGED,
                note=(
                    "Microenvironment parameters should be changed as coherent room archetypes "
                    "instead of independent marginals."
                ),
            )
        )
    if profile.application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}:
        items.append(
            DependencyDescriptor(
                dependency_id="spray-mechanism-cluster",
                title="Aerosol release depends on spray mechanism and physical form",
                relationship_type=DependencyRelationship.MECHANISTIC,
                assumption_names=[
                    "aerosolized_fraction",
                    "application_method",
                    "physical_form",
                ],
                handling_strategy=DependencyHandlingStrategy.CONDITIONAL_MODEL_REQUIRED,
                note=(
                    "Later uncertainty tiers should condition aerosol release on the spray "
                    "mechanism rather than sample it independently."
                ),
            )
        )
    if (
        scenario.route == Route.INHALATION
        and scenario.tier_semantics.tier_claimed == TierLevel.TIER_1
    ):
        items.append(
            DependencyDescriptor(
                dependency_id="near-field-geometry-cluster",
                title="Tier 1 NF/FF geometry and timing should move together",
                relationship_type=DependencyRelationship.SCENARIO_PACKAGE,
                assumption_names=[
                    "source_distance_m",
                    "spray_duration_seconds",
                    "near_field_volume_m3",
                    "airflow_directionality",
                    "particle_size_regime",
                ],
                handling_strategy=DependencyHandlingStrategy.SCENARIO_PACKAGED,
                note=(
                    "Tier 1 spray geometry, timing, and airflow classes should remain a "
                    "coherent scenario package rather than independent marginals."
                ),
            )
        )
    return items


def _impact_from_sensitivity(
    parameter_name: str,
    sensitivity_ranking: list[SensitivityRankingEntry],
) -> Literal["low", "medium", "high"]:
    match = next(
        (item for item in sensitivity_ranking if item.parameter_name == parameter_name),
        None,
    )
    if match is None or match.elasticity is None:
        return "medium"
    elasticity = abs(match.elasticity)
    if elasticity >= 0.8:
        return "high"
    if elasticity >= 0.3:
        return "medium"
    return "low"


def _mechanistic_constraint_entries(
    scenario: ExposureScenario,
    sensitivity_ranking: list[SensitivityRankingEntry],
) -> list[UncertaintyRegisterEntry]:
    entries: list[UncertaintyRegisterEntry] = []
    route_metrics = scenario.route_metrics
    assumption_names = {item.name for item in scenario.assumptions}

    def _related(*names: str) -> list[str]:
        return [name for name in names if name in assumption_names]

    deposition_rate = route_metrics.get("deposition_rate_per_hour")
    if scenario.route == Route.INHALATION and isinstance(deposition_rate, int | float):
        if float(deposition_rate) > 0.0:
            entries.append(
                UncertaintyRegisterEntry(
                    entry_id="mechanistic-constraint-deposition-sink",
                    title="Bounded aerosol deposition sink constrains inhalation persistence",
                    uncertainty_types=[
                        UncertaintyType.MODEL_UNCERTAINTY,
                        UncertaintyType.PARAMETER_UNCERTAINTY,
                    ],
                    related_assumptions=_related(
                        "particle_size_regime",
                        "air_exchange_rate_per_hour",
                        "exposure_duration_hours",
                    ),
                    quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                    bias_direction=BiasDirection.BIDIRECTIONAL,
                    impact_level=_impact_from_sensitivity(
                        "air_exchange_rate_per_hour", sensitivity_ranking
                    ),
                    summary=(
                        "Inhalation persistence is reduced with a bounded first-order "
                        "deposition sink rather than a full aerosol deposition and "
                        "evaporation solver."
                    ),
                    recommendation=(
                        "Treat deposition-sensitive spray outputs as physically bounded "
                        "screening estimates and prefer benchmarked particle families."
                    ),
                )
            )

    if bool(route_metrics.get("saturation_cap_applied")):
        entries.append(
            UncertaintyRegisterEntry(
                entry_id="mechanistic-constraint-saturation-cap-active",
                title="Volatility saturation cap actively constrained inhalation concentration",
                uncertainty_types=[
                    UncertaintyType.MODEL_UNCERTAINTY,
                    UncertaintyType.PARAMETER_UNCERTAINTY,
                ],
                related_assumptions=_related(
                    "vapor_pressure_mmhg",
                    "molecular_weight_g_per_mol",
                    "room_volume_m3",
                ),
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.BIDIRECTIONAL,
                impact_level="high",
                summary=(
                    "The modeled air concentration exceeded the bounded thermodynamic ceiling "
                    "and was clamped to a room-temperature saturation cap."
                ),
                recommendation=(
                    "Review volatility inputs and treat the result as a cap-bounded screening "
                    "estimate rather than a free unconstrained spray concentration."
                ),
            )
        )

    aerosol_volume_factor = next(
        (
            item.value
            for item in scenario.assumptions
            if item.name == "pressurized_aerosol_volume_interpretation_factor"
        ),
        None,
    )
    if isinstance(aerosol_volume_factor, int | float) and float(aerosol_volume_factor) < 1.0:
        entries.append(
            UncertaintyRegisterEntry(
                entry_id="mechanistic-constraint-pressurized-aerosol-volume-interpretation",
                title="Pressurized aerosol volume was bounded before mass conversion",
                uncertainty_types=[
                    UncertaintyType.MODEL_UNCERTAINTY,
                    UncertaintyType.PARAMETER_UNCERTAINTY,
                ],
                related_assumptions=_related(
                    "use_amount_per_event",
                    "density_g_per_ml",
                    "pressurized_aerosol_volume_interpretation_factor",
                ),
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.BIDIRECTIONAL,
                impact_level=_impact_from_sensitivity("use_amount_per_event", sensitivity_ranking),
                summary=(
                    "Volumetric aerosol product mass was reduced with a bounded "
                    "pressurized-aerosol interpretation factor instead of treating the "
                    "declared can volume as fully condensed liquid mass."
                ),
                recommendation=(
                    "Prefer product-specific mass-per-event or explicit density semantics "
                    "for pressurized aerosols when higher-confidence route realism is needed."
                ),
            )
        )

    reentry_mode = str(route_metrics.get("reentry_mode") or "").strip().lower()
    if reentry_mode == "native_treated_surface_reentry":
        entries.append(
            UncertaintyRegisterEntry(
                entry_id="mechanistic-constraint-native-treated-surface-source",
                title="Native treated-surface reentry uses a bounded first-order source term",
                uncertainty_types=[
                    UncertaintyType.MODEL_UNCERTAINTY,
                    UncertaintyType.SCENARIO_UNCERTAINTY,
                ],
                related_assumptions=_related(
                    "treated_surface_chemical_mass_mg_initial",
                    "surface_emission_rate_per_hour",
                    "post_application_delay_hours",
                ),
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.BIDIRECTIONAL,
                impact_level="high",
                summary=(
                    "Residual-air reentry was derived from a bounded native treated-surface "
                    "source term rather than a full indoor partitioning or furnishing uptake "
                    "model."
                ),
                recommendation=(
                    "Use the native treated-surface branch for same-room screening and prefer "
                    "measured reentry air or richer emission data when available."
                ),
            )
        )

    swallowed_mass = route_metrics.get("swallowed_extrathoracic_mass_mg_per_day")
    if scenario.route == Route.INHALATION and isinstance(swallowed_mass, int | float):
        if float(swallowed_mass) > 0.0:
            entries.append(
                UncertaintyRegisterEntry(
                    entry_id="mechanistic-constraint-extrathoracic-handoff",
                    title=(
                        "Coarse-spray extrathoracic swallowing is represented as a bounded "
                        "handoff"
                    ),
                    uncertainty_types=[
                        UncertaintyType.MODEL_UNCERTAINTY,
                        UncertaintyType.PARAMETER_UNCERTAINTY,
                    ],
                    related_assumptions=_related("particle_size_regime"),
                    quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                    bias_direction=BiasDirection.BIDIRECTIONAL,
                    impact_level=_impact_from_sensitivity(
                        "inhalation_rate_m3_per_hour", sensitivity_ranking
                    ),
                    summary=(
                        "A portion of spray mass is routed to extrathoracic swallowing with a "
                        "bounded regime-dependent screening fraction."
                    ),
                    recommendation=(
                        "Keep inhalation and incidental-oral interpretation linked for coarse "
                        "sprays and avoid treating the handoff as a deposition dosimetry model."
                    ),
                )
            )

    if bool(route_metrics.get("interzonal_mixing_floor_applied")):
        entries.append(
            UncertaintyRegisterEntry(
                entry_id="mechanistic-constraint-tier1-local-entrainment-floor",
                title="Tier 1 NF/FF interzonal mixing was bounded by a local entrainment floor",
                uncertainty_types=[
                    UncertaintyType.MODEL_UNCERTAINTY,
                    UncertaintyType.PARAMETER_UNCERTAINTY,
                ],
                related_assumptions=_related(
                    "near_field_volume_m3",
                    "source_distance_m",
                    "thermal_plume_rate_m3_per_hour",
                    "spray_jet_rate_m3_per_hour",
                ),
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.BIDIRECTIONAL,
                impact_level=_impact_from_sensitivity(
                    "near_field_volume_m3", sensitivity_ranking
                ),
                summary=(
                    "The Tier 1 near-field/far-field solver bounded weak static interzonal "
                    "mixing upward with a local entrainment floor from thermal-plume and "
                    "spray-jet heuristics."
                ),
                recommendation=(
                    "Treat floor-bound Tier 1 outputs as physically bounded screening results "
                    "and prefer measured local airflow or validated task-family anchors when "
                    "available."
                ),
            )
        )

    return entries


def build_uncertainty_register(
    scenario: ExposureScenario,
    sensitivity_ranking: list[SensitivityRankingEntry],
    dependency_metadata: list[DependencyDescriptor],
) -> list[UncertaintyRegisterEntry]:
    entries = [
        UncertaintyRegisterEntry(
            entry_id="tier-a-model-boundary",
            title="Tier A deterministic screening boundary remains in force",
            uncertainty_types=[UncertaintyType.MODEL_UNCERTAINTY],
            related_assumptions=[],
            quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
            bias_direction=BiasDirection.UNKNOWN,
            impact_level="high",
            summary=(
                f"The current result is governed as {scenario.uncertainty_tier.value} and "
                f"{scenario.tier_semantics.tier_claimed.value}; it is auditable but not "
                "probabilistic."
            ),
            recommendation=(
                "Use named scenario envelopes for Tier B refinement before attempting "
                "probabilistic propagation."
            ),
        )
    ]
    entries.extend(_mechanistic_constraint_entries(scenario, sensitivity_ranking))
    for assumption in scenario.assumptions:
        governance = assumption.governance
        if governance.evidence_basis.value not in {"heuristic_default", "curated_default"}:
            continue
        if governance.default_visibility.value == "silent_traceable" and (
            governance.applicability_status.value != "screening_extrapolation"
        ):
            continue
        entries.append(
            UncertaintyRegisterEntry(
                entry_id=f"assumption-{assumption.name}",
                title=f"Resolved assumption `{assumption.name}` carries default uncertainty",
                uncertainty_types=governance.uncertainty_types,
                related_assumptions=[assumption.name],
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.UNKNOWN,
                impact_level=_impact_from_sensitivity(assumption.name, sensitivity_ranking),
                summary=(
                    f"`{assumption.name}` resolved as `{governance.evidence_basis.value}` with "
                    f"`{governance.applicability_status.value}` status."
                ),
                recommendation=(
                    "Replace this default with scenario-specific evidence or include it in a "
                    "Tier B envelope as an explicit variant driver."
                ),
            )
        )
    for limitation in scenario.limitations:
        uncertainty_types, bias_direction, impact_level = LIMITATION_UNCERTAINTY_MAP.get(
            limitation.code,
            ([UncertaintyType.SCENARIO_UNCERTAINTY], BiasDirection.UNKNOWN, "medium"),
        )
        entries.append(
            UncertaintyRegisterEntry(
                entry_id=f"limitation-{limitation.code}",
                title=f"Limitation `{limitation.code}` remains unquantified",
                uncertainty_types=uncertainty_types,
                related_assumptions=[],
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=bias_direction,
                impact_level=impact_level,
                summary=limitation.message,
                recommendation=(
                    "Treat this as a model or scenario uncertainty and keep it visible in "
                    "downstream interpretation."
                ),
            )
        )
    if dependency_metadata:
        entries.append(
            UncertaintyRegisterEntry(
                entry_id="dependency-handling-required",
                title="Known dependencies are preserved qualitatively, not numerically",
                uncertainty_types=[
                    UncertaintyType.VARIABILITY,
                    UncertaintyType.SCENARIO_UNCERTAINTY,
                ],
                related_assumptions=sorted(
                    {
                        name
                        for dependency in dependency_metadata
                        for name in dependency.assumption_names
                    }
                ),
                quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
                bias_direction=BiasDirection.UNKNOWN,
                impact_level="high",
                summary=(
                    "The output carries known dependence structures, but no joint sampling or "
                    "correlation model is applied in Tier A."
                ),
                recommendation=(
                    "Use scenario packaging for Tier B and reserve probabilistic propagation for "
                    "later tiers with explicit joint models."
                ),
            )
        )
    return entries


def enrich_scenario_uncertainty(engine, scenario: ExposureScenario) -> ExposureScenario:
    sensitivity_ranking = build_sensitivity_ranking(engine, scenario)
    dependency_metadata = build_dependency_metadata(scenario)
    validation_summary = build_validation_summary(scenario)
    uncertainty_register = build_uncertainty_register(
        scenario,
        sensitivity_ranking=sensitivity_ranking,
        dependency_metadata=dependency_metadata,
    )
    return scenario.model_copy(
        update={
            "uncertainty_tier": UncertaintyTier.TIER_A,
            "sensitivity_ranking": sensitivity_ranking,
            "dependency_metadata": dependency_metadata,
            "validation_summary": validation_summary,
            "uncertainty_register": uncertainty_register,
        },
        deep=True,
    )


def build_aggregate_uncertainty(component_scenarios: list[ExposureScenario]):
    dependency_metadata = [
        DependencyDescriptor(
            dependency_id="aggregate-stacking-cluster",
            title="Aggregate totals preserve route-specific dependence rather than joint sampling",
            relationship_type=DependencyRelationship.SCENARIO_PACKAGE,
            assumption_names=["component_scenarios", "route_totals"],
            handling_strategy=DependencyHandlingStrategy.NOT_QUANTIFIED,
            note=(
                "The aggregate output is a deterministic stacking summary and does not encode "
                "behavioral co-use correlations."
            ),
        )
    ]
    validation_summary = ValidationSummary(
        validation_status=ValidationStatus.BENCHMARK_REGRESSION,
        route_mechanism="aggregate_cross_route_screening",
        benchmark_case_ids=["cross_route_aggregate_summary"],
        external_dataset_ids=["aggregate_external_proxy_candidate"],
        evidence_readiness=ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES,
        heuristic_assumption_names=[],
        validation_gap_ids=[],
        highest_supported_uncertainty_tier=UncertaintyTier.TIER_B,
        probabilistic_enablement="blocked",
        notes=[
            "Aggregate outputs are benchmarked as deterministic screening summaries only.",
            "Cross-route co-use dependencies are not modeled probabilistically in v0.1.",
        ],
    )
    uncertainty_register = [
        UncertaintyRegisterEntry(
            entry_id="aggregate-screening-summary",
            title="Aggregate result remains a Tier A additive screening summary",
            uncertainty_types=[
                UncertaintyType.MODEL_UNCERTAINTY,
                UncertaintyType.SCENARIO_UNCERTAINTY,
            ],
            related_assumptions=[],
            quantification_status=UncertaintyQuantificationStatus.QUALITATIVE_ONLY,
            bias_direction=BiasDirection.BIDIRECTIONAL,
            impact_level=(
                "high" if len({item.route for item in component_scenarios}) > 1 else "medium"
            ),
            summary=(
                "The aggregate output preserves route totals but does not model co-use "
                "dependencies or population correlations."
            ),
            recommendation=(
                "Use Tier B scenario packages or a future population engine before interpreting "
                "aggregate totals as realistic population behavior."
            ),
        )
    ]
    return {
        "uncertainty_tier": UncertaintyTier.TIER_A,
        "uncertainty_register": uncertainty_register,
        "dependency_metadata": dependency_metadata,
        "validation_summary": validation_summary,
    }


def build_exposure_envelope(
    params: BuildExposureEnvelopeInput,
    engine,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ExposureEnvelopeSummary:
    ensure(
        len(params.archetypes) >= 2,
        "envelope_requires_multiple_archetypes",
        "Deterministic envelopes require at least two named archetypes.",
        suggestion="Provide at least a lower and upper plausible scenario archetype.",
    )
    scenarios: list[tuple[str, str, ExposureScenario]] = []
    for archetype in params.archetypes:
        request = archetype.request
        ensure(
            request.chemical_id == params.chemical_id,
            "envelope_chemical_mismatch",
            "Every envelope archetype must share the same chemical_id.",
            suggestion="Normalize all archetypes to the same target chemical.",
        )
        if isinstance(request, InhalationTier1ScenarioRequest):
            from exposure_scenario_mcp.plugins.inhalation import (
                build_inhalation_tier_1_screening_scenario,
            )

            scenario = enrich_scenario_uncertainty(
                engine,
                build_inhalation_tier_1_screening_scenario(request, registry),
            )
        else:
            scenario = engine.build(request)
        scenarios.append((archetype.label, archetype.description, scenario))
    routes = {item.route for _, _, item in scenarios}
    classes = {item.scenario_class for _, _, item in scenarios}
    units = {item.external_dose.unit for _, _, item in scenarios}
    ensure(
        len(routes) == 1,
        "envelope_route_mismatch",
        "Every envelope archetype must share the same exposure route.",
        suggestion="Build separate envelopes for different routes.",
    )
    ensure(
        len(classes) == 1,
        "envelope_scenario_class_mismatch",
        "Every envelope archetype must share the same scenario class.",
        suggestion="Build separate envelopes for different scenario classes.",
    )
    ensure(
        len(units) == 1,
        "envelope_unit_mismatch",
        "Every envelope archetype must resolve the same external dose unit.",
        suggestion="Normalize archetype requests so their primary output units match.",
    )
    sorted_scenarios = sorted(scenarios, key=lambda item: item[2].external_dose.value)
    dose_values = [item[2].external_dose.value for item in sorted_scenarios]
    min_item = sorted_scenarios[0]
    max_item = sorted_scenarios[-1]
    min_assumptions = {item.name: item for item in min_item[2].assumptions}
    max_assumptions = {item.name: item for item in max_item[2].assumptions}
    driver_attribution: list[EnvelopeDriverAttribution] = []
    for name in sorted(set(min_assumptions) | set(max_assumptions)):
        left = min_assumptions.get(name)
        right = max_assumptions.get(name)
        if left and right and left.value == right.value and left.unit == right.unit:
            continue
        driver_attribution.append(
            EnvelopeDriverAttribution(
                parameter_name=name,
                unit=left.unit if left else right.unit if right else None,
                min_value=left.value if left else None,
                max_value=right.value if right else None,
                scenario_labels=[min_item[0], max_item[0]],
                attribution_note=(
                    "Driver attribution is based on explicit differences between the minimum "
                    "and maximum deterministic archetypes, not on probabilistic decomposition."
                ),
            )
        )
    dependency_metadata = sorted_scenarios[-1][2].dependency_metadata
    validation_summary = sorted_scenarios[-1][2].validation_summary
    uncertainty_register = [
        UncertaintyRegisterEntry(
            entry_id="envelope-not-probabilistic",
            title="Tier B envelope is bounded but not probabilistic",
            uncertainty_types=[
                UncertaintyType.SCENARIO_UNCERTAINTY,
                UncertaintyType.PARAMETER_UNCERTAINTY,
            ],
            related_assumptions=[item.parameter_name for item in driver_attribution[:5]],
            quantification_status=UncertaintyQuantificationStatus.BOUNDED,
            bias_direction=BiasDirection.BIDIRECTIONAL,
            impact_level="high",
            summary=(
                "Envelope outputs represent named deterministic archetypes and should not be "
                "interpreted as confidence intervals or population probabilities."
            ),
            recommendation=(
                "Keep archetype definitions explicit and add probability bounds or "
                "probabilistic methods only when evidence and dependencies justify them."
            ),
        )
    ]
    tracker = AssumptionTracker(registry=registry)
    tracker.add_derived(
        "archetype_count",
        len(sorted_scenarios),
        None,
        "Tier B envelope count derived from the supplied archetypes.",
    )
    template_ids = {
        (item.label, item.description): item.template_id for item in params.archetypes
    }
    return ExposureEnvelopeSummary(
        envelope_id=f"env-{uuid4().hex[:12]}",
        chemical_id=params.chemical_id,
        route=next(iter(routes)),
        scenario_class=next(iter(classes)),
        label=params.label,
        archetypes=[
            EnvelopeArchetypeResult(
                template_id=template_ids.get((label, description)),
                label=label,
                description=description,
                scenario=scenario,
            )
            for label, description, scenario in sorted_scenarios
        ],
        min_dose=min_item[2].external_dose,
        median_dose=ScenarioDose(
            metric=min_item[2].external_dose.metric,
            value=round(median(dose_values), 8),
            unit=min_item[2].external_dose.unit,
        ),
        max_dose=max_item[2].external_dose,
        span_ratio=(
            None
            if math.isclose(min_item[2].external_dose.value, 0.0)
            else round(
                max_item[2].external_dose.value / min_item[2].external_dose.value,
                8,
            )
        ),
        driver_attribution=driver_attribution[:8],
        uncertainty_register=uncertainty_register,
        dependency_metadata=dependency_metadata,
        validation_summary=validation_summary,
        provenance=tracker.provenance(
            plugin_id="deterministic_envelope_service",
            algorithm_id="uncertainty.envelope.v1",
            generated_at=generated_at,
        ),
        interpretation_notes=[
            "This envelope is a deterministic Tier B scenario set, not a probabilistic interval.",
            "Archetype definitions remain the primary explanation for the resulting span.",
        ],
    )


def _library_backed_envelope(
    envelope: ExposureEnvelopeSummary,
    template_set: ArchetypeLibrarySet,
    library: ArchetypeLibraryRegistry,
) -> ExposureEnvelopeSummary:
    uncertainty_register = list(envelope.uncertainty_register)
    uncertainty_register.append(
        UncertaintyRegisterEntry(
            entry_id="library-governed-archetypes",
            title="Envelope archetypes were instantiated from the packaged library",
            uncertainty_types=[UncertaintyType.SCENARIO_UNCERTAINTY],
            related_assumptions=template_set.driver_parameters,
            quantification_status=UncertaintyQuantificationStatus.BOUNDED,
            bias_direction=BiasDirection.BIDIRECTIONAL,
            impact_level="medium",
            summary=(
                f"Envelope archetypes came from packaged set `{template_set.set_id}` in "
                f"library version `{library.version}`."
            ),
            recommendation=(
                "Treat the packaged library as a governed screening starting point and "
                "replace it with scenario-specific evidence when higher-fidelity context exists."
            ),
        )
    )
    provenance = envelope.provenance.model_copy(
        update={
            "notes": [
                *envelope.provenance.notes,
                f"Archetype library set: {template_set.set_id}",
                f"Archetype library version: {library.version}",
            ]
        },
        deep=True,
    )
    return envelope.model_copy(
        update={
            "archetype_library_set_id": template_set.set_id,
            "archetype_library_version": library.version,
            "uncertainty_register": uncertainty_register,
            "provenance": provenance,
            "interpretation_notes": [
                (
                    f"Envelope instantiated from packaged archetype-library set "
                    f"`{template_set.set_id}`."
                ),
                *template_set.interpretation_notes,
                *envelope.interpretation_notes,
                *[f"Library limitation: {item}" for item in template_set.limitations],
            ],
        },
        deep=True,
    )


def build_exposure_envelope_from_library(
    params: BuildExposureEnvelopeFromLibraryInput,
    engine,
    registry: DefaultsRegistry,
    library: ArchetypeLibraryRegistry,
    *,
    generated_at: str | None = None,
) -> ExposureEnvelopeSummary:
    envelope_input, template_set = build_envelope_input_from_library(params, library)
    envelope = build_exposure_envelope(
        envelope_input,
        engine,
        registry,
        generated_at=generated_at,
    )
    return _library_backed_envelope(envelope, template_set, library)


def build_parameter_bounds_summary(
    params: BuildParameterBoundsInput,
    engine,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ParameterBoundsSummary:
    base_scenario = engine.build(params.base_request)
    min_request, max_request = _bounds_requests(
        params.base_request,
        params.bounded_parameters,
    )
    min_scenario = engine.build(min_request)
    max_scenario = engine.build(max_request)
    monotonicity_checks = _monotonicity_checks(
        params.base_request,
        params.bounded_parameters,
        engine,
    )
    dependency_metadata = base_scenario.dependency_metadata
    validation_summary = base_scenario.validation_summary
    uncertainty_register = [
        UncertaintyRegisterEntry(
            entry_id="bounds-summary-range",
            title="Parameter-bounds summary is a deterministic bounded range",
            uncertainty_types=[
                UncertaintyType.PARAMETER_UNCERTAINTY,
                UncertaintyType.SCENARIO_UNCERTAINTY,
            ],
            related_assumptions=[
                item.parameter_name for item in params.bounded_parameters
            ],
            quantification_status=UncertaintyQuantificationStatus.BOUNDED,
            bias_direction=BiasDirection.BIDIRECTIONAL,
            impact_level="high",
            summary=(
                "The summary propagates explicit lower and upper parameter bounds through the "
                "deterministic engine without assigning probabilities."
            ),
            recommendation=(
                "Do not interpret the resulting range as a confidence interval or population "
                "probability statement."
            ),
        )
    ]
    for bound in params.bounded_parameters:
        uncertainty_register.append(
            UncertaintyRegisterEntry(
                entry_id=f"bound-{bound.parameter_name}",
                title=f"Bounded parameter `{bound.parameter_name}` drives the summary",
                uncertainty_types=[
                    UncertaintyType.PARAMETER_UNCERTAINTY,
                    UncertaintyType.SCENARIO_UNCERTAINTY,
                ],
                related_assumptions=[bound.parameter_name],
                quantification_status=UncertaintyQuantificationStatus.BOUNDED,
                bias_direction=BiasDirection.BIDIRECTIONAL,
                impact_level="medium",
                summary=(
                    f"`{bound.parameter_name}` is bounded between {bound.lower_value:g} and "
                    f"{bound.upper_value:g}."
                ),
                recommendation=bound.rationale,
            )
        )
    if any(item.status != "pass" for item in monotonicity_checks):
        uncertainty_register.append(
            UncertaintyRegisterEntry(
                entry_id="bounds-monotonicity-warning",
                title="At least one monotonicity check failed",
                uncertainty_types=[UncertaintyType.MODEL_UNCERTAINTY],
                related_assumptions=[
                    item.parameter_name
                    for item in monotonicity_checks
                    if item.status != "pass"
                ],
                quantification_status=UncertaintyQuantificationStatus.BOUNDED,
                bias_direction=BiasDirection.UNKNOWN,
                impact_level="high",
                summary=(
                    "One or more bounded parameters did not behave monotonically under the "
                    "current deterministic assumptions."
                ),
                recommendation=(
                    "Review route applicability and use scenario envelopes instead of "
                    "monotonic bounds when the driver is not monotonic."
                ),
            )
        )
    tracker = AssumptionTracker(registry=registry)
    tracker.add_derived(
        "bounded_parameter_count",
        len(params.bounded_parameters),
        None,
        "Tier B bounds summary count derived from explicit bounded drivers.",
    )
    return ParameterBoundsSummary(
        summary_id=f"bnd-{uuid4().hex[:12]}",
        chemical_id=base_scenario.chemical_id,
        route=base_scenario.route,
        scenario_class=base_scenario.scenario_class,
        label=params.label,
        base_scenario=base_scenario,
        min_scenario=min_scenario,
        max_scenario=max_scenario,
        bounded_parameters=params.bounded_parameters,
        monotonicity_checks=monotonicity_checks,
        min_dose=min_scenario.external_dose,
        max_dose=max_scenario.external_dose,
        uncertainty_register=uncertainty_register,
        dependency_metadata=dependency_metadata,
        validation_summary=validation_summary,
        provenance=tracker.provenance(
            plugin_id="parameter_bounds_service",
            algorithm_id="uncertainty.bounds.v1",
            generated_at=generated_at,
        ),
        interpretation_notes=[
            "This output is a bounded deterministic range, not a probabilistic interval.",
            "Bounds are only as defensible as the supplied parameter ranges and route relevance.",
        ],
    )
