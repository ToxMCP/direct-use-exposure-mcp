"""Plugin runtime and scenario orchestration."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import uuid4

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError, ensure
from exposure_scenario_mcp.models import (
    AggregateComponentReference,
    AggregateContributor,
    AggregateExposureSummary,
    AggregationMode,
    AssumptionDelta,
    BuildAggregateExposureScenarioInput,
    CompareExposureScenariosInput,
    DoseUnit,
    ExportPbpkScenarioInputRequest,
    ExposureScenario,
    ExposureScenarioRequest,
    PbpkConcentrationProfilePoint,
    PbpkPopulationContext,
    PbpkScenarioInput,
    PhyschemContext,
    Route,
    RouteDoseTotal,
    ScenarioClass,
    ScenarioComparisonRecord,
    ScenarioDose,
    Severity,
)
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.uncertainty import (
    build_aggregate_uncertainty,
    enrich_scenario_uncertainty,
)
from exposure_scenario_mcp.worker_routing import apply_worker_task_semantics


@dataclass(slots=True)
class ScenarioExecutionContext:
    registry: DefaultsRegistry
    tracker: AssumptionTracker


class ScenarioPlugin(ABC):
    """Base class for deterministic scenario plugins."""

    plugin_id: str
    algorithm_id: str
    scenario_class: ScenarioClass
    supported_routes: tuple[Route, ...]

    @abstractmethod
    def build(
        self, request: ExposureScenarioRequest, context: ScenarioExecutionContext
    ) -> ExposureScenario:
        raise NotImplementedError


class PluginRegistry:
    """Simple registry keyed by scenario class and route."""

    def __init__(self) -> None:
        self._plugins: list[ScenarioPlugin] = []

    def register(self, plugin: ScenarioPlugin) -> None:
        self._plugins.append(plugin)

    def get(self, scenario_class: ScenarioClass, route: Route) -> ScenarioPlugin:
        for plugin in self._plugins:
            if plugin.scenario_class == scenario_class and route in plugin.supported_routes:
                return plugin
        raise LookupError(
            f"No plugin registered for scenario_class={scenario_class.value} route={route.value}"
        )


def grams_to_mg(value_g: float) -> float:
    return value_g * 1000.0


def resolve_product_mass_g(
    profile,
    registry: DefaultsRegistry,
    tracker: AssumptionTracker,
    physchem_context: PhyschemContext | None = None,
) -> float:
    if profile.use_amount_unit.value == "g":
        tracker.add_user(
            "use_amount_per_event",
            profile.use_amount_per_event,
            "g",
            "Product amount per event was supplied directly in grams.",
        )
        tracker.add_derived(
            "product_mass_g_per_event",
            profile.use_amount_per_event,
            "g",
            "Mass-based use amount already represents product mass per event.",
        )
        return profile.use_amount_per_event

    tracker.add_user(
        "use_amount_per_event",
        profile.use_amount_per_event,
        "mL",
        "Product amount per event was supplied in milliliters and converted with density.",
    )
    density_defaulted = profile.density_g_per_ml is None
    if profile.density_g_per_ml is not None:
        tracker.add_user(
            "density_g_per_ml",
            profile.density_g_per_ml,
            "g/mL",
            "Density was supplied explicitly for volume-to-mass conversion.",
        )
        density = profile.density_g_per_ml
    else:
        density, source = registry.default_density_g_per_ml(
            product_category=profile.product_category,
            physical_form=profile.physical_form,
            product_subtype=profile.product_subtype,
        )
        tracker.add_default(
            "density_g_per_ml",
            density,
            "g/mL",
            source,
            (
                "Default density used for volume-to-mass conversion in screening mode, "
                "resolved from product category, physical form, and product subtype when "
                "available."
            ),
        )
    aerosol_volume_factor = 1.0
    if density_defaulted and profile.application_method == "aerosol_spray":
        aerosol_volume_factor, source = registry.pressurized_aerosol_volume_interpretation_factor(
            product_category=profile.product_category,
            physical_form=profile.physical_form,
            product_subtype=profile.product_subtype,
        )
        physchem_adjustment = registry.pressurized_aerosol_physchem_adjustment_factor(
            product_category=profile.product_category,
            product_subtype=profile.product_subtype,
            vapor_pressure_mmhg=(
                None
                if physchem_context is None
                else physchem_context.vapor_pressure_mmhg
            ),
            molecular_weight_g_per_mol=(
                None
                if physchem_context is None
                else physchem_context.molecular_weight_g_per_mol
            ),
        )
        aerosol_physchem_factor = 1.0
        if physchem_adjustment is not None:
            _, aerosol_physchem_factor, physchem_source = physchem_adjustment
            tracker.add_default(
                "pressurized_aerosol_physchem_adjustment_factor",
                aerosol_physchem_factor,
                "fraction",
                physchem_source,
                (
                    "Aerosol volume interpretation was further adjusted with a bounded "
                    "volatility and low-molecular-weight heuristic because pressurized "
                    "aerosol mass semantics were resolved from default density plus "
                    "supplied physchem context."
                ),
            )
            aerosol_volume_factor *= aerosol_physchem_factor
        carrier_adjustment = registry.pressurized_aerosol_carrier_family_adjustment_factor(
            profile.aerosol_carrier_family
        )
        aerosol_carrier_factor = 1.0
        if carrier_adjustment is not None:
            _, aerosol_carrier_factor, carrier_source = carrier_adjustment
            tracker.add_default(
                "pressurized_aerosol_carrier_family_adjustment_factor",
                aerosol_carrier_factor,
                "fraction",
                carrier_source,
                (
                    "Aerosol volume interpretation was further adjusted with a bounded "
                    "carrier-family heuristic because explicit aerosol carrier family "
                    "context was supplied."
                ),
            )
            aerosol_volume_factor *= aerosol_carrier_factor
        formulation_adjustment = (
            registry.pressurized_aerosol_formulation_profile_adjustment_factor(
                product_category=profile.product_category,
                product_subtype=profile.product_subtype,
                aerosol_formulation_profile=profile.aerosol_formulation_profile,
            )
        )
        aerosol_formulation_factor = 1.0
        if formulation_adjustment is not None:
            _, aerosol_formulation_factor, formulation_source = formulation_adjustment
            tracker.add_default(
                "pressurized_aerosol_formulation_profile_adjustment_factor",
                aerosol_formulation_factor,
                "fraction",
                formulation_source,
                (
                    "Aerosol volume interpretation was further adjusted with a bounded "
                    "formulation-profile heuristic because explicit formulation context "
                    "was supplied."
                ),
            )
            aerosol_volume_factor *= aerosol_formulation_factor
        tracker.add_default(
            "pressurized_aerosol_volume_interpretation_factor",
            aerosol_volume_factor,
            "fraction",
            source,
            (
                "Volumetric aerosol-spray amount was bounded with a pressurized-aerosol "
                "interpretation factor because density was defaulted rather than supplied "
                "from product-specific mass semantics."
            ),
        )
        if aerosol_physchem_factor < 1.0:
            tracker.add_quality_flag(
                "pressurized_aerosol_physchem_adjustment_defaulted",
                (
                    "Volumetric aerosol-spray mass was further reduced with a bounded "
                    "aerosol volatility and light-carrier adjustment because default "
                    "density and pressurized product semantics were used together."
                ),
                severity=Severity.WARNING,
            )
        if aerosol_carrier_factor < 1.0:
            tracker.add_quality_flag(
                "pressurized_aerosol_carrier_family_adjustment_defaulted",
                (
                    "Volumetric aerosol-spray mass was further reduced with a bounded "
                    "aerosol carrier-family adjustment because explicit carrier composition "
                    "context was supplied."
                ),
                severity=Severity.WARNING,
            )
        if aerosol_formulation_factor < 1.0:
            tracker.add_quality_flag(
                "pressurized_aerosol_formulation_profile_adjustment_defaulted",
                (
                    "Volumetric aerosol-spray mass was further reduced with a bounded "
                    "aerosol formulation-profile adjustment because explicit formulation "
                    "context was supplied."
                ),
                severity=Severity.WARNING,
            )
        if aerosol_volume_factor < 1.0:
            tracker.add_quality_flag(
                "pressurized_aerosol_volume_interpretation_defaulted",
                (
                    "Volumetric aerosol-spray mass was reduced with a bounded "
                    "pressurized-aerosol interpretation factor because default density was "
                    "used for a pressurized product."
                ),
                severity=Severity.WARNING,
            )
    product_mass_g = profile.use_amount_per_event * density * aerosol_volume_factor
    tracker.add_derived(
        "product_mass_g_per_event",
        product_mass_g,
        "g",
        (
            "Converted volume-based use amount into mass using density and, when needed, "
            "a bounded pressurized-aerosol interpretation factor."
        ),
    )
    return product_mass_g


def resolve_population_value(
    field_name: str,
    supplied_value: float | None,
    population_group: str,
    registry: DefaultsRegistry,
    tracker: AssumptionTracker,
    unit: str,
    rationale: str,
    *,
    gt: float | None = None,
    region: str = "global",
) -> float:
    if supplied_value is not None:
        resolved = supplied_value
    else:
        defaults, source = registry.population_defaults(population_group, region=region)
        resolved = float(defaults[field_name])
        rationale = f"Resolved from population defaults for '{population_group}'."
        if region != "global":
            tracker.add_quality_flag(
                code="regional_population_override_active",
                severity=Severity.INFO,
                message=(
                    f"Population default '{field_name}' uses region='{region}' override "
                    f"({resolved} {unit}). Global default would differ."
                ),
            )
    if gt is not None and resolved <= gt:
        source_detail = "user-supplied" if supplied_value is not None else "population-default"
        raise ExposureScenarioError(
            code="population_value_not_positive",
            message=(
                f"{field_name} must be greater than {gt} {unit} "
                f"but received {resolved} ({source_detail})."
            ),
            suggestion=(
                "Provide a positive value for this field or select a population group "
                "with a positive default."
            ),
            details={
                "field_name": field_name,
                "resolved": resolved,
                "unit": unit,
                "source": source_detail,
            },
        )
    if supplied_value is not None:
        tracker.add_user(field_name, resolved, unit, rationale)
    else:
        tracker.add_default(field_name, resolved, unit, source, rationale)
    return resolved


def aggregate_scenarios(
    params: BuildAggregateExposureScenarioInput,
    registry: DefaultsRegistry,
) -> AggregateExposureSummary:
    ensure(
        all(s.chemical_id == params.chemical_id for s in params.component_scenarios),
        "aggregate_chemical_mismatch",
        "All component scenarios must share the same chemical_id.",
        suggestion="Filter component scenarios so they represent the same target chemical.",
    )
    component_ids = [item.scenario_id for item in params.component_scenarios]
    ensure(
        len(component_ids) == len(set(component_ids)),
        "aggregate_duplicate_component",
        "Aggregate requests cannot contain duplicate component scenario IDs.",
        suggestion="Deduplicate component scenarios before building an aggregate summary.",
        component_ids=component_ids,
    )
    units = {item.external_dose.unit for item in params.component_scenarios}
    ensure(
        units == {DoseUnit.MG_PER_KG_DAY},
        "aggregate_unit_unsupported",
        "Simple additive aggregation currently supports only normalized mg/kg-day component doses.",
        suggestion=(
            "Aggregate only normalized screening scenarios or extend the aggregation method."
        ),
        units=sorted(unit.value for unit in units),
    )

    tracker = AssumptionTracker(registry=registry)
    tracker.add_derived(
        "component_count",
        len(params.component_scenarios),
        None,
        "Aggregate scenario count derived from the supplied component list.",
    )
    tracker.add_user(
        "aggregation_mode",
        params.aggregation_mode.value,
        "mode",
        "Aggregation mode was supplied explicitly or defaulted by schema.",
    )

    component_refs = [
        AggregateComponentReference(
            scenario_id=item.scenario_id, route=item.route, dose=item.external_dose
        )
        for item in params.component_scenarios
    ]

    per_route_map: dict[Route, float] = {}
    for item in params.component_scenarios:
        per_route_map[item.route] = per_route_map.get(item.route, 0.0) + item.external_dose.value

    per_route_totals = [
        RouteDoseTotal(
            route=route,
            total_dose=ScenarioDose(
                metric="route_total_external_dose",
                value=round(value, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            ),
        )
        for route, value in sorted(per_route_map.items(), key=lambda item: item[0].value)
    ]

    total_value = sum(item.external_dose.value for item in params.component_scenarios)
    route_bioavailability_map = {
        item.route: item.bioavailability_fraction
        for item in params.route_bioavailability_adjustments
    }
    internal_equivalent_total_dose = None
    per_route_internal_equivalent_totals: list[RouteDoseTotal] = []
    contributor_values: dict[str, float] = {
        item.scenario_id: item.external_dose.value for item in params.component_scenarios
    }

    if params.aggregation_mode == AggregationMode.INTERNAL_EQUIVALENT:
        missing_routes = sorted(
            route.value for route in per_route_map if route not in route_bioavailability_map
        )
        ensure(
            not missing_routes,
            "aggregate_internal_equivalent_bioavailability_missing",
            (
                "Internal-equivalent aggregation requires route bioavailability fractions "
                "for every route represented in the component scenarios."
            ),
            suggestion=(
                "Provide routeBioavailabilityAdjustments for each represented route or "
                "use aggregationMode='external_summary'."
            ),
            missing_routes=missing_routes,
        )
        for adjustment in params.route_bioavailability_adjustments:
            tracker.add_user(
                f"bioavailability_fraction_{adjustment.route.value}",
                adjustment.bioavailability_fraction,
                "fraction",
                (
                    "Route-specific bioavailability fraction supplied for "
                    "internal-equivalent aggregation."
                ),
            )
        per_route_internal_map = {
            route: value * route_bioavailability_map[route]
            for route, value in per_route_map.items()
        }
        per_route_internal_equivalent_totals = [
            RouteDoseTotal(
                route=route,
                total_dose=ScenarioDose(
                    metric="route_internal_equivalent_dose",
                    value=round(value, 8),
                    unit=DoseUnit.MG_PER_KG_DAY,
                ),
            )
            for route, value in sorted(
                per_route_internal_map.items(), key=lambda item: item[0].value
            )
        ]
        internal_total_value = sum(per_route_internal_map.values())
        internal_equivalent_total_dose = ScenarioDose(
            metric="aggregate_internal_equivalent_dose",
            value=round(internal_total_value, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        )
        contributor_values = {
            item.scenario_id: item.external_dose.value * route_bioavailability_map[item.route]
            for item in params.component_scenarios
        }
        tracker.add_quality_flag(
            "aggregate_internal_equivalent_screening",
            (
                "Internal-equivalent aggregation applies caller-supplied route bioavailability "
                "fractions to external doses. It remains a screening transformation, not a PBPK "
                "substitute."
            ),
        )
        tracker.add_limitation(
            "internal_equivalent_bioavailability_user_supplied",
            (
                "Internal-equivalent totals depend on the supplied route bioavailability "
                "fractions and do not replace route-specific kinetic modeling."
            ),
        )
    else:
        if params.route_bioavailability_adjustments:
            tracker.add_quality_flag(
                "aggregate_route_bioavailability_ignored",
                (
                    "routeBioavailabilityAdjustments were supplied, but aggregationMode "
                    "remained `external_summary`, so external-dose totals were returned unchanged."
                ),
            )
    if len(per_route_map) > 1:
        tracker.add_limitation(
            "cross_route_aggregate",
            (
                "Aggregate total spans multiple exposure routes and should "
                "be interpreted as a screening summary rather than a "
                "PBPK-ready collapse."
            ),
        )

    dominant_contributors = []
    dominant_total = sum(contributor_values.values())
    if dominant_total and dominant_total > 0:
        ranked = sorted(
            params.component_scenarios,
            key=lambda item: contributor_values[item.scenario_id],
            reverse=True,
        )
        dominant_contributors = [
            AggregateContributor(
                scenario_id=item.scenario_id,
                contribution_fraction=round(
                    contributor_values[item.scenario_id] / dominant_total, 6
                ),
                dose_value=round(contributor_values[item.scenario_id], 8),
            )
            for item in ranked[:3]
        ]

    diagnostics = build_aggregate_uncertainty(params.component_scenarios)

    return AggregateExposureSummary(
        scenario_id=f"agg-{uuid4().hex[:12]}",
        chemical_id=params.chemical_id,
        component_scenarios=component_refs,
        aggregation_mode=params.aggregation_mode,
        aggregation_method=(
            "simple_additive_screening"
            if params.aggregation_mode == AggregationMode.EXTERNAL_SUMMARY
            else "route_bioavailability_adjusted_internal_equivalent_screening"
        ),
        normalized_total_external_dose=(
            ScenarioDose(
                metric="aggregate_external_dose",
                value=round(total_value, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            )
        ),
        internal_equivalent_total_dose=internal_equivalent_total_dose,
        per_route_totals=per_route_totals,
        per_route_internal_equivalent_totals=per_route_internal_equivalent_totals,
        route_bioavailability_adjustments=params.route_bioavailability_adjustments,
        dominant_contributors=dominant_contributors,
        limitations=tracker.limitations,
        quality_flags=tracker.quality_flags,
        uncertainty_tier=diagnostics["uncertainty_tier"],
        uncertainty_register=diagnostics["uncertainty_register"],
        dependency_metadata=diagnostics["dependency_metadata"],
        validation_summary=diagnostics["validation_summary"],
        provenance=tracker.provenance(
            plugin_id="aggregate_summary_service",
            algorithm_id="aggregate.simple_additive.v1",
        ),
    )


def _pbpk_transient_concentration_profile(
    scenario: ExposureScenario,
    tracker: AssumptionTracker,
) -> list[PbpkConcentrationProfilePoint]:
    if scenario.route != Route.INHALATION:
        tracker.add_limitation(
            "pbpk_transient_profile_non_inhalation_unsupported",
            (
                "Transient concentration profiles are only exported for inhalation scenarios. "
                "Other routes continue to export scalar PBPK handoff inputs only."
            ),
        )
        return []

    duration = scenario.product_use_profile.exposure_duration_hours
    if duration is None:
        tracker.add_limitation(
            "pbpk_transient_profile_duration_missing",
            (
                "Transient inhalation export requires an explicit event duration on the "
                "source scenario."
            ),
        )
        return []

    metrics = scenario.route_metrics
    if (
        "air_concentration_at_reentry_start_mg_per_m3" in metrics
        and "air_concentration_at_reentry_end_mg_per_m3" in metrics
    ):
        average = float(
            metrics.get(
                "average_air_concentration_mg_per_m3",
                metrics["air_concentration_at_reentry_start_mg_per_m3"],
            )
        )
        return [
            PbpkConcentrationProfilePoint(
                timeHours=0.0,
                concentrationMgPerM3=float(
                    metrics["air_concentration_at_reentry_start_mg_per_m3"]
                ),
            ),
            PbpkConcentrationProfilePoint(
                timeHours=round(duration / 2.0, 8),
                concentrationMgPerM3=round(average, 8),
            ),
            PbpkConcentrationProfilePoint(
                timeHours=round(duration, 8),
                concentrationMgPerM3=float(metrics["air_concentration_at_reentry_end_mg_per_m3"]),
            ),
        ]

    if (
        "initial_air_concentration_mg_per_m3" in metrics
        and "air_concentration_at_event_end_mg_per_m3" in metrics
    ):
        average = float(
            metrics.get(
                "average_air_concentration_mg_per_m3",
                metrics["initial_air_concentration_mg_per_m3"],
            )
        )
        return [
            PbpkConcentrationProfilePoint(
                timeHours=0.0,
                concentrationMgPerM3=float(metrics["initial_air_concentration_mg_per_m3"]),
            ),
            PbpkConcentrationProfilePoint(
                timeHours=round(duration / 2.0, 8),
                concentrationMgPerM3=round(average, 8),
            ),
            PbpkConcentrationProfilePoint(
                timeHours=round(duration, 8),
                concentrationMgPerM3=float(metrics["air_concentration_at_event_end_mg_per_m3"]),
            ),
        ]

    tracker.add_limitation(
        "pbpk_transient_profile_route_metrics_missing",
        (
            "Transient inhalation export requires route metrics that expose start and end air "
            "concentrations. The source scenario did not provide that pair."
        ),
    )
    return []


def export_pbpk_input(
    params: ExportPbpkScenarioInputRequest,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> PbpkScenarioInput:
    scenario = params.scenario
    tracker = AssumptionTracker(registry=registry)
    tracker.add_derived(
        "supporting_assumption_count",
        len(scenario.assumptions),
        None,
        "PBPK export captures the names of assumptions supporting the source scenario.",
    )

    duration = scenario.product_use_profile.exposure_duration_hours
    if duration is None and scenario.route == Route.INHALATION:
        tracker.add_limitation(
            "pbpk_event_duration_missing",
            (
                "Inhalation PBPK export has no explicit event duration "
                "because the source scenario did not include one."
            ),
        )

    transient_profile: list[PbpkConcentrationProfilePoint] = []
    if params.include_transient_concentration_profile:
        transient_profile = _pbpk_transient_concentration_profile(scenario, tracker)
        tracker.add_derived(
            "pbpk_transient_profile_point_count",
            len(transient_profile),
            None,
            "Transient concentration-profile point count derived for additive PBPK export.",
        )

    return PbpkScenarioInput(
        source_scenario_id=scenario.scenario_id,
        chemical_id=scenario.chemical_id,
        chemical_name=scenario.chemical_name,
        route=scenario.route,
        dose_magnitude=round(scenario.external_dose.value, 8),
        dose_unit=scenario.external_dose.unit,
        dose_metric=scenario.external_dose.metric,
        events_per_day=scenario.product_use_profile.use_events_per_day,
        event_duration_hours=duration,
        timing_pattern=params.regimen_name
        or f"{scenario.product_use_profile.use_events_per_day:g} events/day",
        population_context=PbpkPopulationContext(
            population_group=scenario.population_profile.population_group,
            body_weight_kg=scenario.population_profile.body_weight_kg
            if scenario.population_profile.body_weight_kg is not None
            else next(item.value for item in scenario.assumptions if item.name == "body_weight_kg"),
            inhalation_rate_m3_per_hour=scenario.population_profile.inhalation_rate_m3_per_hour,
            region=scenario.population_profile.region,
        ),
        transient_concentration_profile=transient_profile,
        supporting_assumption_names=[item.name for item in scenario.assumptions],
        provenance=tracker.provenance(
            plugin_id="pbpk_export_service",
            algorithm_id="pbpk.export.v1",
            generated_at=generated_at,
        ),
        limitations=tracker.limitations,
    )


def compare_scenarios(
    params: CompareExposureScenariosInput,
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ScenarioComparisonRecord:
    baseline = params.baseline
    comparison = params.comparison
    ensure(
        baseline.chemical_id == comparison.chemical_id,
        "comparison_chemical_mismatch",
        "Scenarios must share the same chemical_id to be compared.",
        suggestion="Compare scenarios built for the same chemical and route family.",
    )

    tracker = AssumptionTracker(registry=registry)
    base = baseline.external_dose.value
    comp = comparison.external_dose.value
    absolute_delta = round(comp - base, 8)
    percent_delta = None if math.isclose(base, 0.0) else round(((comp - base) / base) * 100.0, 4)

    base_assumptions = {item.name: item for item in baseline.assumptions}
    comp_assumptions = {item.name: item for item in comparison.assumptions}
    changed_assumptions = []
    for name in sorted(set(base_assumptions) | set(comp_assumptions)):
        left = base_assumptions.get(name)
        right = comp_assumptions.get(name)
        if left and right and left.value == right.value and left.unit == right.unit:
            continue
        changed_assumptions.append(
            AssumptionDelta(
                name=name,
                baseline_value=left.value if left else None,
                comparison_value=right.value if right else None,
                unit=left.unit if left else right.unit if right else None,
            )
        )

    notes = []
    if percent_delta is None:
        notes.append("Baseline dose was zero; percentage delta is undefined.")
    elif percent_delta > 0:
        notes.append(f"Comparison dose increased by {percent_delta:.2f}% relative to baseline.")
    elif percent_delta < 0:
        notes.append(
            f"Comparison dose decreased by {abs(percent_delta):.2f}% relative to baseline."
        )
    else:
        notes.append("Comparison dose is numerically identical to the baseline.")

    if baseline.route != comparison.route:
        notes.append(
            "Routes differ between scenarios; interpret the comparison as "
            "an audit trace, not a like-for-like route refinement."
        )

    tracker.add_derived(
        "changed_assumption_count",
        len(changed_assumptions),
        None,
        "Comparison engine counted assumptions with changed values or presence.",
    )

    return ScenarioComparisonRecord(
        baseline_scenario_id=baseline.scenario_id,
        comparison_scenario_id=comparison.scenario_id,
        chemical_id=baseline.chemical_id,
        baseline_dose=baseline.external_dose,
        comparison_dose=comparison.external_dose,
        absolute_delta=absolute_delta,
        percent_delta=percent_delta,
        changed_assumptions=changed_assumptions,
        interpretation_notes=notes,
        provenance=tracker.provenance(
            plugin_id="scenario_comparison_service",
            algorithm_id="scenario.compare.v1",
            generated_at=generated_at,
        ),
    )


class ScenarioEngine:
    """Thin orchestrator for route-specific plugins."""

    def __init__(self, registry: PluginRegistry, defaults_registry: DefaultsRegistry) -> None:
        self.registry = registry
        self.defaults_registry = defaults_registry

    def build(
        self,
        request: ExposureScenarioRequest,
        *,
        include_diagnostics: bool = True,
    ) -> ExposureScenario:
        try:
            plugin = self.registry.get(request.scenario_class, request.route)
        except LookupError as error:
            raise ExposureScenarioError(
                code="plugin_not_available",
                message=(
                    "No scenario plugin is available for "
                    f"scenario_class='{request.scenario_class.value}' "
                    f"and route='{request.route.value}'."
                ),
                suggestion=(
                    "Use the inhalation-specific tool for inhalation "
                    "scenarios or choose a supported screening route."
                ),
            ) from error
        tracker = AssumptionTracker(registry=self.defaults_registry)
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
        context = ScenarioExecutionContext(registry=self.defaults_registry, tracker=tracker)
        scenario = plugin.build(request, context)
        scenario = apply_worker_task_semantics(
            scenario,
            request,
            registry=self.defaults_registry,
        )
        if not include_diagnostics:
            return scenario
        return enrich_scenario_uncertainty(self, scenario)
