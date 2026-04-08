"""Deterministic worker-task routing and scenario post-processing helpers."""

from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    ExposureScenario,
    FitForPurpose,
    LimitationNote,
    PopulationProfile,
    QualityFlag,
    Route,
    Severity,
    TierLevel,
    WorkerSupportStatus,
    WorkerTaskRoutingDecision,
    WorkerTaskRoutingInput,
)

WORKER_GUIDANCE_RESOURCE = "docs://worker-routing-guide"
SPRAY_APPLICATION_METHODS = {"trigger_spray", "pump_spray", "aerosol_spray"}
WORKER_TAG_TOKENS = {
    "worker",
    "occupational",
    "occupational_user",
    "occupational_worker",
    "professional",
    "industrial",
    "workplace",
}


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def detect_worker_context(population_profile: PopulationProfile) -> tuple[bool, list[str]]:
    basis: list[str] = []
    normalized_group = _normalize_token(population_profile.population_group)
    if any(token in normalized_group for token in ("worker", "occupational", "professional")):
        basis.append(f"population_group:{population_profile.population_group}")

    for tag in population_profile.demographic_tags:
        if _normalize_token(tag) in WORKER_TAG_TOKENS:
            basis.append(f"demographic_tag:{tag}")

    unique_basis = sorted(set(basis))
    return (bool(unique_basis), unique_basis)


def _supports_transfer(registry: DefaultsRegistry, params: WorkerTaskRoutingInput) -> bool:
    try:
        registry.transfer_efficiency(
            params.product_use_profile.application_method,
            params.product_use_profile.product_category,
        )
        return True
    except ExposureScenarioError:
        return False


def _supports_ingestion(registry: DefaultsRegistry, params: WorkerTaskRoutingInput) -> bool:
    try:
        registry.ingestion_fraction(params.product_use_profile.application_method)
        return True
    except ExposureScenarioError:
        return False


def _supports_inhalation(registry: DefaultsRegistry, params: WorkerTaskRoutingInput) -> bool:
    try:
        registry.aerosolized_fraction(
            params.product_use_profile.application_method,
            params.product_use_profile.product_category,
            params.product_use_profile.product_subtype,
        )
        return True
    except ExposureScenarioError:
        return False


def _worker_fit_for_purpose(base: FitForPurpose) -> FitForPurpose:
    suitable_for = list(base.suitable_for)
    for item in ("worker task triage", "occupational scenario scoping"):
        if item not in suitable_for:
            suitable_for.append(item)

    not_suitable_for = list(base.not_suitable_for)
    for item in (
        "occupational compliance determination",
        "measured workplace exposure verification",
    ):
        if item not in not_suitable_for:
            not_suitable_for.append(item)

    return base.model_copy(
        update={
            "suitable_for": suitable_for,
            "not_suitable_for": not_suitable_for,
        }
    )


def route_worker_task(
    params: WorkerTaskRoutingInput,
    registry: DefaultsRegistry | None = None,
) -> WorkerTaskRoutingDecision:
    registry = registry or DefaultsRegistry.load()
    worker_detected, detection_basis = detect_worker_context(params.population_profile)
    warnings: list[str] = []
    limitations: list[str] = []
    app = params.product_use_profile.application_method.lower()
    form = params.product_use_profile.physical_form.lower()

    if not worker_detected:
        warnings.append(
            "Worker context was not explicitly detected from population_profile; routing falls "
            "back to task mechanics. Add demographic_tags like `worker` or `occupational` when "
            "this is truly a workplace task."
        )

    if params.route == Route.INHALATION:
        if params.requested_tier in {TierLevel.TIER_2, TierLevel.TIER_3}:
            return WorkerTaskRoutingDecision(
                route=params.route,
                scenario_class=params.scenario_class,
                worker_detected=worker_detected,
                detection_basis=detection_basis,
                support_status=WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED,
                recommended_model_family="art_adapter_candidate",
                recommended_tool=None,
                target_mcp="future_worker_exposure_adapter",
                guidance_resource=WORKER_GUIDANCE_RESOURCE,
                required_inputs=[
                    "task_description",
                    "ventilation_context",
                    "local_controls",
                    "task_duration_hours",
                    "emission_characterization",
                ],
                warnings=warnings,
                limitations=[
                    "The current Exposure Scenario MCP does not implement Tier 2 occupational "
                    "inhalation models such as ART or Stoffenmanager."
                ],
                rationale=(
                    "A higher worker inhalation tier was requested, so routing escalates to a "
                    "future occupational adapter rather than reusing deterministic screening."
                ),
                next_step=(
                    "Collect task-control and ventilation inputs for an ART- or "
                    "Stoffenmanager-aligned adapter."
                ),
            )

        if form == "spray" and app in SPRAY_APPLICATION_METHODS:
            limitations.append(
                "The current Tier 1 inhalation path remains a deterministic NF/FF screening "
                "model and does not substitute for ART, measured workplace monitoring, or a "
                "validated occupational aerosol simulator."
            )
            if worker_detected:
                warnings.append(
                    "Worker-tagged spray tasks are currently routed to the shared Tier 1 "
                    "inhalation screening tool because it is the strongest bounded path "
                    "implemented in this MCP."
                )
            if params.prefer_current_mcp:
                return WorkerTaskRoutingDecision(
                    route=params.route,
                    scenario_class=params.scenario_class,
                    worker_detected=worker_detected,
                    detection_basis=detection_basis,
                    support_status=(
                        WorkerSupportStatus.SUPPORTED_WITH_CAVEATS
                        if worker_detected
                        else WorkerSupportStatus.SUPPORTED_IN_CURRENT_MCP
                    ),
                    recommended_model_family="inhalation_near_field_far_field_screening",
                    recommended_tool="exposure_build_inhalation_tier1_screening_scenario",
                    target_mcp="exposure_scenario_mcp",
                    guidance_resource=WORKER_GUIDANCE_RESOURCE,
                    required_inputs=[
                        "source_distance_m",
                        "spray_duration_seconds",
                        "near_field_volume_m3",
                        "airflow_directionality",
                        "particle_size_regime",
                    ],
                    warnings=warnings,
                    limitations=limitations,
                    rationale=(
                        "Spray tasks can already be represented by the current Tier 1 NF/FF "
                        "screening contract, which is the strongest worker-relevant inhalation "
                        "path implemented in this MCP."
                    ),
                    next_step=(
                        "Call exposure_build_inhalation_tier1_screening_scenario and preserve "
                        "tier_semantics, quality_flags, limitations, and any profile-alignment "
                        "signals."
                    ),
                )
            return WorkerTaskRoutingDecision(
                route=params.route,
                scenario_class=params.scenario_class,
                worker_detected=worker_detected,
                detection_basis=detection_basis,
                support_status=WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED,
                recommended_model_family="art_adapter_candidate",
                recommended_tool=None,
                target_mcp="future_worker_exposure_adapter",
                guidance_resource=WORKER_GUIDANCE_RESOURCE,
                required_inputs=[
                    "task_description",
                    "ventilation_context",
                    "local_controls",
                    "task_duration_hours",
                    "emission_characterization",
                ],
                warnings=warnings,
                limitations=limitations,
                rationale=(
                    "The caller explicitly prefers a dedicated occupational path over the "
                    "currently implemented screening NF/FF route."
                ),
                next_step="Route the task to a future ART-aligned worker inhalation adapter.",
            )

        if _supports_inhalation(registry, params) and params.prefer_current_mcp:
            limitations.append(
                "The current inhalation room-average path is only appropriate when the worker "
                "task still behaves like a bounded direct-use microenvironment rather than a "
                "process emission or full workplace-source model."
            )
            return WorkerTaskRoutingDecision(
                route=params.route,
                scenario_class=params.scenario_class,
                worker_detected=worker_detected,
                detection_basis=detection_basis,
                support_status=(
                    WorkerSupportStatus.SUPPORTED_WITH_CAVEATS
                    if worker_detected
                    else WorkerSupportStatus.SUPPORTED_IN_CURRENT_MCP
                ),
                recommended_model_family="inhalation_room_well_mixed_screening",
                recommended_tool="exposure_build_inhalation_screening_scenario",
                target_mcp="exposure_scenario_mcp",
                guidance_resource=WORKER_GUIDANCE_RESOURCE,
                required_inputs=[
                    "room_volume_m3",
                    "air_exchange_rate_per_hour",
                    "exposure_duration_hours",
                ],
                warnings=warnings,
                limitations=limitations,
                rationale=(
                    "The application method is supported by the current inhalation screening "
                    "engine, so the task can be triaged inside this MCP if a bounded "
                    "room-average abstraction is still acceptable."
                ),
                next_step=(
                    "Call exposure_build_inhalation_screening_scenario and treat the output as "
                    "worker triage rather than a workplace compliance estimate."
                ),
            )

        return WorkerTaskRoutingDecision(
            route=params.route,
            scenario_class=params.scenario_class,
            worker_detected=worker_detected,
            detection_basis=detection_basis,
            support_status=WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED,
            recommended_model_family="art_adapter_candidate",
            recommended_tool=None,
            target_mcp="future_worker_exposure_adapter",
            guidance_resource=WORKER_GUIDANCE_RESOURCE,
            required_inputs=[
                "task_description",
                "ventilation_context",
                "local_controls",
                "task_duration_hours",
                "emission_characterization",
            ],
            warnings=warnings,
            limitations=[
                "The requested inhalation task is not represented by an application method "
                "implemented in the current inhalation defaults packs."
            ],
            rationale=(
                "This inhalation task looks more like a workplace source-emission problem than "
                "a direct-use room or NF/FF screening case."
            ),
            next_step="Escalate to a future occupational inhalation adapter path.",
        )

    if params.route == Route.DERMAL:
        if _supports_transfer(registry, params) and params.prefer_current_mcp:
            limitations.append(
                "The current dermal path estimates external skin loading only and does not "
                "represent absorbed dermal dose, glove breakthrough, or measured workplace "
                "surface transfer."
            )
            return WorkerTaskRoutingDecision(
                route=params.route,
                scenario_class=params.scenario_class,
                worker_detected=worker_detected,
                detection_basis=detection_basis,
                support_status=(
                    WorkerSupportStatus.SUPPORTED_WITH_CAVEATS
                    if worker_detected
                    else WorkerSupportStatus.SUPPORTED_IN_CURRENT_MCP
                ),
                recommended_model_family="screening.external_dose.v1",
                recommended_tool="exposure_build_screening_exposure_scenario",
                target_mcp="exposure_scenario_mcp",
                guidance_resource=WORKER_GUIDANCE_RESOURCE,
                required_inputs=[
                    "use_amount_per_event",
                    "use_events_per_day",
                    "retention_factor",
                    "transfer_efficiency",
                ],
                warnings=warnings,
                limitations=limitations,
                rationale=(
                    "The worker task can still be represented by the current external dermal "
                    "screening equations as a transparent triage path."
                ),
                next_step=(
                    "Call exposure_build_screening_exposure_scenario and keep the result bounded "
                    "to external dermal loading."
                ),
            )

        return WorkerTaskRoutingDecision(
            route=params.route,
            scenario_class=params.scenario_class,
            worker_detected=worker_detected,
            detection_basis=detection_basis,
            support_status=WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED,
            recommended_model_family="dermal_absorption_ppe_adapter_candidate",
            recommended_tool="exposure_export_worker_dermal_absorbed_dose_bridge",
            target_mcp="exposure_scenario_mcp",
            guidance_resource=WORKER_GUIDANCE_RESOURCE,
            required_inputs=[
                "task_description",
                "contact_duration_hours",
                "surface_loading_context",
                "ppe_state",
                "control_measures",
            ],
            warnings=warnings,
            limitations=[
                "The current dermal engine only covers direct-use external loading and does not "
                "ship a dedicated occupational dermal adapter."
            ],
            rationale=(
                "This dermal worker task needs a dedicated occupational path or absorbed-dose "
                "refinement rather than the shared direct-use screening equations."
            ),
            next_step=(
                "Export a worker dermal absorbed-dose bridge and keep the result bounded as a "
                "handoff artifact for a future occupational dermal workflow."
            ),
        )

    if _supports_ingestion(registry, params) and params.prefer_current_mcp:
        limitations.append(
            "The current oral path estimates external intake mass only and does not represent "
            "worker hygiene behavior, task-specific incidental ingestion, or internal dose."
        )
        return WorkerTaskRoutingDecision(
            route=params.route,
            scenario_class=params.scenario_class,
            worker_detected=worker_detected,
            detection_basis=detection_basis,
            support_status=(
                WorkerSupportStatus.SUPPORTED_WITH_CAVEATS
                if worker_detected
                else WorkerSupportStatus.SUPPORTED_IN_CURRENT_MCP
            ),
            recommended_model_family="screening.external_dose.v1",
            recommended_tool="exposure_build_screening_exposure_scenario",
            target_mcp="exposure_scenario_mcp",
            guidance_resource=WORKER_GUIDANCE_RESOURCE,
            required_inputs=["ingestion_fraction", "use_amount_per_event", "use_events_per_day"],
            warnings=warnings,
            limitations=limitations,
            rationale=(
                "The current oral screening engine can still provide a bounded external intake "
                "triage estimate when the worker ingestion pathway is simple and explicit."
            ),
            next_step=(
                "Call exposure_build_screening_exposure_scenario and interpret the result as "
                "external oral intake only."
            ),
        )

    return WorkerTaskRoutingDecision(
        route=params.route,
        scenario_class=params.scenario_class,
        worker_detected=worker_detected,
        detection_basis=detection_basis,
        support_status=(
            WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED
            if worker_detected
            else WorkerSupportStatus.OUT_OF_SCOPE
        ),
        recommended_model_family="occupational_incidental_ingestion_adapter_candidate",
        recommended_tool=None,
        target_mcp="future_worker_exposure_adapter",
        guidance_resource=WORKER_GUIDANCE_RESOURCE,
        required_inputs=[
            "task_description",
            "hand_to_mouth_frequency",
            "surface_loading_context",
            "hygiene_controls",
        ],
        warnings=warnings,
        limitations=[
            "The current oral engine only supports direct_oral or incidental_oral screening "
            "semantics with explicit ingestion fractions."
        ],
        rationale=(
            "The requested oral worker task is outside the narrow ingestion patterns supported "
            "by the current direct-use screening engine."
        ),
        next_step="Escalate to a future worker incidental-ingestion adapter path.",
    )


def apply_worker_task_semantics(
    scenario: ExposureScenario,
    request,
    registry: DefaultsRegistry | None = None,
) -> ExposureScenario:
    routing = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id=getattr(request, "chemical_id", None),
            route=request.route,
            scenario_class=request.scenario_class,
            product_use_profile=request.product_use_profile,
            population_profile=request.population_profile,
            requested_tier=getattr(request, "requested_tier", None),
        ),
        registry=registry,
    )
    if not routing.worker_detected:
        return scenario

    quality_flags = list(scenario.quality_flags)
    quality_flags.append(
        QualityFlag(
            code="worker_task_context",
            severity=Severity.INFO,
            message=(
                "Population profile indicates worker or occupational context; the scenario "
                "should be interpreted as worker-task triage, not as a consumer-use result."
            ),
        )
    )
    quality_flags.append(
        QualityFlag(
            code="worker_shared_screening_engine",
            severity=Severity.WARNING,
            message=(
                "Worker-tagged scenario uses the current shared screening engine rather than a "
                "dedicated occupational adapter. Inspect worker routing guidance before using "
                "the output downstream."
            ),
        )
    )

    limitations = list(scenario.limitations)
    limitations.append(
        LimitationNote(
            code="worker_model_boundary",
            severity=Severity.WARNING,
            message=(
                "This worker-tagged scenario reuses direct-use screening semantics and does "
                "not represent ECETOC TRA, ART, Stoffenmanager, measured workplace "
                "monitoring, or a regulatory occupational compliance determination."
            ),
        )
    )

    route_metrics = dict(scenario.route_metrics)
    route_metrics["worker_context_detected"] = True
    route_metrics["worker_support_status"] = routing.support_status.value
    route_metrics["worker_recommended_tool"] = routing.recommended_tool
    route_metrics["worker_guidance_resource"] = routing.guidance_resource
    route_metrics["worker_detection_basis"] = "; ".join(routing.detection_basis)

    interpretation_notes = list(scenario.interpretation_notes)
    interpretation_notes.append(
        "Worker context was detected from the population profile; keep the output bounded to "
        "worker-task screening and review docs://worker-routing-guide for escalation paths."
    )

    return scenario.model_copy(
        update={
            "route_metrics": route_metrics,
            "quality_flags": quality_flags,
            "limitations": limitations,
            "fit_for_purpose": _worker_fit_for_purpose(scenario.fit_for_purpose),
            "interpretation_notes": interpretation_notes,
        },
        deep=True,
    )
