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
    AssumptionDelta,
    BuildAggregateExposureScenarioInput,
    CompareExposureScenariosInput,
    DoseUnit,
    ExportPbpkScenarioInputRequest,
    ExposureScenario,
    ExposureScenarioRequest,
    PbpkPopulationContext,
    PbpkScenarioInput,
    Route,
    RouteDoseTotal,
    ScenarioClass,
    ScenarioComparisonRecord,
    ScenarioDose,
)
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.uncertainty import (
    build_aggregate_uncertainty,
    enrich_scenario_uncertainty,
)


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
        )
        tracker.add_default(
            "density_g_per_ml",
            density,
            "g/mL",
            source,
            (
                "Default density used for volume-to-mass conversion in screening mode, "
                "resolved from product category and physical form when available."
            ),
        )
    product_mass_g = profile.use_amount_per_event * density
    tracker.add_derived(
        "product_mass_g_per_event",
        product_mass_g,
        "g",
        "Converted volume-based use amount into mass using density.",
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
) -> float:
    if supplied_value is not None:
        tracker.add_user(field_name, supplied_value, unit, rationale)
        return supplied_value
    defaults, source = registry.population_defaults(population_group)
    resolved = float(defaults[field_name])
    tracker.add_default(
        field_name,
        resolved,
        unit,
        source,
        f"Resolved from population defaults for '{population_group}'.",
    )
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
    if total_value and total_value > 0:
        ranked = sorted(
            params.component_scenarios, key=lambda item: item.external_dose.value, reverse=True
        )
        dominant_contributors = [
            AggregateContributor(
                scenario_id=item.scenario_id,
                contribution_fraction=round(item.external_dose.value / total_value, 6),
                dose_value=round(item.external_dose.value, 8),
            )
            for item in ranked[:3]
        ]

    diagnostics = build_aggregate_uncertainty(params.component_scenarios)

    return AggregateExposureSummary(
        scenario_id=f"agg-{uuid4().hex[:12]}",
        chemical_id=params.chemical_id,
        component_scenarios=component_refs,
        aggregation_method="simple_additive_screening",
        normalized_total_external_dose=(
            ScenarioDose(
                metric="aggregate_external_dose",
                value=round(total_value, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            )
        ),
        per_route_totals=per_route_totals,
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
            physical_form=request.product_use_profile.physical_form,
            application_method=request.product_use_profile.application_method,
            retention_type=request.product_use_profile.retention_type,
            population_group=request.population_profile.population_group,
            region=request.population_profile.region,
        )
        context = ScenarioExecutionContext(registry=self.defaults_registry, tracker=tracker)
        scenario = plugin.build(request, context)
        if not include_diagnostics:
            return scenario
        return enrich_scenario_uncertainty(self, scenario)
