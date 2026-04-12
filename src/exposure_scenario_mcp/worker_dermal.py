"""Worker dermal bridge and adapter models for absorbed-dose and PPE workflows."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ApplicabilityStatus,
    AssumptionGovernance,
    AssumptionSourceReference,
    DefaultVisibility,
    DoseUnit,
    EvidenceBasis,
    EvidenceGrade,
    ExecutedValidationCheck,
    ExposureAssumptionRecord,
    ExposureScenarioRequest,
    FitForPurpose,
    LimitationNote,
    PhyschemContext,
    PopulationProfile,
    ProductAmountUnit,
    ProductUseProfile,
    ProvenanceBundle,
    QualityFlag,
    Route,
    ScalarValue,
    ScenarioClass,
    ScenarioDose,
    Severity,
    SourceKind,
    StrictModel,
    TierLevel,
    TierSemantics,
    UncertaintyTier,
    UncertaintyType,
    ValidationCheckStatus,
    ValidationEvidenceReadiness,
    ValidationStatus,
    ValidationSummary,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.worker_routing import route_worker_task

WORKER_DERMAL_BRIDGE_GUIDANCE_RESOURCE = "docs://worker-dermal-bridge-guide"
WORKER_DERMAL_ADAPTER_GUIDANCE_RESOURCE = "docs://worker-dermal-adapter-guide"
WORKER_DERMAL_EXECUTION_GUIDANCE_RESOURCE = "docs://worker-dermal-execution-guide"
WORKER_DERMAL_TEMPLATE_CATALOG_VERSION = "2026.04.07.v1"
WORKER_DERMAL_BENCHMARK_CASE_ID = "worker_dermal_wet_wipe_gloved_hands_execution"
WORKER_DERMAL_BIOCIDAL_BENCHMARK_CASE_ID = (
    "worker_dermal_handheld_biocidal_trigger_spray_execution"
)
WORKER_DERMAL_SURFACE_CAP_BENCHMARK_CASE_ID = (
    "worker_dermal_extreme_loading_surface_cap_execution"
)
WORKER_DERMAL_BIOCIDAL_EXTERNAL_CHECK_ID = (
    "worker_biocidal_handheld_trigger_spray_dermal_mass_2023"
)
WORKER_BENCHMARK_REL_TOLERANCE = 0.05


class WorkerDermalModelFamily(StrEnum):
    DERMAL_ABSORPTION_PPE = "dermal_absorption_ppe"
    IH_SKINPERM = "ih_skinperm"


class WorkerDermalTemplateAlignmentStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIAL = "partial"
    HEURISTIC = "heuristic"
    NONE = "none"


class WorkerDermalContactPattern(StrEnum):
    UNKNOWN = "unknown"
    DIRECT_HANDLING = "direct_handling"
    SURFACE_TRANSFER = "surface_transfer"
    SPLASH_CONTACT = "splash_contact"
    IMMERSION_CONTACT = "immersion_contact"
    RESIDUE_CONTACT = "residue_contact"


class WorkerDermalPpeState(StrEnum):
    UNKNOWN = "unknown"
    NONE = "none"
    WORK_GLOVES = "work_gloves"
    CHEMICAL_RESISTANT_GLOVES = "chemical_resistant_gloves"
    PROTECTIVE_CLOTHING = "protective_clothing"
    GLOVES_AND_PROTECTIVE_CLOTHING = "gloves_and_protective_clothing"


class WorkerSkinCondition(StrEnum):
    UNKNOWN = "unknown"
    INTACT = "intact"
    WET = "wet"
    COMPROMISED = "compromised"
    OCCLUDED = "occluded"


class WorkerDermalBarrierMaterial(StrEnum):
    UNKNOWN = "unknown"
    GENERIC_WORK_GLOVE = "generic_work_glove"
    NITRILE = "nitrile"
    LATEX = "latex"
    NEOPRENE = "neoprene"
    BUTYL = "butyl"
    PVC = "pvc"
    LAMINATE = "laminate"
    TEXTILE = "textile"
    COATED_TEXTILE = "coated_textile"


class WorkerDermalChemicalContext(PhyschemContext):
    schema_version: Literal["workerDermalChemicalContext.v1"] = (
        "workerDermalChemicalContext.v1"
    )


class WorkerDermalTaskContext(StrictModel):
    schema_version: Literal["workerDermalTaskContext.v1"] = "workerDermalTaskContext.v1"
    task_description: str = Field(..., alias="taskDescription")
    workplace_setting: str | None = Field(default=None, alias="workplaceSetting")
    contact_duration_hours: float | None = Field(
        default=None,
        alias="contactDurationHours",
        gt=0.0,
    )
    contact_pattern: WorkerDermalContactPattern = Field(
        default=WorkerDermalContactPattern.UNKNOWN,
        alias="contactPattern",
    )
    exposed_body_areas: list[str] = Field(default_factory=list, alias="exposedBodyAreas")
    ppe_state: WorkerDermalPpeState = Field(
        default=WorkerDermalPpeState.UNKNOWN,
        alias="ppeState",
    )
    barrier_material: WorkerDermalBarrierMaterial = Field(
        default=WorkerDermalBarrierMaterial.UNKNOWN,
        alias="barrierMaterial",
    )
    control_measures: list[str] = Field(default_factory=list, alias="controlMeasures")
    surface_loading_context: str | None = Field(
        default=None,
        alias="surfaceLoadingContext",
    )
    skin_condition: WorkerSkinCondition = Field(
        default=WorkerSkinCondition.UNKNOWN,
        alias="skinCondition",
    )
    notes: list[str] = Field(default_factory=list)


class ExportWorkerDermalAbsorbedDoseBridgeRequest(StrictModel):
    schema_version: Literal["exportWorkerDermalAbsorbedDoseBridgeRequest.v1"] = (
        "exportWorkerDermalAbsorbedDoseBridgeRequest.v1"
    )
    base_request: ExposureScenarioRequest = Field(..., alias="baseRequest")
    target_model_family: WorkerDermalModelFamily = Field(
        default=WorkerDermalModelFamily.DERMAL_ABSORPTION_PPE,
        alias="targetModelFamily",
    )
    task_description: str = Field(
        default="worker dermal task requiring absorbed-dose or PPE refinement",
        alias="taskDescription",
    )
    workplace_setting: str | None = Field(default=None, alias="workplaceSetting")
    contact_duration_hours: float | None = Field(
        default=None,
        alias="contactDurationHours",
        gt=0.0,
    )
    contact_pattern: WorkerDermalContactPattern = Field(
        default=WorkerDermalContactPattern.UNKNOWN,
        alias="contactPattern",
    )
    exposed_body_areas: list[str] = Field(default_factory=list, alias="exposedBodyAreas")
    ppe_state: WorkerDermalPpeState = Field(
        default=WorkerDermalPpeState.UNKNOWN,
        alias="ppeState",
    )
    barrier_material: WorkerDermalBarrierMaterial = Field(
        default=WorkerDermalBarrierMaterial.UNKNOWN,
        alias="barrierMaterial",
    )
    control_measures: list[str] = Field(default_factory=list, alias="controlMeasures")
    surface_loading_context: str | None = Field(
        default=None,
        alias="surfaceLoadingContext",
    )
    skin_condition: WorkerSkinCondition = Field(
        default=WorkerSkinCondition.UNKNOWN,
        alias="skinCondition",
    )
    chemical_context: WorkerDermalChemicalContext | None = Field(
        default=None,
        alias="chemicalContext",
    )
    context_of_use: str = Field(
        default="worker-dermal-bridge",
        alias="contextOfUse",
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dermal_scope(self) -> ExportWorkerDermalAbsorbedDoseBridgeRequest:
        if self.base_request.route != Route.DERMAL:
            raise ValueError("Worker dermal bridge export requires route='dermal'.")
        return self


class WorkerDermalCompatibilityReport(StrictModel):
    schema_version: Literal["workerDermalCompatibilityReport.v1"] = (
        "workerDermalCompatibilityReport.v1"
    )
    source_request_schema: str = Field(..., alias="sourceRequestSchema")
    target_model_family: WorkerDermalModelFamily = Field(
        ...,
        alias="targetModelFamily",
    )
    route: Route = Field(default=Route.DERMAL)
    worker_detected: bool = Field(..., alias="workerDetected")
    ready_for_adapter: bool = Field(..., alias="readyForAdapter")
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    issues: list[LimitationNote] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        alias="recommendedNextSteps",
    )


class WorkerDermalAbsorbedDoseAdapterRequest(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseAdapterRequest.v1"] = (
        "workerDermalAbsorbedDoseAdapterRequest.v1"
    )
    target_adapter: str = Field(
        default="future_worker_dermal_adapter",
        alias="targetAdapter",
    )
    target_model_family: WorkerDermalModelFamily = Field(
        ...,
        alias="targetModelFamily",
    )
    source_module: str = Field(default="exposure-scenario-mcp", alias="sourceModule")
    context_of_use: str = Field(..., alias="contextOfUse")
    chemical_identity: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="chemicalIdentity",
    )
    chemical_context: WorkerDermalChemicalContext | None = Field(
        default=None,
        alias="chemicalContext",
    )
    task_context: WorkerDermalTaskContext = Field(..., alias="taskContext")
    exposure_inputs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="exposureInputs",
    )
    supporting_handoffs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="supportingHandoffs",
    )
    guidance_resource: str = Field(
        default=WORKER_DERMAL_BRIDGE_GUIDANCE_RESOURCE,
        alias="guidanceResource",
    )


class WorkerDermalAbsorbedDoseAdapterToolCall(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseAdapterToolCall.v1"] = (
        "workerDermalAbsorbedDoseAdapterToolCall.v1"
    )
    tool_name: str = Field(
        default="worker_ingest_dermal_absorbed_dose_task",
        alias="toolName",
    )
    arguments: WorkerDermalAbsorbedDoseAdapterRequest


class WorkerDermalAbsorbedDoseBridgePackage(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseBridgePackage.v1"] = (
        "workerDermalAbsorbedDoseBridgePackage.v1"
    )
    routing_decision: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="routingDecision",
    )
    adapter_request: WorkerDermalAbsorbedDoseAdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    tool_call: WorkerDermalAbsorbedDoseAdapterToolCall = Field(
        ...,
        alias="toolCall",
    )
    compatibility_report: WorkerDermalCompatibilityReport = Field(
        ...,
        alias="compatibilityReport",
    )
    quality_flags: list[QualityFlag] = Field(default_factory=list, alias="qualityFlags")
    provenance: ProvenanceBundle


class WorkerDermalDeterminantTemplateMatch(StrictModel):
    schema_version: Literal["workerDermalDeterminantTemplateMatch.v1"] = (
        "workerDermalDeterminantTemplateMatch.v1"
    )
    template_id: str | None = Field(default=None, alias="templateId")
    template_label: str | None = Field(default=None, alias="templateLabel")
    alignment_status: WorkerDermalTemplateAlignmentStatus = Field(
        default=WorkerDermalTemplateAlignmentStatus.NONE,
        alias="alignmentStatus",
    )
    match_score: float = Field(default=0.0, alias="matchScore")
    match_basis: list[str] = Field(default_factory=list, alias="matchBasis")
    determinant_recommendations: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="determinantRecommendations",
    )
    source_basis: list[str] = Field(default_factory=list, alias="sourceBasis")
    review_notes: list[str] = Field(default_factory=list, alias="reviewNotes")


class WorkerDermalAbsorbedDoseTaskEnvelope(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseTaskEnvelope.v1"] = (
        "workerDermalAbsorbedDoseTaskEnvelope.v1"
    )
    adapter_name: str = Field(default="worker_dermal_absorption_ppe_adapter", alias="adapterName")
    adapter_version: str = Field(default="0.1.0", alias="adapterVersion")
    contact_profile: str = Field(..., alias="contactProfile")
    ppe_profile: str = Field(..., alias="ppeProfile")
    body_zone_profile: str = Field(..., alias="bodyZoneProfile")
    determinant_template_match: WorkerDermalDeterminantTemplateMatch = Field(
        ...,
        alias="determinantTemplateMatch",
    )
    chemical_context: WorkerDermalChemicalContext | None = Field(
        default=None,
        alias="chemicalContext",
    )
    task_summary: list[str] = Field(default_factory=list, alias="taskSummary")
    dermal_inputs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="dermalInputs",
    )
    screening_handoff_summary: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="screeningHandoffSummary",
    )


class WorkerDermalAbsorbedDoseAdapterIngestResult(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseAdapterIngestResult.v1"] = (
        "workerDermalAbsorbedDoseAdapterIngestResult.v1"
    )
    supported_by_adapter: bool = Field(..., alias="supportedByAdapter")
    ready_for_adapter_execution: bool = Field(..., alias="readyForAdapterExecution")
    manual_review_required: bool = Field(..., alias="manualReviewRequired")
    resolved_adapter: str | None = Field(default=None, alias="resolvedAdapter")
    target_model_family: WorkerDermalModelFamily = Field(..., alias="targetModelFamily")
    dermal_task_envelope: WorkerDermalAbsorbedDoseTaskEnvelope | None = Field(
        default=None,
        alias="dermalTaskEnvelope",
    )
    quality_flags: list[QualityFlag] = Field(default_factory=list, alias="qualityFlags")
    limitations: list[LimitationNote] = Field(default_factory=list)
    provenance: ProvenanceBundle


class WorkerDermalAbsorbedDoseExecutionOverrides(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseExecutionOverrides.v1"] = (
        "workerDermalAbsorbedDoseExecutionOverrides.v1"
    )
    external_skin_mass_mg_per_day: float | None = Field(
        default=None,
        alias="externalSkinMassMgPerDay",
        ge=0.0,
    )
    body_zone_surface_area_cm2: float | None = Field(
        default=None,
        alias="bodyZoneSurfaceAreaCm2",
        gt=0.0,
    )
    ppe_penetration_factor: float | None = Field(
        default=None,
        alias="ppePenetrationFactor",
        ge=0.0,
        le=1.0,
    )
    dermal_absorption_fraction: float | None = Field(
        default=None,
        alias="dermalAbsorptionFraction",
        ge=0.0,
        le=1.0,
    )
    contact_duration_factor: float | None = Field(
        default=None,
        alias="contactDurationFactor",
        ge=0.0,
        le=1.0,
    )


class ExecuteWorkerDermalAbsorbedDoseRequest(StrictModel):
    schema_version: Literal["executeWorkerDermalAbsorbedDoseRequest.v1"] = (
        "executeWorkerDermalAbsorbedDoseRequest.v1"
    )
    adapter_request: WorkerDermalAbsorbedDoseAdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    execution_overrides: WorkerDermalAbsorbedDoseExecutionOverrides | None = Field(
        default=None,
        alias="executionOverrides",
    )
    context_of_use: str = Field(default="worker-dermal-execution", alias="contextOfUse")


class WorkerDermalAbsorbedDoseExecutionResult(StrictModel):
    schema_version: Literal["workerDermalAbsorbedDoseExecutionResult.v1"] = (
        "workerDermalAbsorbedDoseExecutionResult.v1"
    )
    supported_by_adapter: bool = Field(..., alias="supportedByAdapter")
    ready_for_execution: bool = Field(..., alias="readyForExecution")
    manual_review_required: bool = Field(..., alias="manualReviewRequired")
    resolved_adapter: str | None = Field(default=None, alias="resolvedAdapter")
    target_model_family: WorkerDermalModelFamily = Field(..., alias="targetModelFamily")
    chemical_id: str = Field(..., alias="chemicalId")
    chemical_name: str | None = Field(default=None, alias="chemicalName")
    route: Route = Field(default=Route.DERMAL)
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.REFINED,
        alias="scenarioClass",
    )
    external_dose: ScenarioDose | None = Field(default=None, alias="externalDose")
    absorbed_dose: ScenarioDose | None = Field(default=None, alias="absorbedDose")
    product_use_profile: ProductUseProfile | None = Field(
        default=None,
        alias="productUseProfile",
    )
    population_profile: PopulationProfile | None = Field(
        default=None,
        alias="populationProfile",
    )
    task_context: WorkerDermalTaskContext = Field(..., alias="taskContext")
    chemical_context: WorkerDermalChemicalContext | None = Field(
        default=None,
        alias="chemicalContext",
    )
    dermal_task_envelope: WorkerDermalAbsorbedDoseTaskEnvelope | None = Field(
        default=None,
        alias="dermalTaskEnvelope",
    )
    execution_overrides: WorkerDermalAbsorbedDoseExecutionOverrides | None = Field(
        default=None,
        alias="executionOverrides",
    )
    route_metrics: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="routeMetrics",
    )
    assumptions: list[ExposureAssumptionRecord] = Field(default_factory=list)
    quality_flags: list[QualityFlag] = Field(default_factory=list, alias="qualityFlags")
    limitations: list[LimitationNote] = Field(default_factory=list)
    provenance: ProvenanceBundle
    fit_for_purpose: FitForPurpose = Field(..., alias="fitForPurpose")
    tier_semantics: TierSemantics = Field(..., alias="tierSemantics")
    validation_summary: ValidationSummary | None = Field(
        default=None,
        alias="validationSummary",
    )
    interpretation_notes: list[str] = Field(default_factory=list, alias="interpretationNotes")


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _normalized_scalar_text(value: ScalarValue | object) -> str:
    return _normalized_text(value if isinstance(value, str) else None)


def _body_area_context(values: list[str]) -> str:
    return " ".join(_normalized_text(item) for item in values if item)


def _contact_profile(task_context: WorkerDermalTaskContext) -> str:
    mapping = {
        WorkerDermalContactPattern.DIRECT_HANDLING: "direct_handling_contact_profile",
        WorkerDermalContactPattern.SURFACE_TRANSFER: "surface_transfer_contact_profile",
        WorkerDermalContactPattern.SPLASH_CONTACT: "liquid_splash_contact_profile",
        WorkerDermalContactPattern.IMMERSION_CONTACT: "immersion_contact_profile",
        WorkerDermalContactPattern.RESIDUE_CONTACT: "residual_surface_contact_profile",
    }
    return mapping.get(task_context.contact_pattern, "contact_pattern_not_declared")


def _ppe_profile(task_context: WorkerDermalTaskContext) -> str:
    if task_context.ppe_state == WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES:
        return "chemical_resistant_glove_barrier_profile"
    if task_context.ppe_state == WorkerDermalPpeState.WORK_GLOVES:
        return "general_work_glove_barrier_profile"
    if task_context.ppe_state == WorkerDermalPpeState.PROTECTIVE_CLOTHING:
        return "protective_clothing_barrier_profile"
    if task_context.ppe_state == WorkerDermalPpeState.GLOVES_AND_PROTECTIVE_CLOTHING:
        return "combined_glove_and_clothing_barrier_profile"
    if task_context.ppe_state == WorkerDermalPpeState.NONE:
        return "unprotected_skin_profile"
    return "ppe_not_declared_profile"


def _body_zone_profile(task_context: WorkerDermalTaskContext) -> str:
    areas = {_normalized_text(item) for item in task_context.exposed_body_areas}
    if {"hand", "hands"} & areas and not areas - {"hand", "hands"}:
        return "hands_only_body_zone"
    if {"hand", "hands"} & areas and {"forearm", "forearms", "arm", "arms"} & areas:
        return "hands_and_forearms_body_zone"
    if {"face", "neck"} & areas:
        return "head_and_neck_body_zone"
    if areas:
        return "multi_zone_body_contact_profile"
    return "body_zone_not_declared"


def _float_or_none(value: ScalarValue | object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _has_worker_dermal_chemical_context(
    chemical_context: WorkerDermalChemicalContext | None,
) -> bool:
    return chemical_context is not None and any(
        value is not None
        for value in (
            chemical_context.log_kow,
            chemical_context.molecular_weight_g_per_mol,
            chemical_context.water_solubility_mg_per_l,
            chemical_context.vapor_pressure_mmhg,
        )
    )


def _coerce_worker_dermal_chemical_context(
    value: WorkerDermalChemicalContext | PhyschemContext | None,
) -> WorkerDermalChemicalContext | None:
    if value is None:
        return None
    if isinstance(value, WorkerDermalChemicalContext):
        return value
    return WorkerDermalChemicalContext(
        logKow=value.log_kow,
        molecularWeightGPerMol=value.molecular_weight_g_per_mol,
        waterSolubilityMgPerL=value.water_solubility_mg_per_l,
        vaporPressureMmhg=value.vapor_pressure_mmhg,
    )


def _product_amount_unit(value: ScalarValue | object) -> ProductAmountUnit | None:
    if isinstance(value, ProductAmountUnit):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        for unit in ProductAmountUnit:
            if normalized == unit.value:
                return unit
    return None


def _execution_algorithm_source() -> AssumptionSourceReference:
    return AssumptionSourceReference(
        source_id="worker_dermal_absorbed_dose_execution_v1",
        title="Direct-Use Exposure MCP worker dermal absorbed-dose execution algorithm",
        locator=WORKER_DERMAL_EXECUTION_GUIDANCE_RESOURCE,
        version="2026.04.07.v1",
    )


def _bounded_transition_fraction(
    *,
    duration_hours: float,
    lag_hours: float,
    transition_hours: float,
) -> float:
    if duration_hours <= lag_hours:
        return 0.0
    if transition_hours <= 0.0:
        return 1.0
    if duration_hours >= lag_hours + transition_hours:
        return 1.0
    return min(max((duration_hours - lag_hours) / transition_hours, 0.0), 1.0)


def _worker_benchmark_case(case_id: str) -> dict | None:
    fixture = load_benchmark_manifest()
    for case in fixture.get("cases", []):
        if case.get("id") == case_id:
            return case
    return None


def _benchmark_bounds(expected: float) -> tuple[float, float]:
    delta = abs(expected) * WORKER_BENCHMARK_REL_TOLERANCE
    if delta == 0.0:
        delta = 1e-8
    return expected - delta, expected + delta


def _benchmark_status(observed: float, lower: float, upper: float) -> ValidationCheckStatus:
    if lower <= observed <= upper:
        return ValidationCheckStatus.PASS
    return ValidationCheckStatus.WARNING


def _matches_worker_dermal_benchmark(
    result: WorkerDermalAbsorbedDoseExecutionResult,
) -> bool:
    profile = result.product_use_profile
    overrides = result.execution_overrides
    envelope = result.dermal_task_envelope
    if profile is None or overrides is None or envelope is None:
        return False
    return (
        envelope.determinant_template_match.template_id == "janitorial_wet_wipe_gloved_hands_v1"
        and profile.product_category == "household_cleaner"
        and profile.application_method == "wipe"
        and math.isclose(float(overrides.ppe_penetration_factor or 0.0), 0.3, rel_tol=1e-9)
    )


def _matches_worker_dermal_handheld_biocidal_benchmark(
    result: WorkerDermalAbsorbedDoseExecutionResult,
) -> bool:
    profile = result.product_use_profile
    envelope = result.dermal_task_envelope
    task_context = result.task_context
    if profile is None or envelope is None or task_context is None:
        return False
    return (
        envelope.determinant_template_match.template_id == "generic_gloved_hand_contact_v1"
        and profile.product_category == "disinfectant"
        and profile.physical_form == "spray"
        and profile.application_method == "trigger_spray"
        and math.isclose(float(profile.concentration_fraction), 0.0016, rel_tol=1e-9)
        and math.isclose(float(profile.use_amount_per_event), 40.0, rel_tol=1e-9)
        and math.isclose(float(profile.use_events_per_day), 1.0, rel_tol=1e-9)
        and math.isclose(float(profile.exposure_duration_hours or 0.0), 1.0, rel_tol=1e-9)
        and math.isclose(float(task_context.contact_duration_hours or 0.0), 1.0, rel_tol=1e-9)
        and _normalized_text(task_context.workplace_setting) == "workbench_area"
        and task_context.contact_pattern == WorkerDermalContactPattern.SURFACE_TRANSFER
        and task_context.ppe_state == WorkerDermalPpeState.WORK_GLOVES
    )


def _matches_worker_dermal_surface_cap_benchmark(
    result: WorkerDermalAbsorbedDoseExecutionResult,
) -> bool:
    profile = result.product_use_profile
    envelope = result.dermal_task_envelope
    task_context = result.task_context
    if profile is None or envelope is None or task_context is None:
        return False
    return (
        envelope.determinant_template_match.template_id == "generic_ungloved_hand_contact_v1"
        and profile.product_category == "household_cleaner"
        and profile.physical_form == "liquid"
        and profile.application_method == "hand_application"
        and math.isclose(float(profile.concentration_fraction), 0.02, rel_tol=1e-9)
        and math.isclose(float(profile.use_amount_per_event), 500.0, rel_tol=1e-9)
        and math.isclose(float(profile.use_events_per_day), 1.0, rel_tol=1e-9)
        and math.isclose(float(profile.exposure_duration_hours or 0.0), 0.75, rel_tol=1e-9)
        and math.isclose(float(task_context.contact_duration_hours or 0.0), 1.0, rel_tol=1e-9)
        and _normalized_text(task_context.workplace_setting) == "mix_room"
        and task_context.contact_pattern == WorkerDermalContactPattern.DIRECT_HANDLING
        and task_context.ppe_state == WorkerDermalPpeState.NONE
    )


def _append_worker_dermal_benchmark_checks(
    result: WorkerDermalAbsorbedDoseExecutionResult,
    *,
    case_id: str,
    executed_validation_checks: list[ExecutedValidationCheck],
) -> None:
    if result.external_dose is None or result.absorbed_dose is None:
        return
    case = _worker_benchmark_case(case_id)
    if case is None:
        return
    expected = case["expected"]
    external_expected = float(expected["external_dose_value"])
    external_lower, external_upper = _benchmark_bounds(external_expected)
    executed_validation_checks.append(
        ExecutedValidationCheck(
            checkId=f"{case_id}_external_dose_benchmark_2026",
            title=f"Worker dermal external dose vs benchmark `{case_id}`",
            referenceDatasetId=case_id,
            status=_benchmark_status(
                result.external_dose.value,
                external_lower,
                external_upper,
            ),
            comparedMetric="normalized_external_skin_dose",
            observedValue=round(result.external_dose.value, 8),
            referenceLower=round(external_lower, 8),
            referenceUpper=round(external_upper, 8),
            unit=result.external_dose.unit.value,
            note=(
                "Compares the current result against the packaged worker dermal benchmark "
                f"`{case_id}` with a +/-5% acceptance band."
            ),
        )
    )

    absorbed_expected = float(expected["absorbed_dose_value"])
    absorbed_lower, absorbed_upper = _benchmark_bounds(absorbed_expected)
    executed_validation_checks.append(
        ExecutedValidationCheck(
            checkId=f"{case_id}_absorbed_dose_benchmark_2026",
            title=f"Worker dermal absorbed dose vs benchmark `{case_id}`",
            referenceDatasetId=case_id,
            status=_benchmark_status(
                result.absorbed_dose.value,
                absorbed_lower,
                absorbed_upper,
            ),
            comparedMetric="normalized_absorbed_dose",
            observedValue=round(result.absorbed_dose.value, 8),
            referenceLower=round(absorbed_lower, 8),
            referenceUpper=round(absorbed_upper, 8),
            unit=result.absorbed_dose.unit.value,
            note=(
                "Checks the PPE-aware absorbed-dose output against the packaged worker "
                f"dermal benchmark `{case_id}`."
            ),
        )
    )

    external_skin_mass = result.route_metrics.get("externalSkinMassMgPerDay")
    if isinstance(external_skin_mass, int | float):
        expected_mass = float(expected["route_metrics"]["externalSkinMassMgPerDay"])
        mass_lower, mass_upper = _benchmark_bounds(expected_mass)
        executed_validation_checks.append(
            ExecutedValidationCheck(
                checkId=f"{case_id}_external_skin_mass_benchmark_2026",
                title=f"Worker dermal external skin mass vs benchmark `{case_id}`",
                referenceDatasetId=case_id,
                status=_benchmark_status(
                    float(external_skin_mass),
                    mass_lower,
                    mass_upper,
                ),
                comparedMetric="external_skin_mass_mg_per_day",
                observedValue=round(float(external_skin_mass), 8),
                referenceLower=round(mass_lower, 8),
                referenceUpper=round(mass_upper, 8),
                unit="mg/day",
                note=(
                    "Checks the skin-boundary worker dermal mass against the packaged worker "
                    f"dermal benchmark `{case_id}`."
                ),
            )
        )


def _build_worker_dermal_validation_summary(
    result: WorkerDermalAbsorbedDoseExecutionResult,
) -> ValidationSummary:
    profile = result.product_use_profile
    heuristic_assumption_names = sorted(
        item.name
        for item in result.assumptions
        if (
            "heuristic" in item.source.source_id
            or item.source.source_id.startswith("benchmark_")
        )
    )
    benchmark_case_ids: list[str] = []
    executed_validation_checks: list[ExecutedValidationCheck] = []
    external_dataset_ids: list[str] = []
    evidence_readiness = ValidationEvidenceReadiness.BENCHMARK_ONLY

    if (
        profile is not None
        and profile.product_category == "household_cleaner"
        and profile.application_method == "wipe"
    ):
        external_dataset_ids.append("rivm_wet_cloth_dermal_contact_loading_2018")
        evidence_readiness = ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES
    if (
        profile is not None
        and profile.product_category in {"disinfectant", "pest_control"}
        and profile.application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}
    ):
        external_dataset_ids.append("worker_biocidal_spray_foam_dermal_2023")
        evidence_readiness = ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES

    if _matches_worker_dermal_benchmark(result):
        benchmark_case_ids.append(WORKER_DERMAL_BENCHMARK_CASE_ID)
        _append_worker_dermal_benchmark_checks(
            result,
            case_id=WORKER_DERMAL_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )

    if _matches_worker_dermal_handheld_biocidal_benchmark(result):
        benchmark_case_ids.append(WORKER_DERMAL_BIOCIDAL_BENCHMARK_CASE_ID)
        _append_worker_dermal_benchmark_checks(
            result,
            case_id=WORKER_DERMAL_BIOCIDAL_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )
        external_skin_mass = result.route_metrics.get("externalSkinMassMgPerDay")
        if isinstance(external_skin_mass, int | float):
            reference_band = ValidationReferenceBandRegistry.load().band_for_check(
                WORKER_DERMAL_BIOCIDAL_EXTERNAL_CHECK_ID
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(external_skin_mass)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            executed_validation_checks.append(
                ExecutedValidationCheck(
                    checkId=WORKER_DERMAL_BIOCIDAL_EXTERNAL_CHECK_ID,
                    title=(
                        "Small-scale handheld biocidal spray dermal loading vs occupational "
                        "monitoring study"
                    ),
                    referenceDatasetId="worker_biocidal_spray_foam_dermal_2023",
                    status=status,
                    comparedMetric="external_skin_mass_mg_per_day",
                    observedValue=round(float(external_skin_mass), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed externalSkinMassMgPerDay is compared against the reported "
                        "approximately 12.8-13.6 mg/day handheld BAC spray contamination band "
                        "for small-scale surface disinfection tasks in the 2023 occupational "
                        "biocidal spray study."
                    ),
                )
            )
            evidence_readiness = ValidationEvidenceReadiness.EXTERNAL_PARTIAL

    if _matches_worker_dermal_surface_cap_benchmark(result):
        benchmark_case_ids.append(WORKER_DERMAL_SURFACE_CAP_BENCHMARK_CASE_ID)
        _append_worker_dermal_benchmark_checks(
            result,
            case_id=WORKER_DERMAL_SURFACE_CAP_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )

    if not benchmark_case_ids:
        benchmark_case_ids = [WORKER_DERMAL_BENCHMARK_CASE_ID]

    validation_status = (
        ValidationStatus.BENCHMARK_REGRESSION
        if benchmark_case_ids
        else ValidationStatus.VERIFICATION_ONLY
    )
    return ValidationSummary(
        validationStatus=validation_status,
        routeMechanism="worker_dermal_absorbed_dose_screening",
        benchmarkCaseIds=benchmark_case_ids,
        externalDatasetIds=external_dataset_ids,
        evidenceReadiness=evidence_readiness,
        heuristicAssumptionNames=heuristic_assumption_names,
        validationGapIds=[
            "worker_dermal_external_validation_partial_only",
            "worker_dermal_execution_not_chemical_specific",
        ],
        executedValidationChecks=executed_validation_checks,
        highestSupportedUncertaintyTier=UncertaintyTier.TIER_B,
        probabilisticEnablement="blocked",
        notes=[
            "Worker dermal validation is currently benchmark-regressed against packaged "
            "PPE-aware screening cases, not a chemical-specific permeability model.",
            (
                "Source-backed external loading anchors are attached for household-cleaner "
                "wipe tasks and for worker biocidal spray/foam dermal tasks when the product "
                "family matches."
            ),
            (
                "Executable checks run only when the task matches a governed wet-wipe or "
                "study-like handheld biocidal spray benchmark pattern."
            ),
        ],
    )


def _assumption_governance(
    *,
    source_kind: SourceKind,
    source: AssumptionSourceReference,
    applicability_domain: dict[str, ScalarValue] | None = None,
) -> AssumptionGovernance:
    if source_kind == SourceKind.USER_INPUT:
        return AssumptionGovernance(
            evidence_grade=EvidenceGrade.GRADE_4,
            evidence_basis=EvidenceBasis.EXPLICIT_INPUT,
            default_visibility=DefaultVisibility.SILENT_TRACEABLE,
            applicability_status=ApplicabilityStatus.USER_ASSERTED,
            uncertainty_types=[UncertaintyType.SCENARIO_UNCERTAINTY],
            applicability_domain=applicability_domain or {},
        )
    if source_kind == SourceKind.DERIVED:
        return AssumptionGovernance(
            evidence_grade=None,
            evidence_basis=EvidenceBasis.DERIVED,
            default_visibility=DefaultVisibility.SILENT_TRACEABLE,
            applicability_status=ApplicabilityStatus.DERIVED,
            uncertainty_types=[
                UncertaintyType.MODEL_UNCERTAINTY,
                UncertaintyType.PARAMETER_UNCERTAINTY,
            ],
            applicability_domain=applicability_domain or {},
        )

    heuristic = "heuristic" in source.source_id or source.source_id.startswith("benchmark_")
    return AssumptionGovernance(
        evidence_grade=EvidenceGrade.GRADE_1 if heuristic else EvidenceGrade.GRADE_3,
        evidence_basis=(
            EvidenceBasis.HEURISTIC_DEFAULT if heuristic else EvidenceBasis.CURATED_DEFAULT
        ),
        default_visibility=(
            DefaultVisibility.WARN if heuristic else DefaultVisibility.SILENT_TRACEABLE
        ),
        applicability_status=(
            ApplicabilityStatus.SCREENING_EXTRAPOLATION
            if heuristic
            else ApplicabilityStatus.IN_DOMAIN
        ),
        uncertainty_types=[
            UncertaintyType.PARAMETER_UNCERTAINTY,
            UncertaintyType.SCENARIO_UNCERTAINTY,
        ],
        applicability_domain=applicability_domain or {},
    )


def _assumption_record(
    *,
    name: str,
    value: ScalarValue,
    unit: str | None,
    source_kind: SourceKind,
    source: AssumptionSourceReference,
    rationale: str,
    applicability_domain: dict[str, ScalarValue] | None = None,
) -> ExposureAssumptionRecord:
    return ExposureAssumptionRecord(
        name=name,
        value=value,
        unit=unit,
        source_kind=source_kind,
        source=source,
        confidence=(
            "explicit_input"
            if source_kind == SourceKind.USER_INPUT
            else "derived"
            if source_kind == SourceKind.DERIVED
            else "heuristic_default"
            if "heuristic" in source.source_id or source.source_id.startswith("benchmark_")
            else "curated_default"
        ),
        default_applied=source_kind == SourceKind.DEFAULT_REGISTRY,
        rationale=rationale,
        governance=_assumption_governance(
            source_kind=source_kind,
            source=source,
            applicability_domain=applicability_domain,
        ),
    )


def _base_request_from_supporting_handoffs(
    supporting_handoffs: dict[str, ScalarValue | dict | list],
) -> ExposureScenarioRequest | None:
    payload = supporting_handoffs.get("baseRequest")
    if not isinstance(payload, dict):
        return None
    try:
        return ExposureScenarioRequest.model_validate(payload)
    except Exception:
        return None


def _normalized_transfer_application_method(application_method: str) -> str:
    normalized = _normalized_text(application_method)
    if normalized in {"pour_transfer", "pouring", "transfer"}:
        return "pour"
    if "wipe" in normalized:
        return "wipe"
    if "hand" in normalized:
        return "hand_application"
    if "spray" in normalized:
        return "trigger_spray"
    return normalized


_WORKER_DERMAL_TEMPLATES: tuple[dict[str, object], ...] = (
    {
        "template_id": "janitorial_wet_wipe_gloved_hands_v1",
        "template_label": "Janitorial Wet-Wipe Contact with Gloved Hands",
        "product_categories": {"household_cleaner", "disinfectant"},
        "application_methods": {"wipe"},
        "physical_forms": {"liquid"},
        "contact_patterns": {"surface_transfer", "residue_contact"},
        "ppe_states": {
            "work_gloves",
            "chemical_resistant_gloves",
            "gloves_and_protective_clothing",
        },
        "body_area_tokens": {"hand", "hands"},
        "workplace_tokens": {"janitorial", "cleaning", "custodial", "wipe", "restroom"},
        "determinant_recommendations": {
            "dermalTaskFamily": "janitorial_wet_wipe_gloved_hands",
            "contactMechanism": "wet_surface_secondary_transfer",
            "ppeAssumption": "gloved_hand_contact",
            "absorptionContext": "aqueous_surface_residue_contact",
            "contactProfile": "surface_transfer_contact_profile",
            "ppeProfile": "general_work_glove_barrier_profile",
            "bodyZoneProfile": "hands_only_body_zone",
        },
        "source_basis": [
            "worker_dermal_template_pack_2026_v1",
            "rivm_wet_cloth_dermal_contact_loading_2018",
        ],
    },
    {
        "template_id": "solvent_transfer_gloved_hands_v1",
        "template_label": "Solvent Transfer with Gloved Hands",
        "product_categories": {
            "solvent",
            "degreaser",
            "automotive_maintenance",
            "adhesive_sealant",
        },
        "application_methods": {"pour_transfer", "wipe", "hand_application"},
        "physical_forms": {"liquid", "gel"},
        "contact_patterns": {"direct_handling", "surface_transfer"},
        "ppe_states": {
            "chemical_resistant_gloves",
            "gloves_and_protective_clothing",
        },
        "body_area_tokens": {"hand", "hands"},
        "workplace_tokens": {
            "solvent",
            "transfer",
            "drum",
            "parts",
            "degreas",
            "charging",
        },
        "determinant_recommendations": {
            "dermalTaskFamily": "solvent_transfer_gloved_hands",
            "contactMechanism": "direct_liquid_contact_during_transfer",
            "ppeAssumption": "chemical_resistant_gloves",
            "absorptionContext": "volatile_liquid_handling_with_barrier",
            "contactProfile": "direct_handling_contact_profile",
            "ppeProfile": "chemical_resistant_glove_barrier_profile",
            "bodyZoneProfile": "hands_only_body_zone",
        },
        "source_basis": [
            "worker_dermal_template_pack_2026_v1",
            "exposure_platform_worker_dermal_transfer_expansion_2026",
        ],
    },
    {
        "template_id": "generic_gloved_hand_contact_v1",
        "template_label": "Generic Gloved Hand Contact",
        "product_categories": set(),
        "application_methods": set(),
        "physical_forms": {"liquid", "gel", "spray"},
        "contact_patterns": {"direct_handling", "surface_transfer", "residue_contact"},
        "ppe_states": {
            "work_gloves",
            "chemical_resistant_gloves",
            "gloves_and_protective_clothing",
        },
        "body_area_tokens": {"hand", "hands"},
        "workplace_tokens": set(),
        "determinant_recommendations": {
            "dermalTaskFamily": "generic_gloved_hand_contact",
            "contactMechanism": "direct_or_secondary_hand_contact",
            "ppeAssumption": "glove_barrier_present",
            "absorptionContext": "barrier_mediated_skin_loading",
            "contactProfile": "direct_handling_contact_profile",
            "ppeProfile": "general_work_glove_barrier_profile",
            "bodyZoneProfile": "hands_only_body_zone",
        },
        "source_basis": [
            "worker_dermal_template_pack_2026_v1",
            "worker_dermal_absorbed_dose_bridge_export_v1",
        ],
    },
    {
        "template_id": "generic_ungloved_hand_contact_v1",
        "template_label": "Generic Ungloved Hand Contact",
        "product_categories": set(),
        "application_methods": set(),
        "physical_forms": {"liquid", "gel", "spray"},
        "contact_patterns": {"direct_handling", "surface_transfer", "residue_contact"},
        "ppe_states": {"none"},
        "body_area_tokens": {"hand", "hands"},
        "workplace_tokens": set(),
        "determinant_recommendations": {
            "dermalTaskFamily": "generic_ungloved_hand_contact",
            "contactMechanism": "direct_or_secondary_hand_contact",
            "ppeAssumption": "no_dermal_barrier",
            "absorptionContext": "unprotected_hand_loading",
            "contactProfile": "direct_handling_contact_profile",
            "ppeProfile": "unprotected_skin_profile",
            "bodyZoneProfile": "hands_only_body_zone",
        },
        "source_basis": [
            "worker_dermal_template_pack_2026_v1",
            "worker_dermal_absorbed_dose_bridge_export_v1",
        ],
    },
    {
        "template_id": "generic_liquid_splash_unprotected_skin_v1",
        "template_label": "Generic Liquid Splash to Unprotected Skin",
        "product_categories": set(),
        "application_methods": set(),
        "physical_forms": {"liquid", "gel"},
        "contact_patterns": {"splash_contact"},
        "ppe_states": {"none"},
        "body_area_tokens": set(),
        "workplace_tokens": {"splash", "spray_back", "spill", "splat"},
        "determinant_recommendations": {
            "dermalTaskFamily": "generic_liquid_splash_unprotected_skin",
            "contactMechanism": "short_duration_liquid_splash",
            "ppeAssumption": "no_dermal_barrier",
            "absorptionContext": "localized_splash_loading",
            "contactProfile": "liquid_splash_contact_profile",
            "ppeProfile": "unprotected_skin_profile",
        },
        "source_basis": [
            "worker_dermal_template_pack_2026_v1",
            "worker_dermal_absorbed_dose_bridge_export_v1",
        ],
    },
)


def _template_sets(key: str, template: dict[str, object]) -> set[str]:
    return set(template.get(key, set()))


def _match_worker_dermal_template(
    params: WorkerDermalAbsorbedDoseAdapterRequest,
) -> WorkerDermalDeterminantTemplateMatch:
    category = _normalized_scalar_text(params.exposure_inputs.get("productCategory"))
    application_method = _normalized_scalar_text(params.exposure_inputs.get("applicationMethod"))
    physical_form = _normalized_scalar_text(params.exposure_inputs.get("physicalForm"))
    contact_pattern = _normalized_text(params.task_context.contact_pattern.value)
    ppe_state = _normalized_text(params.task_context.ppe_state.value)
    body_area_context = _body_area_context(params.task_context.exposed_body_areas)
    workplace_context = " ".join(
        _normalized_text(item)
        for item in (
            params.task_context.task_description,
            params.task_context.workplace_setting,
            params.task_context.surface_loading_context,
            *params.task_context.control_measures,
        )
        if item
    )

    best_payload: WorkerDermalDeterminantTemplateMatch | None = None
    best_weight = -1
    best_specificity = -1
    best_score = -1.0

    for template in _WORKER_DERMAL_TEMPLATES:
        product_categories = _template_sets("product_categories", template)
        application_methods = _template_sets("application_methods", template)
        physical_forms = _template_sets("physical_forms", template)
        contact_patterns = _template_sets("contact_patterns", template)
        ppe_states = _template_sets("ppe_states", template)
        body_area_tokens = _template_sets("body_area_tokens", template)
        workplace_tokens = _template_sets("workplace_tokens", template)

        match_basis: list[str] = []
        review_notes: list[str] = []
        matched_weight = 0
        possible_weight = 0
        specificity = 0

        if product_categories:
            possible_weight += 3
            specificity += 1
            if category and category in product_categories:
                matched_weight += 3
                match_basis.append(f"productCategory=`{category}` matched the template family.")
            else:
                continue

        if application_methods:
            possible_weight += 3
            specificity += 1
            if application_method and application_method in application_methods:
                matched_weight += 3
                match_basis.append(
                    f"applicationMethod=`{application_method}` matched the contact mode."
                )
            else:
                continue

        if physical_forms:
            possible_weight += 2
            specificity += 1
            if physical_form and physical_form in physical_forms:
                matched_weight += 2
                match_basis.append(f"physicalForm=`{physical_form}` matched the template form.")
            else:
                continue

        if contact_patterns:
            possible_weight += 3
            specificity += 1
            if contact_pattern and contact_pattern in contact_patterns:
                matched_weight += 3
                match_basis.append(
                    f"contactPattern=`{contact_pattern}` matched the template contact mode."
                )
            else:
                continue

        if ppe_states:
            possible_weight += 2
            specificity += 1
            if ppe_state and ppe_state in ppe_states:
                matched_weight += 2
                match_basis.append(f"ppeState=`{ppe_state}` matched the template barrier state.")
            else:
                continue

        if body_area_tokens:
            possible_weight += 2
            specificity += 1
            if any(token in body_area_context for token in body_area_tokens):
                matched_weight += 2
                match_basis.append("Body-area selections matched the template contact zone.")
            else:
                continue

        workplace_hit = False
        if workplace_tokens:
            possible_weight += 2
            specificity += 1
            if any(token in workplace_context for token in workplace_tokens):
                matched_weight += 2
                workplace_hit = True
                match_basis.append("Task text or workplace context matched the template family.")
            else:
                review_notes.append(
                    "No workplace token matched the packaged dermal template context, so "
                    "alignment remains partial."
                )

        match_score = matched_weight / possible_weight if possible_weight else 0.0
        template_id = str(template["template_id"])
        if template_id.startswith("generic_"):
            alignment_status = WorkerDermalTemplateAlignmentStatus.HEURISTIC
        elif workplace_tokens and not workplace_hit:
            alignment_status = WorkerDermalTemplateAlignmentStatus.PARTIAL
        else:
            alignment_status = WorkerDermalTemplateAlignmentStatus.ALIGNED

        payload = WorkerDermalDeterminantTemplateMatch(
            template_id=template_id,
            template_label=str(template["template_label"]),
            alignment_status=alignment_status,
            match_score=round(match_score, 4),
            match_basis=match_basis,
            determinant_recommendations=dict(template["determinant_recommendations"]),
            source_basis=list(template["source_basis"]),
            review_notes=review_notes,
        )

        if (
            matched_weight > best_weight
            or (
                matched_weight == best_weight
                and specificity > best_specificity
                and match_score >= best_score
            )
            or (
                matched_weight == best_weight
                and specificity == best_specificity
                and match_score > best_score
            )
        ):
            best_payload = payload
            best_weight = matched_weight
            best_specificity = specificity
            best_score = match_score

    if best_payload is not None:
        return best_payload

    return WorkerDermalDeterminantTemplateMatch(
        alignment_status=WorkerDermalTemplateAlignmentStatus.NONE,
        match_score=0.0,
        review_notes=[
            "No packaged dermal determinant template matched the current worker task.",
            "Proceed with manual dermal determinant and PPE selection before downstream use.",
        ],
    )


def _bridge_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.dermal_absorbed_dose_bridge.v1",
        plugin_id="worker_dermal_absorbed_dose_bridge_export",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Bridge package only; no dermal absorption or glove breakthrough solver is executed.",
            "Worker routing and the source dermal screening request remain preserved as "
            "supporting handoffs.",
        ],
    )


def _adapter_ingest_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.dermal_absorbed_dose_adapter_ingest.v1",
        plugin_id="worker_dermal_absorbed_dose_adapter_ingest",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Adapter ingest only; no dermal absorption, permeation, or glove breakthrough "
            "solver is executed here.",
            "The adapter envelope preserves screening and worker routing context as reviewable "
            "upstream evidence.",
        ],
    )


def _execution_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.dermal_absorbed_dose_execution.v1",
        plugin_id="worker_dermal_absorbed_dose_execution",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Execution starts from screening-style skin-boundary mass semantics and then "
            "applies PPE penetration and generic dermal absorption factors.",
            "The current kernel is PPE-aware and absorbed-dose-aware, but it is not a "
            "chemical-specific permeability model or glove-breakthrough simulator.",
        ],
    )


def build_worker_dermal_absorbed_dose_bridge(
    params: ExportWorkerDermalAbsorbedDoseBridgeRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerDermalAbsorbedDoseBridgePackage:
    registry = registry or DefaultsRegistry.load()
    base_request = params.base_request
    contact_duration_hours = (
        params.contact_duration_hours or base_request.product_use_profile.exposure_duration_hours
    )
    routing_decision = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id=base_request.chemical_id,
            route=base_request.route,
            scenario_class=base_request.scenario_class,
            product_use_profile=base_request.product_use_profile,
            population_profile=base_request.population_profile,
            requested_tier=TierLevel.TIER_2,
            prefer_current_mcp=False,
        )
    )

    missing_fields: list[str] = []
    issues: list[LimitationNote] = []
    quality_flags: list[QualityFlag] = [
        QualityFlag(
            code="worker_dermal_bridge_export",
            severity=Severity.INFO,
            message=(
                "Worker dermal absorbed-dose bridge package was exported for a future "
                "occupational dermal adapter path."
            ),
        )
    ]

    if not routing_decision.worker_detected:
        issues.append(
            LimitationNote(
                code="worker_context_not_explicit",
                severity=Severity.WARNING,
                message=(
                    "Worker context was not explicitly detected from the population profile. "
                    "Add demographic tags such as `worker` or `occupational` before treating "
                    "the bridge as a workplace handoff."
                ),
            )
        )
        quality_flags.append(
            QualityFlag(
                code="worker_context_inferred_or_missing",
                severity=Severity.WARNING,
                message=(
                    "Worker dermal bridge was built without explicit worker-tag detection in "
                    "the population profile."
                ),
            )
        )

    if contact_duration_hours is None:
        missing_fields.append("contactDurationHours")
        issues.append(
            LimitationNote(
                code="worker_dermal_contact_duration_missing",
                severity=Severity.ERROR,
                message=(
                    "Dermal worker handoff requires contactDurationHours or an explicit "
                    "product_use_profile.exposure_duration_hours value."
                ),
            )
        )

    if params.contact_pattern == WorkerDermalContactPattern.UNKNOWN:
        missing_fields.append("contactPattern")
        issues.append(
            LimitationNote(
                code="worker_dermal_contact_pattern_missing",
                severity=Severity.ERROR,
                message=(
                    "Dermal worker handoff is not adapter-ready until contactPattern is declared."
                ),
            )
        )

    if not params.exposed_body_areas:
        missing_fields.append("exposedBodyAreas")
        issues.append(
            LimitationNote(
                code="worker_dermal_body_areas_missing",
                severity=Severity.WARNING,
                message=(
                    "Dermal worker handoff is stronger when exposedBodyAreas is declared for "
                    "the contact zone."
                ),
            )
        )

    if params.ppe_state == WorkerDermalPpeState.UNKNOWN:
        missing_fields.append("ppeState")
        issues.append(
            LimitationNote(
                code="worker_dermal_ppe_missing",
                severity=Severity.WARNING,
                message=(
                    "Dermal worker handoff is stronger when ppeState is declared rather than "
                    "left as unknown."
                ),
            )
        )

    if params.surface_loading_context is None:
        missing_fields.append("surfaceLoadingContext")
        issues.append(
            LimitationNote(
                code="worker_dermal_surface_loading_context_missing",
                severity=Severity.WARNING,
                message=(
                    "Dermal worker handoff is stronger when surfaceLoadingContext states the "
                    "residue, wet-contact, or splash context."
                ),
            )
        )

    if params.workplace_setting is None:
        missing_fields.append("workplaceSetting")
        issues.append(
            LimitationNote(
                code="worker_dermal_workplace_setting_missing",
                severity=Severity.WARNING,
                message=(
                    "Dermal worker handoff is stronger when workplaceSetting is declared for "
                    "the task context."
                ),
            )
        )

    if base_request.population_profile.exposed_surface_area_cm2 is None:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_surface_area_missing",
                severity=Severity.WARNING,
                message=(
                    "The source request does not declare exposedSurfaceAreaCm2, so downstream "
                    "absorbed-dose interpretation may need manual body-zone assumptions."
                ),
            )
        )

    issues.append(
        LimitationNote(
            code="worker_dermal_bridge_no_solver",
            severity=Severity.WARNING,
            message=(
                "This package prepares a future occupational dermal absorbed-dose handoff "
                "only. Direct-Use Exposure MCP does not execute a dermal absorption or PPE "
                "solver here."
            ),
        )
    )

    ready_for_adapter = not any(item.severity == Severity.ERROR for item in issues)
    chemical_context = _coerce_worker_dermal_chemical_context(
        params.chemical_context or base_request.physchem_context
    )
    if params.chemical_context is None and chemical_context is not None:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_physchem_context_from_base_request",
                severity=Severity.INFO,
                message=(
                    "Worker dermal bridge promoted physchemContext from the base direct-use "
                    "request into the legacy chemicalContext adapter lane."
                ),
            )
        )

    task_context = WorkerDermalTaskContext(
        task_description=params.task_description,
        workplace_setting=params.workplace_setting,
        contact_duration_hours=contact_duration_hours,
        contact_pattern=params.contact_pattern,
        exposed_body_areas=params.exposed_body_areas,
        ppe_state=params.ppe_state,
        barrier_material=params.barrier_material,
        control_measures=params.control_measures,
        surface_loading_context=params.surface_loading_context,
        skin_condition=params.skin_condition,
        notes=params.notes,
    )

    use_amount_unit = _product_amount_unit(base_request.product_use_profile.use_amount_unit)
    exposure_inputs: dict[str, ScalarValue | dict | list] = {
        "applicationMethod": base_request.product_use_profile.application_method,
        "physicalForm": base_request.product_use_profile.physical_form,
        "productCategory": base_request.product_use_profile.product_category,
        "productSubtype": base_request.product_use_profile.product_subtype,
        "concentrationFraction": base_request.product_use_profile.concentration_fraction,
        "useAmountPerEvent": base_request.product_use_profile.use_amount_per_event,
        "useAmountUnit": (
            use_amount_unit.value
            if use_amount_unit is not None
            else base_request.product_use_profile.use_amount_unit
        ),
        "useEventsPerDay": base_request.product_use_profile.use_events_per_day,
        "eventDurationHours": base_request.product_use_profile.exposure_duration_hours,
        "retentionType": base_request.product_use_profile.retention_type,
        "retentionFactor": base_request.product_use_profile.retention_factor,
        "transferEfficiency": base_request.product_use_profile.transfer_efficiency,
        "densityGPerMl": base_request.product_use_profile.density_g_per_ml,
        "bodyWeightKg": base_request.population_profile.body_weight_kg,
        "exposedSurfaceAreaCm2": base_request.population_profile.exposed_surface_area_cm2,
        "region": base_request.population_profile.region,
    }

    adapter_request = WorkerDermalAbsorbedDoseAdapterRequest(
        target_model_family=params.target_model_family,
        context_of_use=params.context_of_use,
        chemical_identity={
            "chemicalId": base_request.chemical_id,
            "preferredName": base_request.chemical_name or base_request.chemical_id,
            "sourceModule": "exposure-scenario-mcp",
        },
        chemical_context=chemical_context,
        task_context=task_context,
        exposure_inputs=exposure_inputs,
        supporting_handoffs={
            "baseRequest": base_request.model_dump(mode="json", by_alias=True),
            "workerRoutingDecision": routing_decision.model_dump(mode="json", by_alias=True),
        },
    )
    compatibility_report = WorkerDermalCompatibilityReport(
        source_request_schema=base_request.schema_version,
        target_model_family=params.target_model_family,
        worker_detected=routing_decision.worker_detected,
        ready_for_adapter=ready_for_adapter,
        missing_fields=sorted(set(missing_fields)),
        issues=issues,
        recommended_next_steps=[
            "Review compatibilityReport.missingFields and fill the dermal task gaps first.",
            "Preserve adapterRequest and toolCall as the exact absorbed-dose handoff payload "
            "for a future occupational dermal adapter.",
            "Use docs://worker-dermal-bridge-guide to keep the bridge bounded as a handoff "
            "artifact rather than a solved absorbed-dose estimate.",
        ],
    )
    return WorkerDermalAbsorbedDoseBridgePackage(
        routing_decision=routing_decision.model_dump(mode="json", by_alias=True),
        adapter_request=adapter_request,
        tool_call=WorkerDermalAbsorbedDoseAdapterToolCall(arguments=adapter_request),
        compatibility_report=compatibility_report,
        quality_flags=quality_flags,
        provenance=_bridge_provenance(registry, generated_at=generated_at),
    )


def ingest_worker_dermal_absorbed_dose_task(
    params: WorkerDermalAbsorbedDoseAdapterRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerDermalAbsorbedDoseAdapterIngestResult:
    registry = registry or DefaultsRegistry.load()
    quality_flags = [
        QualityFlag(
            code="worker_dermal_adapter_request_ingested",
            severity=Severity.INFO,
            message=(
                "Worker dermal absorbed-dose adapter request was ingested and normalized "
                "into a dermal/PPE intake envelope."
            ),
        )
    ]
    limitations = [
        LimitationNote(
            code="worker_dermal_adapter_no_solver",
            severity=Severity.WARNING,
            message=(
                "This ingest step does not execute a dermal absorption solver, glove "
                "breakthrough model, or compliance-ready occupational assessment."
            ),
        ),
        LimitationNote(
            code="worker_dermal_adapter_mapping_heuristic",
            severity=Severity.WARNING,
            message=(
                "The current ingest path maps screening task fields into a structured "
                "occupational dermal envelope, but determinant selection remains packaged "
                "or heuristic unless later overridden."
            ),
        ),
    ]

    supported_by_adapter = (
        params.target_model_family == WorkerDermalModelFamily.DERMAL_ABSORPTION_PPE
    )
    if not supported_by_adapter:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_adapter_family_unsupported",
                severity=Severity.WARNING,
                message=(
                    "The current dermal ingest path only normalizes the "
                    "`dermal_absorption_ppe` family."
                ),
            )
        )
        limitations.append(
            LimitationNote(
                code="worker_dermal_adapter_family_unsupported",
                severity=Severity.WARNING,
                message=(
                    "Requested dermal model family is preserved as a handoff preference only; "
                    "no supported adapter mapping exists in this MCP for it yet."
                ),
            )
        )
        return WorkerDermalAbsorbedDoseAdapterIngestResult(
            supported_by_adapter=False,
            ready_for_adapter_execution=False,
            manual_review_required=True,
            resolved_adapter=None,
            target_model_family=params.target_model_family,
            dermal_task_envelope=None,
            quality_flags=quality_flags,
            limitations=limitations,
            provenance=_adapter_ingest_provenance(registry, generated_at=generated_at),
        )

    missing_fields: list[str] = []
    preferred_name = _normalized_scalar_text(params.chemical_identity.get("preferredName"))
    application_method = _normalized_scalar_text(params.exposure_inputs.get("applicationMethod"))
    physical_form = _normalized_scalar_text(params.exposure_inputs.get("physicalForm"))

    if not preferred_name:
        missing_fields.append("chemicalIdentity.preferredName")
    if not application_method:
        missing_fields.append("exposureInputs.applicationMethod")
    if not physical_form:
        missing_fields.append("exposureInputs.physicalForm")
    if params.task_context.contact_duration_hours is None:
        missing_fields.append("taskContext.contactDurationHours")
    if params.task_context.contact_pattern == WorkerDermalContactPattern.UNKNOWN:
        missing_fields.append("taskContext.contactPattern")
    if not params.task_context.exposed_body_areas:
        missing_fields.append("taskContext.exposedBodyAreas")
    if params.task_context.ppe_state == WorkerDermalPpeState.UNKNOWN:
        missing_fields.append("taskContext.ppeState")
    if not params.task_context.surface_loading_context:
        missing_fields.append("taskContext.surfaceLoadingContext")

    ready_for_adapter_execution = not missing_fields

    if missing_fields:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_adapter_missing_fields",
                severity=Severity.WARNING,
                message=(
                    "The current dermal adapter envelope is missing one or more fields needed "
                    "for absorbed-dose or PPE-aware execution."
                ),
            )
        )
        limitations.append(
            LimitationNote(
                code="worker_dermal_adapter_missing_fields",
                severity=Severity.WARNING,
                message=(
                    "Review the missing fields before sending this dermal envelope into a "
                    "downstream absorbed-dose or glove-barrier workflow."
                ),
            )
        )

    template_match = _match_worker_dermal_template(params)
    if template_match.alignment_status == WorkerDermalTemplateAlignmentStatus.PARTIAL:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_template_partial",
                severity=Severity.WARNING,
                message=(
                    "Dermal determinant template matched only partially; keep manual review "
                    "in the loop before downstream use."
                ),
            )
        )
    elif template_match.alignment_status == WorkerDermalTemplateAlignmentStatus.HEURISTIC:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_template_heuristic",
                severity=Severity.WARNING,
                message=("Dermal determinant template fell back to a generic heuristic family."),
            )
        )
    elif template_match.alignment_status == WorkerDermalTemplateAlignmentStatus.NONE:
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_template_none",
                severity=Severity.WARNING,
                message=(
                    "No packaged dermal determinant template matched the task; manual "
                    "determinant selection is required."
                ),
            )
        )

    contact_profile = str(
        template_match.determinant_recommendations.get("contactProfile")
        or _contact_profile(params.task_context)
    )
    ppe_profile = str(
        template_match.determinant_recommendations.get("ppeProfile")
        or _ppe_profile(params.task_context)
    )
    body_zone_profile = str(
        template_match.determinant_recommendations.get("bodyZoneProfile")
        or _body_zone_profile(params.task_context)
    )

    dermal_inputs: dict[str, ScalarValue | dict | list] = {
        "substanceName": params.chemical_identity.get("preferredName")
        or params.chemical_identity.get("chemicalId"),
        "chemicalId": params.chemical_identity.get("chemicalId"),
        "productCategory": params.exposure_inputs.get("productCategory"),
        "productSubtype": params.exposure_inputs.get("productSubtype"),
        "applicationMethod": params.exposure_inputs.get("applicationMethod"),
        "physicalForm": params.exposure_inputs.get("physicalForm"),
        "concentrationFraction": params.exposure_inputs.get("concentrationFraction"),
        "useAmountPerEvent": params.exposure_inputs.get("useAmountPerEvent"),
        "useAmountUnit": params.exposure_inputs.get("useAmountUnit"),
        "useEventsPerDay": params.exposure_inputs.get("useEventsPerDay"),
        "eventDurationHours": params.exposure_inputs.get("eventDurationHours"),
        "contactDurationHours": params.task_context.contact_duration_hours,
        "contactPattern": params.task_context.contact_pattern.value,
        "exposedBodyAreas": params.task_context.exposed_body_areas,
        "ppeState": params.task_context.ppe_state.value,
        "barrierMaterial": params.task_context.barrier_material.value,
        "controlMeasures": params.task_context.control_measures,
        "surfaceLoadingContext": params.task_context.surface_loading_context,
        "skinCondition": params.task_context.skin_condition.value,
        "transferEfficiency": params.exposure_inputs.get("transferEfficiency"),
        "retentionFactor": params.exposure_inputs.get("retentionFactor"),
        "exposedSurfaceAreaCm2": params.exposure_inputs.get("exposedSurfaceAreaCm2"),
        "bodyWeightKg": params.exposure_inputs.get("bodyWeightKg"),
        "region": params.exposure_inputs.get("region"),
        "templateAlignmentStatus": template_match.alignment_status.value,
    }
    if params.chemical_context is not None:
        dermal_inputs["chemicalContext"] = params.chemical_context.model_dump(
            mode="json",
            by_alias=True,
        )

    manual_review_required = (not ready_for_adapter_execution) or (
        template_match.alignment_status
        in {
            WorkerDermalTemplateAlignmentStatus.PARTIAL,
            WorkerDermalTemplateAlignmentStatus.HEURISTIC,
            WorkerDermalTemplateAlignmentStatus.NONE,
        }
    )

    return WorkerDermalAbsorbedDoseAdapterIngestResult(
        supported_by_adapter=True,
        ready_for_adapter_execution=ready_for_adapter_execution,
        manual_review_required=manual_review_required,
        resolved_adapter="worker_dermal_absorption_ppe_adapter",
        target_model_family=params.target_model_family,
        dermal_task_envelope=WorkerDermalAbsorbedDoseTaskEnvelope(
            contact_profile=contact_profile,
            ppe_profile=ppe_profile,
            body_zone_profile=body_zone_profile,
            determinant_template_match=template_match,
            chemical_context=params.chemical_context,
            task_summary=[
                f"Matched determinant template=`{template_match.template_id or 'none'}` with "
                f"alignmentStatus=`{template_match.alignment_status.value}`.",
                f"Mapped contactPattern=`{params.task_context.contact_pattern.value}` and "
                f"ppeState=`{params.task_context.ppe_state.value}` to contactProfile="
                f"`{contact_profile}` and ppeProfile=`{ppe_profile}`.",
                f"Mapped exposedBodyAreas to bodyZoneProfile=`{body_zone_profile}`.",
                (
                    "Preserved barrierMaterial="
                    f"`{params.task_context.barrier_material.value}` and chemicalContext "
                    "for downstream absorbed-dose execution."
                    if params.chemical_context is not None
                    else "Preserved barrierMaterial="
                    f"`{params.task_context.barrier_material.value}` for downstream "
                    "absorbed-dose execution."
                ),
            ],
            dermal_inputs=dermal_inputs,
            screening_handoff_summary={
                "workerRoutingSupportStatus": (
                    params.supporting_handoffs.get("workerRoutingDecision", {}) or {}
                ).get("supportStatus")
                or (params.supporting_handoffs.get("workerRoutingDecision", {}) or {}).get(
                    "support_status"
                ),
                "sourceRequestSchema": (
                    params.supporting_handoffs.get("baseRequest", {}) or {}
                ).get("schemaVersion")
                or (params.supporting_handoffs.get("baseRequest", {}) or {}).get(
                    "schema_version"
                ),
                "templateCatalogVersion": WORKER_DERMAL_TEMPLATE_CATALOG_VERSION,
            },
        ),
        quality_flags=quality_flags,
        limitations=limitations,
        provenance=_adapter_ingest_provenance(registry, generated_at=generated_at),
    )


def execute_worker_dermal_absorbed_dose_task(
    params: ExecuteWorkerDermalAbsorbedDoseRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerDermalAbsorbedDoseExecutionResult:
    registry = registry or DefaultsRegistry.load()
    adapter_request = params.adapter_request
    ingest_result = ingest_worker_dermal_absorbed_dose_task(
        adapter_request,
        registry=registry,
        generated_at=generated_at,
    )

    quality_flags = list(ingest_result.quality_flags)
    limitations = list(ingest_result.limitations)
    assumptions: list[ExposureAssumptionRecord] = []
    overrides = params.execution_overrides
    base_request = _base_request_from_supporting_handoffs(adapter_request.supporting_handoffs)
    product_profile = base_request.product_use_profile if base_request else None
    population_profile = base_request.population_profile if base_request else None
    chemical_id = str(
        adapter_request.chemical_identity.get("chemicalId")
        or (base_request.chemical_id if base_request else "unknown")
    )
    chemical_name = (
        str(adapter_request.chemical_identity.get("preferredName"))
        if adapter_request.chemical_identity.get("preferredName") is not None
        else (base_request.chemical_name if base_request else None)
    )

    if not ingest_result.supported_by_adapter or ingest_result.dermal_task_envelope is None:
        return WorkerDermalAbsorbedDoseExecutionResult(
            supported_by_adapter=False,
            ready_for_execution=False,
            manual_review_required=True,
            resolved_adapter=None,
            target_model_family=adapter_request.target_model_family,
            chemical_id=chemical_id,
            chemical_name=chemical_name,
            task_context=adapter_request.task_context,
            chemical_context=adapter_request.chemical_context,
            dermal_task_envelope=None,
            execution_overrides=overrides,
            quality_flags=quality_flags,
            limitations=limitations,
            provenance=_execution_provenance(registry, generated_at=generated_at),
            fit_for_purpose=FitForPurpose(
                label="unsupported_worker_dermal_execution",
                suitable_for=[],
                not_suitable_for=[
                    "worker dermal absorbed-dose execution",
                    "PPE-aware dermal scenario refinement",
                ],
            ),
            tier_semantics=TierSemantics(
                tier_claimed=TierLevel.TIER_1,
                tier_earned=TierLevel.TIER_0,
                tier_rationale=(
                    "The requested dermal model family is not executable in the current worker "
                    "dermal kernel."
                ),
                assumption_checks_passed=False,
                required_caveats=[
                    "No absorbed-dose execution was performed because the dermal model family "
                    "is unsupported."
                ],
                forbidden_interpretations=[
                    "Do not treat this response as a solved dermal absorbed-dose result."
                ],
            ),
            validation_summary=None,
            interpretation_notes=[
                "Supported worker dermal execution is currently limited to the "
                "`dermal_absorption_ppe` family."
            ],
        )

    envelope = ingest_result.dermal_task_envelope
    task_context = adapter_request.task_context
    chemical_context = adapter_request.chemical_context
    dermal_inputs = envelope.dermal_inputs
    applicability_domain = {
        "product_category": dermal_inputs.get("productCategory"),
        "application_method": dermal_inputs.get("applicationMethod"),
        "physical_form": dermal_inputs.get("physicalForm"),
        "contact_pattern": task_context.contact_pattern.value,
        "ppe_state": task_context.ppe_state.value,
        "barrier_material": task_context.barrier_material.value,
    }

    body_weight = _float_or_none(dermal_inputs.get("bodyWeightKg"))
    if body_weight is not None:
        assumptions.append(
            _assumption_record(
                name="body_weight_kg",
                value=body_weight,
                unit="kg",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source()
                if population_profile is None
                else _execution_algorithm_source(),
                rationale="Body weight was carried through the dermal adapter request.",
                applicability_domain=applicability_domain,
            )
        )
    elif population_profile is not None and population_profile.body_weight_kg is not None:
        body_weight = float(population_profile.body_weight_kg)
        assumptions.append(
            _assumption_record(
                name="body_weight_kg",
                value=body_weight,
                unit="kg",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale="Body weight was recovered from the supporting source request.",
                applicability_domain=applicability_domain,
            )
        )
    elif population_profile is not None:
        defaults, source = registry.population_defaults(population_profile.population_group)
        body_weight = defaults["body_weight_kg"]
        assumptions.append(
            _assumption_record(
                name="body_weight_kg",
                value=body_weight,
                unit="kg",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=source,
                rationale=(
                    "Body weight defaulted from the population group because the worker "
                    "dermal request did not carry an explicit body weight."
                ),
                applicability_domain=applicability_domain,
            )
        )
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_execution_body_weight_defaulted",
                severity=Severity.WARNING,
                message=(
                    "Worker dermal execution defaulted bodyWeightKg from the population group."
                ),
            )
        )

    if body_weight is None:
        limitations.append(
            LimitationNote(
                code="worker_dermal_execution_body_weight_missing",
                severity=Severity.ERROR,
                message=(
                    "Worker dermal execution requires body weight to normalize absorbed dose."
                ),
            )
        )

    explicit_external_mass = None if overrides is None else overrides.external_skin_mass_mg_per_day
    external_mass_mg_day: float | None = None
    pressurized_aerosol_volume_factor = 1.0
    pressurized_aerosol_physchem_factor = 1.0
    pressurized_aerosol_physchem_label = "generic"
    pressurized_aerosol_carrier_factor = 1.0
    pressurized_aerosol_carrier_label = "generic"
    if explicit_external_mass is not None:
        external_mass_mg_day = float(explicit_external_mass)
        assumptions.append(
            _assumption_record(
                name="external_skin_mass_mg_per_day",
                value=external_mass_mg_day,
                unit="mg/day",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale=(
                    "External skin mass per day was supplied as an execution override and "
                    "takes precedence over screening-derived external mass."
                ),
                applicability_domain=applicability_domain,
            )
        )
        quality_flags.append(
            QualityFlag(
                code="worker_dermal_execution_external_mass_override",
                severity=Severity.INFO,
                message=(
                    "Worker dermal execution used an explicit externalSkinMassMgPerDay "
                    "override instead of re-deriving skin-boundary mass."
                ),
            )
        )
    else:
        use_amount_per_event = _float_or_none(dermal_inputs.get("useAmountPerEvent"))
        concentration_fraction = _float_or_none(dermal_inputs.get("concentrationFraction"))
        use_events_per_day = _float_or_none(dermal_inputs.get("useEventsPerDay")) or 1.0
        density_g_per_ml = _float_or_none(dermal_inputs.get("densityGPerMl"))
        application_method = str(dermal_inputs.get("applicationMethod") or "")
        product_category = str(dermal_inputs.get("productCategory") or "")
        product_subtype = (
            str(dermal_inputs.get("productSubtype"))
            if dermal_inputs.get("productSubtype")
            else None
        )
        physical_form = str(dermal_inputs.get("physicalForm") or "")
        use_amount_unit = _product_amount_unit(dermal_inputs.get("useAmountUnit"))

        product_mass_g_event: float | None = None
        if use_amount_per_event is not None and use_amount_unit == ProductAmountUnit.G:
            product_mass_g_event = use_amount_per_event
            assumptions.append(
                _assumption_record(
                    name="use_amount_per_event",
                    value=use_amount_per_event,
                    unit="g/event",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Use amount per event was carried through the dermal adapter request."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        elif use_amount_per_event is not None and use_amount_unit == ProductAmountUnit.ML:
            density_defaulted = density_g_per_ml is None
            if density_g_per_ml is None:
                density_g_per_ml, density_source = registry.default_density_g_per_ml(
                    product_category or None,
                    physical_form or None,
                    product_subtype,
                )
                assumptions.append(
                    _assumption_record(
                        name="density_g_per_ml",
                        value=density_g_per_ml,
                        unit="g/mL",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=density_source,
                        rationale=(
                            "Density defaulted because the worker dermal execution request "
                            "provided a volumetric use amount without explicit density."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                quality_flags.append(
                    QualityFlag(
                        code="worker_dermal_execution_density_defaulted",
                        severity=Severity.WARNING,
                        message=(
                            "Worker dermal execution defaulted density_g_per_ml from the "
                            "shared defaults registry."
                        ),
                    )
                )
            else:
                assumptions.append(
                    _assumption_record(
                        name="density_g_per_ml",
                        value=density_g_per_ml,
                        unit="g/mL",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Density was carried through the dermal adapter request for "
                            "volumetric product-mass conversion."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if density_defaulted and application_method == "aerosol_spray":
                (
                    pressurized_aerosol_volume_factor,
                    aerosol_source,
                ) = registry.pressurized_aerosol_volume_interpretation_factor(
                    product_category or None,
                    physical_form or None,
                    product_subtype,
                )
                aerosol_physchem_adjustment = (
                    registry.pressurized_aerosol_physchem_adjustment_factor(
                        product_category or None,
                        product_subtype,
                        None
                        if chemical_context is None
                        else _float_or_none(chemical_context.vapor_pressure_mmhg),
                        None
                        if chemical_context is None
                        else _float_or_none(chemical_context.molecular_weight_g_per_mol),
                    )
                )
                if aerosol_physchem_adjustment is not None:
                    (
                        pressurized_aerosol_physchem_label,
                        pressurized_aerosol_physchem_factor,
                        aerosol_physchem_source,
                    ) = aerosol_physchem_adjustment
                    assumptions.append(
                        _assumption_record(
                            name="pressurized_aerosol_physchem_adjustment_factor",
                            value=pressurized_aerosol_physchem_factor,
                            unit="fraction",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=aerosol_physchem_source,
                            rationale=(
                                "Worker dermal aerosol mass semantics were further adjusted "
                                "with a bounded volatility and low-molecular-weight "
                                "heuristic because default density and supplied physchem "
                                "context were both active."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    if pressurized_aerosol_physchem_factor < 1.0:
                        quality_flags.append(
                            QualityFlag(
                                code=(
                                    "worker_dermal_pressurized_aerosol_physchem_"
                                    "adjustment_defaulted"
                                ),
                                severity=Severity.WARNING,
                                message=(
                                    "Worker dermal execution further reduced volumetric "
                                    "aerosol mass with a bounded aerosol volatility and "
                                    "carrier adjustment."
                                ),
                            )
                        )
                aerosol_carrier_adjustment = (
                    registry.pressurized_aerosol_carrier_family_adjustment_factor(
                        None
                        if base_request is None
                        else base_request.product_use_profile.aerosol_carrier_family
                    )
                )
                if aerosol_carrier_adjustment is not None:
                    (
                        pressurized_aerosol_carrier_label,
                        pressurized_aerosol_carrier_factor,
                        aerosol_carrier_source,
                    ) = aerosol_carrier_adjustment
                    assumptions.append(
                        _assumption_record(
                            name="pressurized_aerosol_carrier_family_adjustment_factor",
                            value=pressurized_aerosol_carrier_factor,
                            unit="fraction",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=aerosol_carrier_source,
                            rationale=(
                                "Worker dermal aerosol mass semantics were further adjusted "
                                "with a bounded carrier-family heuristic because default "
                                "density and explicit aerosol carrier context were both "
                                "active."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    if pressurized_aerosol_carrier_factor < 1.0:
                        quality_flags.append(
                            QualityFlag(
                                code=(
                                    "worker_dermal_pressurized_aerosol_carrier_"
                                    "family_adjustment_defaulted"
                                ),
                                severity=Severity.WARNING,
                                message=(
                                    "Worker dermal execution further reduced volumetric "
                                    "aerosol mass with a bounded aerosol carrier-family "
                                    "adjustment."
                                ),
                            )
                        )
                pressurized_aerosol_volume_factor *= pressurized_aerosol_carrier_factor
                pressurized_aerosol_volume_factor *= pressurized_aerosol_physchem_factor
                assumptions.append(
                    _assumption_record(
                        name="pressurized_aerosol_volume_interpretation_factor",
                        value=pressurized_aerosol_volume_factor,
                        unit="fraction",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=aerosol_source,
                        rationale=(
                            "Volumetric aerosol-spray amount was bounded with a "
                            "pressurized-aerosol interpretation factor because the worker "
                            "dermal execution request relied on default density."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                if pressurized_aerosol_volume_factor < 1.0:
                    quality_flags.append(
                        QualityFlag(
                            code=(
                                "worker_dermal_pressurized_aerosol_volume_"
                                "interpretation_defaulted"
                            ),
                            severity=Severity.WARNING,
                            message=(
                                "Worker dermal execution reduced volumetric aerosol mass with "
                                "a bounded pressurized-aerosol interpretation factor because "
                                "density was defaulted."
                            ),
                        )
                    )
            product_mass_g_event = (
                use_amount_per_event
                * density_g_per_ml
                * pressurized_aerosol_volume_factor
            )
            assumptions.append(
                _assumption_record(
                    name="use_amount_per_event",
                    value=use_amount_per_event,
                    unit="mL/event",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Use amount per event was carried through the dermal adapter request."
                    ),
                    applicability_domain=applicability_domain,
                )
            )

        if concentration_fraction is not None:
            assumptions.append(
                _assumption_record(
                    name="concentration_fraction",
                    value=concentration_fraction,
                    unit="fraction",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Concentration fraction was carried through the dermal adapter request."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        assumptions.append(
            _assumption_record(
                name="use_events_per_day",
                value=use_events_per_day,
                unit="events/day",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale="Use frequency was carried through the dermal adapter request.",
                applicability_domain=applicability_domain,
            )
        )

        retention_factor = _float_or_none(dermal_inputs.get("retentionFactor"))
        if retention_factor is None:
            retention_type = str(dermal_inputs.get("retentionType") or "surface_contact")
            retention_factor, retention_source = registry.retention_factor(
                retention_type,
                product_category or None,
            )
            assumptions.append(
                _assumption_record(
                    name="retention_factor",
                    value=retention_factor,
                    unit="fraction",
                    source_kind=SourceKind.DEFAULT_REGISTRY,
                    source=retention_source,
                    rationale=(
                        "Retention factor defaulted from the shared dermal screening defaults "
                        "because the dermal adapter request did not carry an explicit value."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        else:
            assumptions.append(
                _assumption_record(
                    name="retention_factor",
                    value=retention_factor,
                    unit="fraction",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale="Retention factor was carried through the dermal adapter request.",
                    applicability_domain=applicability_domain,
                )
            )

        transfer_efficiency = _float_or_none(dermal_inputs.get("transferEfficiency"))
        if transfer_efficiency is None:
            transfer_method = _normalized_transfer_application_method(application_method)
            transfer_efficiency, transfer_source = registry.transfer_efficiency(
                transfer_method,
                product_category or None,
            )
            assumptions.append(
                _assumption_record(
                    name="transfer_efficiency",
                    value=transfer_efficiency,
                    unit="fraction",
                    source_kind=SourceKind.DEFAULT_REGISTRY,
                    source=transfer_source,
                    rationale=(
                        "Transfer efficiency defaulted from the shared dermal screening "
                        "defaults because the dermal adapter request did not carry an explicit "
                        "value."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        else:
            assumptions.append(
                _assumption_record(
                    name="transfer_efficiency",
                    value=transfer_efficiency,
                    unit="fraction",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale="Transfer efficiency was carried through the dermal adapter request.",
                    applicability_domain=applicability_domain,
                )
            )

        if product_mass_g_event is not None and concentration_fraction is not None:
            chemical_mass_mg_event = product_mass_g_event * 1000.0 * concentration_fraction
            assumptions.append(
                _assumption_record(
                    name="chemical_mass_mg_per_event",
                    value=round(chemical_mass_mg_event, 8),
                    unit="mg/event",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Chemical mass per event was derived from product mass per event and "
                        "concentration fraction."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
            external_mass_mg_day = (
                chemical_mass_mg_event * use_events_per_day * retention_factor * transfer_efficiency
            )
            assumptions.append(
                _assumption_record(
                    name="external_skin_mass_mg_per_day",
                    value=round(external_mass_mg_day, 8),
                    unit="mg/day",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "External skin mass per day was derived from chemical mass per event, "
                        "use frequency, retention factor, and transfer efficiency."
                    ),
                    applicability_domain=applicability_domain,
                )
            )

    explicit_area = None if overrides is None else overrides.body_zone_surface_area_cm2
    if explicit_area is not None:
        body_zone_area_cm2 = float(explicit_area)
        assumptions.append(
            _assumption_record(
                name="body_zone_surface_area_cm2",
                value=body_zone_area_cm2,
                unit="cm2",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale=(
                    "Body-zone surface area was supplied as an execution override and takes "
                    "precedence over the source request or body-zone heuristic."
                ),
                applicability_domain=applicability_domain,
            )
        )
    else:
        body_zone_area_cm2 = _float_or_none(dermal_inputs.get("exposedSurfaceAreaCm2"))
        if body_zone_area_cm2 is not None:
            assumptions.append(
                _assumption_record(
                    name="body_zone_surface_area_cm2",
                    value=body_zone_area_cm2,
                    unit="cm2",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Exposed surface area was carried through the dermal adapter request."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        else:
            body_zone_area_cm2, area_source = registry.worker_dermal_body_zone_surface_area_cm2(
                envelope.body_zone_profile
            )
            assumptions.append(
                _assumption_record(
                    name="body_zone_surface_area_cm2",
                    value=body_zone_area_cm2,
                    unit="cm2",
                    source_kind=SourceKind.DEFAULT_REGISTRY,
                    source=area_source,
                    rationale=(
                        "Body-zone surface area defaulted from the worker dermal execution "
                        "profile because no explicit exposed area was provided."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
            quality_flags.append(
                QualityFlag(
                    code="worker_dermal_execution_body_zone_area_defaulted",
                    severity=Severity.WARNING,
                    message=(
                        "Worker dermal execution defaulted body-zone surface area from the "
                        "bodyZoneProfile heuristic pack."
                    ),
                )
            )

    gross_external_mass_mg_day = external_mass_mg_day
    retained_external_mass_mg_day = external_mass_mg_day
    runoff_mass_mg_day = 0.0
    runoff_fraction = 0.0
    max_retained_loading_mg_per_cm2 = None
    surface_loading_cap_applied = False
    if external_mass_mg_day is not None:
        (
            max_retained_loading_mg_per_cm2,
            surface_loading_cap_source,
        ) = registry.worker_dermal_max_retained_surface_loading_mg_per_cm2(
            physical_form=str(dermal_inputs.get("physicalForm") or "global"),
            contact_profile=envelope.contact_profile,
        )
        assumptions.append(
            _assumption_record(
                name="max_retained_surface_loading_mg_per_cm2",
                value=max_retained_loading_mg_per_cm2,
                unit="mg/cm2-day",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=surface_loading_cap_source,
                rationale=(
                    "Maximum retained surface loading defaulted from the worker dermal "
                    "surface-cap heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
        retained_external_mass_mg_day = min(
            external_mass_mg_day,
            max_retained_loading_mg_per_cm2 * body_zone_area_cm2,
        )
        runoff_mass_mg_day = max(external_mass_mg_day - retained_external_mass_mg_day, 0.0)
        runoff_fraction = (
            runoff_mass_mg_day / external_mass_mg_day if external_mass_mg_day > 0.0 else 0.0
        )
        surface_loading_cap_applied = runoff_mass_mg_day > 1e-12
        assumptions.append(
            _assumption_record(
                name="retained_external_skin_mass_mg_per_day",
                value=round(retained_external_mass_mg_day, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Retained external skin mass per day was bounded by the maximum retained "
                    "surface loading before PPE and absorption were applied."
                ),
                applicability_domain=applicability_domain,
            )
        )
        assumptions.append(
            _assumption_record(
                name="runoff_mass_mg_per_day",
                value=round(runoff_mass_mg_day, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Runoff mass per day captures external mass above the bounded retained "
                    "surface-loading ceiling."
                ),
                applicability_domain=applicability_domain,
            )
        )
        assumptions.append(
            _assumption_record(
                name="surface_loading_cap_applied",
                value=surface_loading_cap_applied,
                unit=None,
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Indicates whether the bounded retained surface-loading cap constrained "
                    "the gross external skin mass."
                ),
                applicability_domain=applicability_domain,
            )
        )
        if surface_loading_cap_applied:
            quality_flags.append(
                QualityFlag(
                    code="worker_dermal_surface_loading_cap_applied",
                    severity=Severity.WARNING,
                    message=(
                        "Worker dermal execution capped retained skin-surface loading and "
                        "treated the excess mass as runoff or non-retained contact."
                    ),
                )
            )

    explicit_contact_duration_hours = task_context.contact_duration_hours
    barrier_like_ppe = False
    barrier_chemistry_profile = "generic"
    barrier_breakthrough_profile = "not_applied"
    barrier_breakthrough_lag_hours = 0.0
    barrier_breakthrough_transition_hours = 0.0
    barrier_breakthrough_fraction = 1.0
    evaporation_rate_per_hour = 0.0
    evaporation_competition_factor = 1.0

    ppe_penetration_override = None if overrides is None else overrides.ppe_penetration_factor
    if ppe_penetration_override is not None:
        ppe_penetration_factor = float(ppe_penetration_override)
        base_ppe_penetration_factor = ppe_penetration_factor
        barrier_material_factor = 1.0
        barrier_chemistry_factor = 1.0
        barrier_chemistry_profile = "generic"
        assumptions.append(
            _assumption_record(
                name="ppe_penetration_factor",
                value=ppe_penetration_factor,
                unit="fraction",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale=("PPE penetration factor was supplied as an execution override."),
                applicability_domain=applicability_domain,
            )
        )
    else:
        (
            base_ppe_penetration_factor,
            ppe_source,
        ) = registry.worker_dermal_ppe_penetration_factor(
            task_context.ppe_state.value
        )
        assumptions.append(
            _assumption_record(
                name="base_ppe_penetration_factor",
                value=base_ppe_penetration_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=ppe_source,
                rationale=(
                    "Base PPE penetration factor defaulted from the worker dermal PPE "
                    "heuristic pack before any barrier-material modifier was applied."
                ),
                applicability_domain=applicability_domain,
            )
        )
        barrier_material_factor = 1.0
        barrier_chemistry_factor = 1.0
        barrier_like_ppe = task_context.ppe_state in {
            WorkerDermalPpeState.WORK_GLOVES,
            WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            WorkerDermalPpeState.PROTECTIVE_CLOTHING,
            WorkerDermalPpeState.GLOVES_AND_PROTECTIVE_CLOTHING,
        }
        if barrier_like_ppe:
            if task_context.barrier_material != WorkerDermalBarrierMaterial.UNKNOWN:
                (
                    barrier_material_factor,
                    barrier_source,
                ) = registry.worker_dermal_barrier_material_factor(
                    task_context.barrier_material.value
                )
                assumptions.append(
                    _assumption_record(
                        name="barrier_material",
                        value=task_context.barrier_material.value,
                        unit="qualitative",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Barrier material was carried through the dermal adapter request."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                assumptions.append(
                    _assumption_record(
                        name="barrier_material_factor",
                        value=barrier_material_factor,
                        unit="factor",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=barrier_source,
                        rationale=(
                            "Barrier-material modifier defaulted from the worker dermal "
                            "material heuristic pack."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                (
                    barrier_chemistry_profile,
                    barrier_chemistry_factor,
                    barrier_chemistry_source,
                ) = registry.worker_dermal_barrier_chemistry_factor(
                    task_context.barrier_material.value,
                    log_kow=(
                        chemical_context.log_kow
                        if chemical_context is not None
                        else None
                    ),
                    water_solubility_mg_per_l=(
                        chemical_context.water_solubility_mg_per_l
                        if chemical_context is not None
                        else None
                    ),
                )
                assumptions.append(
                    _assumption_record(
                        name="barrier_chemistry_profile",
                        value=barrier_chemistry_profile,
                        unit="qualitative",
                        source_kind=SourceKind.DERIVED,
                        source=barrier_chemistry_source,
                        rationale=(
                            "Barrier-chemistry interaction profile was derived from the "
                            "available chemical context and barrier material."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                assumptions.append(
                    _assumption_record(
                        name="barrier_chemistry_factor",
                        value=barrier_chemistry_factor,
                        unit="factor",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=barrier_chemistry_source,
                        rationale=(
                            "Barrier-chemistry modifier defaulted from the worker dermal "
                            "material-chemistry interaction heuristic pack."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                if explicit_contact_duration_hours is not None:
                    (
                        barrier_breakthrough_lag_hours,
                        barrier_breakthrough_source,
                    ) = registry.worker_dermal_barrier_breakthrough_lag_hours(
                        task_context.barrier_material.value,
                        chemistry_profile=barrier_chemistry_profile,
                    )
                    (
                        barrier_breakthrough_transition_hours,
                        barrier_breakthrough_transition_source,
                    ) = registry.worker_dermal_barrier_breakthrough_transition_hours()
                    barrier_breakthrough_profile = barrier_chemistry_profile
                    barrier_breakthrough_fraction = _bounded_transition_fraction(
                        duration_hours=explicit_contact_duration_hours,
                        lag_hours=barrier_breakthrough_lag_hours,
                        transition_hours=barrier_breakthrough_transition_hours,
                    )
                    assumptions.append(
                        _assumption_record(
                            name="barrier_breakthrough_lag_hours",
                            value=barrier_breakthrough_lag_hours,
                            unit="hours",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=barrier_breakthrough_source,
                            rationale=(
                                "Barrier breakthrough lag time defaulted from the bounded "
                                "worker dermal timing heuristic pack."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    assumptions.append(
                        _assumption_record(
                            name="barrier_breakthrough_transition_hours",
                            value=barrier_breakthrough_transition_hours,
                            unit="hours",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=barrier_breakthrough_transition_source,
                            rationale=(
                                "Barrier breakthrough transition window defaulted from the "
                                "bounded worker dermal timing heuristic pack."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    assumptions.append(
                        _assumption_record(
                            name="barrier_breakthrough_fraction",
                            value=round(barrier_breakthrough_fraction, 8),
                            unit="fraction",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Barrier breakthrough fraction was derived from declared "
                                "contact duration, lag time, and the bounded breakthrough "
                                "transition window."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    if barrier_breakthrough_fraction < 1.0:
                        quality_flags.append(
                            QualityFlag(
                                code="worker_dermal_breakthrough_lag_applied",
                                severity=Severity.WARNING,
                                message=(
                                    "Worker dermal execution attenuated PPE penetration using "
                                    "a bounded barrier breakthrough-lag profile for a short-"
                                    "duration contact."
                                ),
                            )
                        )
            else:
                quality_flags.append(
                    QualityFlag(
                        code="worker_dermal_execution_barrier_material_generic",
                        severity=Severity.WARNING,
                        message=(
                            "Worker dermal execution used a generic barrier-material "
                            "assumption because PPE was declared without a specific "
                            "barrierMaterial."
                        ),
                    )
                )
        ppe_penetration_factor = min(
            max(
                base_ppe_penetration_factor
                * barrier_material_factor
                * barrier_chemistry_factor,
                0.0,
            )
            * barrier_breakthrough_fraction,
            1.0,
        )
        assumptions.append(
            _assumption_record(
                name="ppe_penetration_factor",
                value=round(ppe_penetration_factor, 8),
                unit="fraction",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Effective PPE penetration factor was derived from the base PPE state "
                    "plus any applicable barrier-material, barrier-chemistry, and bounded "
                    "breakthrough-timing modifiers."
                ),
                applicability_domain=applicability_domain,
            )
        )

    absorption_override = None if overrides is None else overrides.dermal_absorption_fraction
    if absorption_override is not None:
        dermal_absorption_fraction = float(absorption_override)
        assumptions.append(
            _assumption_record(
                name="dermal_absorption_fraction",
                value=dermal_absorption_fraction,
                unit="fraction",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale=("Dermal absorption fraction was supplied as an execution override."),
                applicability_domain=applicability_domain,
            )
        )
        base_absorption_fraction = dermal_absorption_fraction
        contact_pattern_factor = 1.0
        contact_duration_factor = 1.0
        skin_condition_factor = 1.0
        log_kow_factor = 1.0
        molecular_weight_factor = 1.0
        water_solubility_factor = 1.0
        vapor_pressure_factor = 1.0
        chemical_context_factor = 1.0
    else:
        physical_form = str(dermal_inputs.get("physicalForm") or "global")
        base_absorption_fraction, base_absorption_source = (
            registry.worker_dermal_base_absorption_fraction(physical_form)
        )
        assumptions.append(
            _assumption_record(
                name="base_dermal_absorption_fraction",
                value=base_absorption_fraction,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=base_absorption_source,
                rationale=(
                    "Base dermal absorption fraction defaulted from the worker dermal "
                    "execution physical-form heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
        contact_pattern_factor, contact_pattern_source = (
            registry.worker_dermal_contact_pattern_factor(task_context.contact_pattern.value)
        )
        assumptions.append(
            _assumption_record(
                name="contact_pattern_factor",
                value=contact_pattern_factor,
                unit="factor",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=contact_pattern_source,
                rationale=(
                    "Contact-pattern factor defaulted from the worker dermal execution "
                    "contact-pattern heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
        duration_override = None if overrides is None else overrides.contact_duration_factor
        if duration_override is not None:
            contact_duration_factor = float(duration_override)
            assumptions.append(
                _assumption_record(
                    name="contact_duration_factor",
                    value=contact_duration_factor,
                    unit="factor",
                    source_kind=SourceKind.USER_INPUT,
                    source=_execution_algorithm_source(),
                    rationale=("Contact-duration factor was supplied as an execution override."),
                    applicability_domain=applicability_domain,
                )
            )
        else:
            contact_duration_hours = task_context.contact_duration_hours or 1.0
            contact_duration_factor, duration_source = (
                registry.worker_dermal_contact_duration_factor(contact_duration_hours)
            )
            assumptions.append(
                _assumption_record(
                    name="contact_duration_factor",
                    value=contact_duration_factor,
                    unit="factor",
                    source_kind=SourceKind.DEFAULT_REGISTRY,
                    source=duration_source,
                    rationale=(
                        "Contact-duration factor defaulted from the worker dermal execution "
                        "duration-scaling heuristic pack."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
        skin_condition_factor, skin_condition_source = registry.worker_dermal_skin_condition_factor(
            task_context.skin_condition.value
        )
        assumptions.append(
            _assumption_record(
                name="skin_condition_factor",
                value=skin_condition_factor,
                unit="factor",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=skin_condition_source,
                rationale=(
                    "Skin-condition factor defaulted from the worker dermal execution "
                    "heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
        log_kow_factor = 1.0
        molecular_weight_factor = 1.0
        water_solubility_factor = 1.0
        vapor_pressure_factor = 1.0
        chemical_context_factor = 1.0
        if _has_worker_dermal_chemical_context(chemical_context):
            if chemical_context is not None and chemical_context.log_kow is not None:
                assumptions.append(
                    _assumption_record(
                        name="log_kow",
                        value=chemical_context.log_kow,
                        unit="log10",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "logKow was carried through the dermal adapter request for "
                            "bounded absorption refinement."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                log_kow_factor, log_kow_source = registry.worker_dermal_log_kow_factor(
                    chemical_context.log_kow
                )
                assumptions.append(
                    _assumption_record(
                        name="log_kow_factor",
                        value=log_kow_factor,
                        unit="factor",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=log_kow_source,
                        rationale=(
                            "logKow modifier defaulted from the worker dermal physchem "
                            "heuristic pack."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if (
                chemical_context is not None
                and chemical_context.molecular_weight_g_per_mol is not None
            ):
                assumptions.append(
                    _assumption_record(
                        name="molecular_weight_g_per_mol",
                        value=chemical_context.molecular_weight_g_per_mol,
                        unit="g/mol",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Molecular weight was carried through the dermal adapter request "
                            "for bounded absorption refinement."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                (
                    molecular_weight_factor,
                    molecular_weight_source,
                ) = registry.worker_dermal_molecular_weight_factor(
                    chemical_context.molecular_weight_g_per_mol
                )
                assumptions.append(
                    _assumption_record(
                        name="molecular_weight_factor",
                        value=molecular_weight_factor,
                        unit="factor",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=molecular_weight_source,
                        rationale=(
                            "Molecular-weight modifier defaulted from the worker dermal "
                            "physchem heuristic pack."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if (
                chemical_context is not None
                and chemical_context.water_solubility_mg_per_l is not None
            ):
                assumptions.append(
                    _assumption_record(
                        name="water_solubility_mg_per_l",
                        value=chemical_context.water_solubility_mg_per_l,
                        unit="mg/L",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Water solubility was carried through the dermal adapter request "
                            "for bounded absorption refinement."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                (
                    water_solubility_factor,
                    water_solubility_source,
                ) = registry.worker_dermal_water_solubility_factor(
                    chemical_context.water_solubility_mg_per_l
                )
                assumptions.append(
                    _assumption_record(
                        name="water_solubility_factor",
                        value=water_solubility_factor,
                        unit="factor",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=water_solubility_source,
                        rationale=(
                            "Water-solubility modifier defaulted from the worker dermal "
                            "physchem heuristic pack."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if chemical_context is not None and chemical_context.vapor_pressure_mmhg is not None:
                assumptions.append(
                    _assumption_record(
                        name="vapor_pressure_mmhg",
                        value=chemical_context.vapor_pressure_mmhg,
                        unit="mmHg",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Vapor pressure was carried through the dermal adapter request "
                            "for bounded volatility refinement."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
                if explicit_contact_duration_hours is not None:
                    (
                        evaporation_rate_per_hour,
                        evaporation_source,
                    ) = registry.worker_dermal_evaporation_rate_per_hour(
                        chemical_context.vapor_pressure_mmhg
                    )
                    evaporation_competition_factor = math.exp(
                        -evaporation_rate_per_hour * explicit_contact_duration_hours
                    )
                    assumptions.append(
                        _assumption_record(
                            name="evaporation_rate_per_hour",
                            value=round(evaporation_rate_per_hour, 8),
                            unit="per hour",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=evaporation_source,
                            rationale=(
                                "Evaporation competition rate defaulted from the worker "
                                "dermal volatility heuristic pack."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    assumptions.append(
                        _assumption_record(
                            name="evaporation_competition_factor",
                            value=round(evaporation_competition_factor, 8),
                            unit="factor",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Evaporation competition factor was derived from vapor "
                                "pressure and declared contact duration so high-volatility "
                                "contacts can reduce effective dermal uptake."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                vapor_pressure_factor = evaporation_competition_factor
            (
                chemical_context_bounds,
                chemical_context_bounds_source,
            ) = registry.worker_dermal_chemical_context_factor_bounds()
            chemical_context_factor = min(
                max(
                    (
                        log_kow_factor
                        * molecular_weight_factor
                        * water_solubility_factor
                    ),
                    chemical_context_bounds[0],
                ),
                chemical_context_bounds[1],
            )
            assumptions.append(
                _assumption_record(
                    name="chemical_context_factor",
                    value=round(chemical_context_factor, 8),
                    unit="factor",
                    source_kind=SourceKind.DERIVED,
                    source=chemical_context_bounds_source,
                rationale=(
                    "Chemical-context modifier was derived from bounded logKow, "
                    "molecular-weight, and water-solubility heuristic factors."
                ),
                applicability_domain=applicability_domain,
            )
            )
        else:
            quality_flags.append(
                QualityFlag(
                    code="worker_dermal_execution_chemical_context_generic",
                    severity=Severity.INFO,
                    message=(
                        "Worker dermal execution used generic absorption heuristics because "
                        "no chemicalContext descriptors were supplied."
                    ),
                )
            )
        dermal_absorption_fraction = min(
            base_absorption_fraction
            * contact_pattern_factor
            * contact_duration_factor
            * skin_condition_factor
            * chemical_context_factor,
            1.0,
        )
        dermal_absorption_fraction = min(
            dermal_absorption_fraction * evaporation_competition_factor,
            1.0,
        )
        assumptions.append(
            _assumption_record(
                name="dermal_absorption_fraction",
                value=round(dermal_absorption_fraction, 8),
                unit="fraction",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Effective dermal absorption fraction was derived from the base physical-"
                    "form fraction, contact-pattern factor, contact-duration factor, "
                    "skin-condition factor, any bounded chemical-context modifier, and any "
                    "bounded evaporation-competition attenuation."
                ),
                applicability_domain=applicability_domain,
            )
        )

    if external_mass_mg_day is None:
        limitations.append(
            LimitationNote(
                code="worker_dermal_execution_external_mass_missing",
                severity=Severity.ERROR,
                message=(
                    "Worker dermal execution could not resolve external skin mass per day from "
                    "either an override or the source screening inputs."
                ),
            )
        )

    protected_external_mass_mg_day = None
    absorbed_mass_mg_day = None
    external_dose = None
    absorbed_dose = None
    route_metrics: dict[str, ScalarValue | dict | list] = {
        "templateId": envelope.determinant_template_match.template_id,
        "templateAlignmentStatus": envelope.determinant_template_match.alignment_status.value,
        "bodyZoneProfile": envelope.body_zone_profile,
        "contactProfile": envelope.contact_profile,
        "ppeProfile": envelope.ppe_profile,
    }

    if external_mass_mg_day is not None:
        protected_external_mass_mg_day = retained_external_mass_mg_day * ppe_penetration_factor
        absorbed_mass_mg_day = protected_external_mass_mg_day * dermal_absorption_fraction
        assumptions.append(
            _assumption_record(
                name="protected_external_skin_mass_mg_per_day",
                value=round(protected_external_mass_mg_day, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Protected external skin mass per day was derived by applying the PPE "
                    "penetration factor to the skin-boundary external mass."
                ),
                applicability_domain=applicability_domain,
            )
        )
        assumptions.append(
            _assumption_record(
                name="absorbed_mass_mg_per_day",
                value=round(absorbed_mass_mg_day, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Absorbed dermal mass per day was derived by applying the effective dermal "
                    "absorption fraction to the PPE-adjusted skin-boundary mass."
                ),
                applicability_domain=applicability_domain,
            )
        )
        route_metrics["externalSkinMassMgPerDay"] = round(external_mass_mg_day, 8)
        route_metrics["retainedExternalSkinMassMgPerDay"] = round(
            retained_external_mass_mg_day, 8
        )
        route_metrics["protectedExternalSkinMassMgPerDay"] = round(
            protected_external_mass_mg_day,
            8,
        )
        route_metrics["absorbedMassMgPerDay"] = round(absorbed_mass_mg_day, 8)
        route_metrics["bodyZoneSurfaceAreaCm2"] = round(body_zone_area_cm2, 8)
        route_metrics["surfaceLoadingMgPerCm2Day"] = round(
            gross_external_mass_mg_day / body_zone_area_cm2,
            8,
        )
        route_metrics["maxRetainedLoadingMgPerCm2Day"] = round(
            max_retained_loading_mg_per_cm2,
            8,
        )
        route_metrics["retainedSurfaceLoadingMgPerCm2Day"] = round(
            retained_external_mass_mg_day / body_zone_area_cm2,
            8,
        )
        route_metrics["absorbedLoadingMgPerCm2Day"] = round(
            absorbed_mass_mg_day / body_zone_area_cm2,
            8,
        )
        route_metrics["runoffMassMgPerDay"] = round(runoff_mass_mg_day, 8)
        route_metrics["runoffFraction"] = round(runoff_fraction, 8)
        route_metrics["surfaceLoadingCapApplied"] = surface_loading_cap_applied
        route_metrics["ppePenetrationFactor"] = round(ppe_penetration_factor, 8)
        route_metrics["dermalAbsorptionFraction"] = round(dermal_absorption_fraction, 8)
        if pressurized_aerosol_volume_factor != 1.0:
            route_metrics["pressurizedAerosolVolumeInterpretationFactor"] = round(
                pressurized_aerosol_volume_factor,
                8,
            )
        if pressurized_aerosol_physchem_factor != 1.0:
            route_metrics["pressurizedAerosolPhyschemAdjustmentFactor"] = round(
                pressurized_aerosol_physchem_factor,
                8,
            )
            route_metrics["pressurizedAerosolPhyschemProfile"] = (
                pressurized_aerosol_physchem_label
            )
        if pressurized_aerosol_carrier_factor != 1.0:
            route_metrics["pressurizedAerosolCarrierFamilyAdjustmentFactor"] = round(
                pressurized_aerosol_carrier_factor,
                8,
            )
            route_metrics["pressurizedAerosolCarrierFamily"] = (
                pressurized_aerosol_carrier_label
            )
        if ppe_penetration_override is None:
            route_metrics["basePpePenetrationFactor"] = round(
                base_ppe_penetration_factor,
                8,
            )
            route_metrics["barrierMaterial"] = task_context.barrier_material.value
            route_metrics["barrierMaterialFactor"] = round(barrier_material_factor, 8)
            route_metrics["barrierChemistryProfile"] = barrier_chemistry_profile
            route_metrics["barrierChemistryFactor"] = round(barrier_chemistry_factor, 8)
            if (
                barrier_like_ppe
                and task_context.barrier_material != WorkerDermalBarrierMaterial.UNKNOWN
                and explicit_contact_duration_hours is not None
            ):
                route_metrics["barrierBreakthroughProfile"] = barrier_breakthrough_profile
                route_metrics["barrierBreakthroughLagHours"] = round(
                    barrier_breakthrough_lag_hours,
                    8,
                )
                route_metrics["barrierBreakthroughTransitionHours"] = round(
                    barrier_breakthrough_transition_hours,
                    8,
                )
                route_metrics["barrierBreakthroughFraction"] = round(
                    barrier_breakthrough_fraction,
                    8,
                )
        if absorption_override is None:
            route_metrics["baseDermalAbsorptionFraction"] = round(base_absorption_fraction, 8)
            route_metrics["contactPatternFactor"] = round(contact_pattern_factor, 8)
            route_metrics["contactDurationFactor"] = round(contact_duration_factor, 8)
            route_metrics["skinConditionFactor"] = round(skin_condition_factor, 8)
            route_metrics["chemicalContextFactor"] = round(chemical_context_factor, 8)
            if chemical_context is not None and chemical_context.log_kow is not None:
                route_metrics["logKow"] = round(chemical_context.log_kow, 8)
                route_metrics["logKowFactor"] = round(log_kow_factor, 8)
            if (
                chemical_context is not None
                and chemical_context.molecular_weight_g_per_mol is not None
            ):
                route_metrics["molecularWeightGPerMol"] = round(
                    chemical_context.molecular_weight_g_per_mol,
                    8,
                )
                route_metrics["molecularWeightFactor"] = round(
                    molecular_weight_factor,
                    8,
                )
            if (
                chemical_context is not None
                and chemical_context.water_solubility_mg_per_l is not None
            ):
                route_metrics["waterSolubilityMgPerL"] = round(
                    chemical_context.water_solubility_mg_per_l,
                    8,
                )
                route_metrics["waterSolubilityFactor"] = round(
                    water_solubility_factor,
                    8,
                )
            if chemical_context is not None and chemical_context.vapor_pressure_mmhg is not None:
                route_metrics["vaporPressureMmhg"] = round(
                    chemical_context.vapor_pressure_mmhg,
                    8,
                )
                route_metrics["vaporPressureFactor"] = round(vapor_pressure_factor, 8)
                route_metrics["evaporationCompetitionFactor"] = round(
                    evaporation_competition_factor,
                    8,
                )
                if explicit_contact_duration_hours is not None:
                    route_metrics["evaporationRatePerHour"] = round(
                        evaporation_rate_per_hour,
                        8,
                    )

        if body_weight is not None:
            normalized_external = retained_external_mass_mg_day / body_weight
            normalized_absorbed = absorbed_mass_mg_day / body_weight
            assumptions.append(
                _assumption_record(
                    name="normalized_external_dose_mg_per_kg_day",
                    value=round(normalized_external, 8),
                    unit="mg/kg-day",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Normalized external dermal dose was derived from retained skin-"
                        "boundary mass and body weight."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
            assumptions.append(
                _assumption_record(
                    name="normalized_absorbed_dose_mg_per_kg_day",
                    value=round(normalized_absorbed, 8),
                    unit="mg/kg-day",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Normalized absorbed dermal dose was derived from absorbed dermal mass "
                        "and body weight."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
            external_dose = ScenarioDose(
                metric="normalized_external_skin_dose",
                value=round(normalized_external, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            )
            absorbed_dose = ScenarioDose(
                metric="normalized_absorbed_dose",
                value=round(normalized_absorbed, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            )

    limitations.extend(
        [
            LimitationNote(
                code="worker_dermal_execution_surface_loading_cap",
                severity=Severity.WARNING,
                message=(
                    "Retained skin-boundary loading is bounded by a screening surface-cap "
                    "heuristic before PPE and absorption are applied; excess mass is treated "
                    "as runoff or non-retained contact."
                ),
            ),
            LimitationNote(
                code=(
                    "worker_dermal_execution_bounded_physchem_absorption"
                    if _has_worker_dermal_chemical_context(chemical_context)
                    else "worker_dermal_execution_generic_absorption"
                ),
                severity=Severity.WARNING,
                message=(
                    "The execution kernel uses bounded chemistry-aware modifiers layered onto "
                    "generic physical-form and contact-pattern absorption factors; it is not "
                    "a chemical-specific dermal permeability model."
                    if _has_worker_dermal_chemical_context(chemical_context)
                    else "The execution kernel uses generic physical-form and contact-pattern "
                    "absorption factors rather than chemical-specific dermal permeability data."
                ),
            ),
            *(
                [
                    LimitationNote(
                        code="worker_dermal_execution_bounded_evaporation_competition",
                        severity=Severity.WARNING,
                        message=(
                            "Volatility-aware contacts apply a bounded evaporation-competition "
                            "term derived from vapor pressure and contact duration, but this "
                            "is still not a full finite-dose mass-transfer or skin-surface "
                            "evaporation model."
                        ),
                    )
                ]
                if (
                    chemical_context is not None
                    and chemical_context.vapor_pressure_mmhg is not None
                    and explicit_contact_duration_hours is not None
                )
                else []
            ),
            LimitationNote(
                code=(
                    "worker_dermal_execution_bounded_barrier_material"
                    if task_context.barrier_material != WorkerDermalBarrierMaterial.UNKNOWN
                    else "worker_dermal_execution_generic_ppe"
                ),
                severity=Severity.WARNING,
                message=(
                    "PPE effects include bounded barrier-material and barrier-chemistry "
                    "modifiers layered onto residual penetration factors, but they still do "
                    "not represent certified protection factors, degradation, or full "
                    "permeation kinetics."
                    if task_context.barrier_material != WorkerDermalBarrierMaterial.UNKNOWN
                    else "PPE effects are represented as residual penetration factors and do "
                    "not capture glove material selection, breakthrough timing, or "
                    "degradation."
                ),
            ),
            *(
                [
                    LimitationNote(
                        code="worker_dermal_execution_bounded_breakthrough_timing",
                        severity=Severity.WARNING,
                        message=(
                            "Barrier timing effects use a bounded lag-and-transition profile "
                            "derived from contact duration and broad material/chemistry "
                            "classes, not certified glove breakthrough curves."
                        ),
                    )
                ]
                if (
                    barrier_like_ppe
                    and task_context.barrier_material != WorkerDermalBarrierMaterial.UNKNOWN
                    and explicit_contact_duration_hours is not None
                )
                else []
            ),
            LimitationNote(
                code="worker_dermal_execution_not_compliance_ready",
                severity=Severity.WARNING,
                message=(
                    "Treat this as a PPE-aware absorbed-dose screening estimate for worker "
                    "scenario refinement, not as a compliance-ready occupational assessment."
                ),
            ),
        ]
    )
    quality_flags.append(
        QualityFlag(
            code="worker_dermal_execution_completed",
            severity=Severity.INFO,
            message=(
                "Worker dermal absorbed-dose execution completed using the PPE-aware screening "
                "kernel."
            ),
        )
    )

    ready_for_execution = ingest_result.ready_for_adapter_execution and not any(
        limitation.severity == Severity.ERROR for limitation in limitations
    )
    manual_review_required = ingest_result.manual_review_required

    fit_for_purpose = FitForPurpose(
        label="worker_dermal_absorbed_dose_screening",
        suitable_for=[
            "PPE-aware occupational dermal scoping",
            "worker dermal absorbed-dose screening",
            "PBPK-ready dermal dose handoff after expert review",
        ],
        not_suitable_for=[
            "chemical-specific skin permeation prediction",
            "glove-breakthrough timing analysis",
            "occupational compliance determination",
        ],
    )
    tier_semantics = TierSemantics(
        tier_claimed=TierLevel.TIER_1,
        tier_earned=TierLevel.TIER_1 if ready_for_execution else TierLevel.TIER_0,
        tier_rationale=(
            "Worker dermal execution reuses deterministic skin-boundary loading semantics and "
            "adds bounded PPE and absorption factors."
        ),
        assumption_checks_passed=ready_for_execution,
        required_caveats=[
            "Interpret the external dose as skin-boundary worker dermal loading after the "
            "current task assumptions.",
            "Interpret the absorbed dose as a PPE-aware screening estimate that still relies "
            "on generic absorption and barrier factors.",
        ],
        forbidden_interpretations=[
            "Do not treat the absorbed dose as a chemical-specific permeability result.",
            "Do not treat the PPE factor as glove-breakthrough or certified protection data.",
            "Do not use this output as a final occupational compliance determination.",
        ],
    )

    interpretation_notes = [
        "Execution starts from the skin-boundary external mass implied by the screening-style "
        "product-use inputs or an explicit external mass override.",
        "Retained skin loading is bounded before PPE and absorption are applied; excess mass "
        "is treated as runoff or non-retained contact.",
        "PPE is represented as a residual penetration factor, with a bounded breakthrough-lag "
        "profile applied when barrier material and contact duration are available.",
        "Absorption is driven by bounded physical-form, contact-pattern, duration, and "
        "skin-condition modifiers unless the caller overrides it explicitly.",
        "When vapor pressure and contact duration are available, a bounded evaporation-"
        "competition term can further suppress effective dermal absorption.",
    ]

    resolved_population = population_profile
    if resolved_population is not None and body_weight is not None:
        resolved_population = resolved_population.model_copy(update={"body_weight_kg": body_weight})

    result = WorkerDermalAbsorbedDoseExecutionResult(
        supported_by_adapter=True,
        ready_for_execution=ready_for_execution,
        manual_review_required=manual_review_required,
        resolved_adapter=ingest_result.resolved_adapter,
        target_model_family=adapter_request.target_model_family,
        chemical_id=chemical_id,
        chemical_name=chemical_name,
        external_dose=external_dose,
        absorbed_dose=absorbed_dose,
        product_use_profile=product_profile,
        population_profile=resolved_population,
        task_context=task_context,
        chemical_context=chemical_context,
        dermal_task_envelope=envelope,
        execution_overrides=overrides,
        route_metrics=route_metrics,
        assumptions=assumptions,
        quality_flags=quality_flags,
        limitations=limitations,
        provenance=_execution_provenance(registry, generated_at=generated_at),
        fit_for_purpose=fit_for_purpose,
        tier_semantics=tier_semantics,
        validation_summary=None,
        interpretation_notes=interpretation_notes,
    )
    return result.model_copy(
        update={"validation_summary": _build_worker_dermal_validation_summary(result)},
        deep=True,
    )
