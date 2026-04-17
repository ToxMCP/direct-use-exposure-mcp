"""Worker inhalation Tier 2 bridge models and export helpers."""

from __future__ import annotations

import csv
import json
import math
from datetime import UTC, datetime
from enum import StrEnum
from io import StringIO
from typing import Literal

from pydantic import Field, ValidationError, model_validator

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
    ExposureScenario,
    FitForPurpose,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    LimitationNote,
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
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_screening_scenario
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine
from exposure_scenario_mcp.tier1_inhalation_profiles import Tier1InhalationProfileRegistry
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.worker_routing import route_worker_task

WORKER_TIER2_GUIDANCE_RESOURCE = "docs://worker-tier2-bridge-guide"
WORKER_ART_ADAPTER_GUIDANCE_RESOURCE = "docs://worker-art-adapter-guide"
WORKER_ART_EXECUTION_GUIDANCE_RESOURCE = "docs://worker-art-execution-guide"
WORKER_ART_EXTERNAL_EXCHANGE_GUIDANCE_RESOURCE = "docs://worker-art-external-exchange-guide"
WORKER_ART_TEMPLATE_CATALOG_VERSION = "2026.04.07.v1"
WORKER_INHALATION_BENCHMARK_CASE_ID = "worker_inhalation_janitorial_trigger_spray_execution"
WORKER_INHALATION_HANDHELD_BENCHMARK_CASE_ID = (
    "worker_inhalation_handheld_biocidal_trigger_spray_execution"
)
WORKER_INHALATION_HANDHELD_EXTERNAL_CHECK_ID = (
    "worker_biocidal_handheld_trigger_spray_concentration_2023"
)
WORKER_INHALATION_PROFESSIONAL_CLEANING_BENCHMARK_CASE_ID = (
    "worker_inhalation_professional_surface_disinfectant_execution"
)
WORKER_INHALATION_PROFESSIONAL_CLEANING_EXTERNAL_CHECK_ID = (
    "worker_biocidal_professional_cleaning_concentration_2023"
)
WORKER_BENCHMARK_REL_TOLERANCE = 0.05


class WorkerTier2ModelFamily(StrEnum):
    ART = "art"
    STOFFENMANAGER = "stoffenmanager"


class WorkerArtTemplateAlignmentStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIAL = "partial"
    HEURISTIC = "heuristic"
    NONE = "none"


class WorkerVentilationContext(StrEnum):
    UNKNOWN = "unknown"
    GENERAL_VENTILATION = "general_ventilation"
    ENHANCED_GENERAL_VENTILATION = "enhanced_general_ventilation"
    PROFESSIONAL_CLEANING = "professional_cleaning"
    SURFACE_DISINFECTION = "surface_disinfection"
    LOCAL_EXHAUST = "local_exhaust"
    ENCLOSED_PROCESS = "enclosed_process"
    OUTDOOR = "outdoor"


class WorkerTaskIntensity(StrEnum):
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


class WorkerArtArtifactAdapterId(StrEnum):
    AUTO_DETECT = "auto_detect"
    RESULT_SUMMARY_JSON_V1 = "art_worker_result_summary_json_v1"
    EXECUTION_REPORT_JSON_V1 = "art_worker_execution_report_json_v1"
    RESULT_SUMMARY_CSV_WIDE_V1 = "art_worker_result_summary_csv_wide_v1"
    RESULT_SUMMARY_CSV_KEY_VALUE_V1 = "art_worker_result_summary_csv_key_value_v1"
    RESULT_SUMMARY_CSV_SEMICOLON_V1 = "art_worker_result_summary_csv_semicolon_v1"


class WorkerInhalationTier2TaskContext(StrictModel):
    schema_version: Literal["workerInhalationTier2TaskContext.v1"] = (
        "workerInhalationTier2TaskContext.v1"
    )
    task_description: str = Field(..., description="Short description of the workplace task.")
    workplace_setting: str | None = Field(
        default=None,
        description="Short workplace-setting label such as janitorial closet or production line.",
    )
    task_duration_hours: float | None = Field(
        default=None,
        description="Task duration relevant to the future Tier 2 worker model.",
        gt=0.0,
    )
    task_intensity: WorkerTaskIntensity | None = Field(
        default=None,
        description=(
            "Optional task-intensity class used to apply a bounded inhalation-rate "
            "adjustment in worker execution."
        ),
    )
    ventilation_context: WorkerVentilationContext = Field(
        default=WorkerVentilationContext.UNKNOWN,
        description="Ventilation/control state declared for the worker task.",
    )
    local_controls: list[str] = Field(
        default_factory=list,
        description="Engineering or administrative controls explicitly present during the task.",
    )
    lev_family: str | None = Field(
        default=None,
        alias="levFamily",
        description=(
            "Optional explicit LEV or hood family such as slot_hood, canopy_hood, "
            "downdraft_booth, or capture_nozzle."
        ),
    )
    hood_face_velocity_m_per_s: float | None = Field(
        default=None,
        alias="hoodFaceVelocityMPerS",
        description=(
            "Optional measured or declared hood-face/capture velocity in m/s used for "
            "bounded worker capture refinements."
        ),
        ge=0.0,
    )
    respiratory_protection: str | None = Field(
        default=None,
        description="Respiratory protection state if explicitly known.",
    )
    emission_descriptor: str | None = Field(
        default=None,
        description="Short free-text description of the emitted mist, vapor, or aerosol context.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional worker-task notes preserved for adapter review.",
    )


class ExportWorkerInhalationTier2BridgeRequest(StrictModel):
    schema_version: Literal["exportWorkerInhalationTier2BridgeRequest.v1"] = (
        "exportWorkerInhalationTier2BridgeRequest.v1"
    )
    base_request: InhalationScenarioRequest | InhalationTier1ScenarioRequest = Field(
        ...,
        alias="baseRequest",
        description="Worker inhalation request to convert into a Tier 2 bridge package.",
    )
    target_model_family: WorkerTier2ModelFamily = Field(
        default=WorkerTier2ModelFamily.ART,
        alias="targetModelFamily",
        description="Preferred future occupational model family for the handoff.",
    )
    task_description: str = Field(
        default="worker inhalation task requiring Tier 2 refinement",
        alias="taskDescription",
        description="Short description of the occupational inhalation task.",
    )
    workplace_setting: str | None = Field(
        default=None,
        alias="workplaceSetting",
        description="Short workplace-setting label for the future adapter.",
    )
    task_duration_hours: float | None = Field(
        default=None,
        alias="taskDurationHours",
        description="Task duration for the Tier 2 bridge when different from event duration.",
        gt=0.0,
    )
    task_intensity: WorkerTaskIntensity | None = Field(
        default=None,
        alias="taskIntensity",
        description=(
            "Optional task-intensity class used to apply a bounded inhalation-rate "
            "adjustment in worker execution."
        ),
    )
    ventilation_context: WorkerVentilationContext = Field(
        default=WorkerVentilationContext.UNKNOWN,
        alias="ventilationContext",
        description="Ventilation or control state provided for the worker task.",
    )
    local_controls: list[str] = Field(
        default_factory=list,
        alias="localControls",
        description="Engineering or administrative controls present during the task.",
    )
    lev_family: str | None = Field(
        default=None,
        alias="levFamily",
        description=(
            "Optional explicit LEV or hood family such as slot_hood, canopy_hood, "
            "downdraft_booth, or capture_nozzle."
        ),
    )
    hood_face_velocity_m_per_s: float | None = Field(
        default=None,
        alias="hoodFaceVelocityMPerS",
        description=(
            "Optional measured or declared hood-face/capture velocity in m/s used for "
            "bounded worker capture refinements."
        ),
        ge=0.0,
    )
    respiratory_protection: str | None = Field(
        default=None,
        alias="respiratoryProtection",
        description="Respiratory protection state if known.",
    )
    emission_descriptor: str | None = Field(
        default=None,
        alias="emissionDescriptor",
        description="Free-text description of the worker emission context.",
    )
    context_of_use: str = Field(
        default="worker-tier2-bridge",
        alias="contextOfUse",
        description="Downstream orchestration context for the bridge package.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional worker bridge notes preserved in taskContext.",
    )

    @model_validator(mode="after")
    def validate_inhalation_scope(self) -> ExportWorkerInhalationTier2BridgeRequest:
        if self.base_request.route != Route.INHALATION:
            raise ValueError("Worker Tier 2 bridge export requires route='inhalation'.")
        return self


class WorkerInhalationTier2CompatibilityReport(StrictModel):
    schema_version: Literal["workerInhalationTier2CompatibilityReport.v1"] = (
        "workerInhalationTier2CompatibilityReport.v1"
    )
    source_request_schema: str = Field(
        ...,
        alias="sourceRequestSchema",
        description="Schema version of the source inhalation request.",
    )
    target_model_family: WorkerTier2ModelFamily = Field(
        ...,
        alias="targetModelFamily",
        description="Future worker-model family targeted by the bridge.",
    )
    route: Route = Field(default=Route.INHALATION, description="Route represented by the bridge.")
    worker_detected: bool = Field(
        ...,
        alias="workerDetected",
        description="Whether worker context was detected from the population profile.",
    )
    ready_for_adapter: bool = Field(
        ...,
        alias="readyForAdapter",
        description="Whether the bridge carries the minimum inputs for a future adapter handoff.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        alias="missingFields",
        description="Adapter-facing fields still missing from the bridge package.",
    )
    issues: list[LimitationNote] = Field(
        default_factory=list,
        description="Warnings or blockers attached to the bridge readiness decision.",
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        alias="recommendedNextSteps",
        description="Short next-step guidance for the downstream orchestrator.",
    )


class WorkerInhalationTier2AdapterRequest(StrictModel):
    schema_version: Literal["workerInhalationTier2AdapterRequest.v1"] = (
        "workerInhalationTier2AdapterRequest.v1"
    )
    target_adapter: str = Field(
        default="future_worker_exposure_adapter",
        alias="targetAdapter",
        description="Target adapter boundary for the future occupational model.",
    )
    target_model_family: WorkerTier2ModelFamily = Field(
        ...,
        alias="targetModelFamily",
        description="Future occupational model family requested by the caller.",
    )
    source_module: str = Field(
        default="exposure-scenario-mcp",
        alias="sourceModule",
        description="Source MCP that created the bridge package.",
    )
    context_of_use: str = Field(
        ...,
        alias="contextOfUse",
        description="Downstream orchestration context for the bridge payload.",
    )
    chemical_identity: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="chemicalIdentity",
        description="Chemical identity block for the future worker adapter.",
    )
    task_context: WorkerInhalationTier2TaskContext = Field(
        ...,
        alias="taskContext",
        description="Typed worker-task context for Tier 2 refinement.",
    )
    exposure_inputs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="exposureInputs",
        description="Normalized inhalation exposure inputs preserved for the future adapter.",
    )
    supporting_handoffs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="supportingHandoffs",
        description="Source request and routing context preserved alongside the adapter payload.",
    )
    guidance_resource: str = Field(
        default=WORKER_TIER2_GUIDANCE_RESOURCE,
        alias="guidanceResource",
        description="Worker Tier 2 guide that explains how to use the bridge.",
    )


class WorkerInhalationTier2AdapterToolCall(StrictModel):
    schema_version: Literal["workerInhalationTier2AdapterToolCall.v1"] = (
        "workerInhalationTier2AdapterToolCall.v1"
    )
    tool_name: str = Field(
        default="worker_ingest_inhalation_tier2_task",
        alias="toolName",
        description="Future tool name that could consume the adapter request payload.",
    )
    arguments: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        description="Arguments that should be passed to the future worker adapter.",
    )


class WorkerInhalationTier2BridgePackage(StrictModel):
    schema_version: Literal["workerInhalationTier2BridgePackage.v1"] = (
        "workerInhalationTier2BridgePackage.v1"
    )
    routing_decision: dict[str, ScalarValue | dict | list] = Field(
        ...,
        alias="routingDecision",
        description="Worker routing decision preserved inside the bridge package.",
    )
    adapter_request: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        alias="adapterRequest",
        description="Normalized future adapter payload.",
    )
    tool_call: WorkerInhalationTier2AdapterToolCall = Field(
        ...,
        alias="toolCall",
        description="Future adapter tool-call envelope.",
    )
    compatibility_report: WorkerInhalationTier2CompatibilityReport = Field(
        ...,
        alias="compatibilityReport",
        description="Readiness and missing-input report for the worker Tier 2 bridge.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        alias="qualityFlags",
        description="Bridge-level warnings and status flags.",
    )
    provenance: ProvenanceBundle = Field(..., description="Bridge-package provenance.")


class WorkerInhalationArtTaskEnvelope(StrictModel):
    schema_version: Literal["workerInhalationArtTaskEnvelope.v1"] = (
        "workerInhalationArtTaskEnvelope.v1"
    )
    adapter_name: Literal["art_worker_inhalation_adapter"] = Field(
        default="art_worker_inhalation_adapter",
        alias="adapterName",
        description="Bounded ART-side adapter identity for worker inhalation intake.",
    )
    adapter_version: str = Field(
        default="0.1.0",
        alias="adapterVersion",
        description="Version of the ART-side adapter boundary implemented here.",
    )
    activity_class: str = Field(
        ...,
        alias="activityClass",
        description="ART-aligned task activity label derived from the source request.",
    )
    emission_profile: str = Field(
        ...,
        alias="emissionProfile",
        description="Short emission-profile label derived from task and form semantics.",
    )
    control_profile: str = Field(
        ...,
        alias="controlProfile",
        description="Short control-profile label derived from ventilation and local controls.",
    )
    determinant_template_match: WorkerArtDeterminantTemplateMatch = Field(
        ...,
        alias="determinantTemplateMatch",
        description="Matched packaged determinant template carried into the ART intake.",
    )
    task_summary: list[str] = Field(
        default_factory=list,
        alias="taskSummary",
        description="Short human-readable summary of the derived ART intake mapping.",
    )
    art_inputs: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="artInputs",
        description="Normalized ART-side input object ready for downstream adapter execution.",
    )
    screening_handoff_summary: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="screeningHandoffSummary",
        description="Preserved screening and worker-routing context carried into the adapter.",
    )
    guidance_resource: str = Field(
        default=WORKER_ART_ADAPTER_GUIDANCE_RESOURCE,
        alias="guidanceResource",
        description="Guide that explains how the ART adapter intake should be interpreted.",
    )


class WorkerInhalationTier2AdapterIngestResult(StrictModel):
    schema_version: Literal["workerInhalationTier2AdapterIngestResult.v1"] = (
        "workerInhalationTier2AdapterIngestResult.v1"
    )
    ingest_tool_name: Literal["worker_ingest_inhalation_tier2_task"] = Field(
        default="worker_ingest_inhalation_tier2_task",
        alias="ingestToolName",
        description="Tool that consumed the worker Tier 2 adapter request.",
    )
    target_model_family: WorkerTier2ModelFamily = Field(
        ...,
        alias="targetModelFamily",
        description="Requested worker Tier 2 model family after ingest.",
    )
    resolved_adapter: str | None = Field(
        default=None,
        alias="resolvedAdapter",
        description="Concrete adapter boundary selected by the ingest step.",
    )
    supported_by_adapter: bool = Field(
        ...,
        alias="supportedByAdapter",
        description="Whether the current ingest implementation supports the requested family.",
    )
    ready_for_adapter_execution: bool = Field(
        ...,
        alias="readyForAdapterExecution",
        description="Whether the adapter payload is complete enough for downstream execution.",
    )
    manual_review_required: bool = Field(
        ...,
        alias="manualReviewRequired",
        description="Whether a reviewer still needs to complete or resolve intake gaps.",
    )
    missing_adapter_fields: list[str] = Field(
        default_factory=list,
        alias="missingAdapterFields",
        description="ART-side intake fields that remain missing or underspecified.",
    )
    art_task_envelope: WorkerInhalationArtTaskEnvelope | None = Field(
        default=None,
        alias="artTaskEnvelope",
        description="ART-aligned normalized intake envelope when the family is supported.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        alias="qualityFlags",
        description="Adapter-ingest status flags and mapping warnings.",
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list,
        description="Boundaries and review notes attached to the ingest result.",
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        alias="recommendedNextSteps",
        description="Short downstream actions for the ART-side execution path.",
    )
    provenance: ProvenanceBundle = Field(..., description="Adapter-ingest provenance.")


class WorkerInhalationTier2ExecutionOverrides(StrictModel):
    schema_version: Literal["workerInhalationTier2ExecutionOverrides.v1"] = (
        "workerInhalationTier2ExecutionOverrides.v1"
    )
    control_factor: float | None = Field(default=None, alias="controlFactor", ge=0.0, le=1.0)
    respiratory_protection_factor: float | None = Field(
        default=None,
        alias="respiratoryProtectionFactor",
        ge=0.0,
        le=1.0,
    )
    vapor_release_fraction: float | None = Field(
        default=None,
        alias="vaporReleaseFraction",
        ge=0.0,
        le=1.0,
    )


class ExecuteWorkerInhalationTier2Request(StrictModel):
    schema_version: Literal["executeWorkerInhalationTier2Request.v1"] = (
        "executeWorkerInhalationTier2Request.v1"
    )
    adapter_request: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    execution_overrides: WorkerInhalationTier2ExecutionOverrides | None = Field(
        default=None,
        alias="executionOverrides",
    )
    context_of_use: str = Field(default="worker-art-execution", alias="contextOfUse")


class WorkerArtExternalArtifact(StrictModel):
    schema_version: Literal["workerArtExternalArtifact.v1"] = "workerArtExternalArtifact.v1"
    label: str = Field(..., description="Short label for the external ART-side artifact.")
    locator: str = Field(..., description="URL, file path, or logical locator for the artifact.")
    media_type: str | None = Field(default=None, alias="mediaType")
    adapter_hint: WorkerArtArtifactAdapterId | None = Field(
        default=None,
        alias="adapterHint",
        description=(
            "Optional explicit adapter hint when the client knows which external ART report "
            "format this artifact uses."
        ),
    )
    content_text: str | None = Field(
        default=None,
        alias="contentText",
        description=(
            "Optional inline text payload preserved with the artifact. JSON content can be "
            "parsed directly during result import when no normalized resultPayload is supplied."
        ),
    )
    content_json: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="contentJson",
        description=(
            "Optional structured artifact payload preserved directly on the artifact. This is "
            "the preferred way to carry a real external runner summary back into the MCP."
        ),
    )
    note: str | None = None


class WorkerArtExternalExecutionResult(StrictModel):
    schema_version: Literal["workerArtExternalExecutionResult.v1"] = (
        "workerArtExternalExecutionResult.v1"
    )
    source_system: str = Field(default="ART", alias="sourceSystem")
    source_run_id: str | None = Field(default=None, alias="sourceRunId")
    model_version: str | None = Field(default=None, alias="modelVersion")
    result_status: Literal["completed", "partial", "failed"] = Field(
        default="completed",
        alias="resultStatus",
    )
    task_duration_hours: float | None = Field(
        default=None,
        alias="taskDurationHours",
        gt=0.0,
    )
    breathing_zone_concentration_mg_per_m3: float | None = Field(
        default=None,
        alias="breathingZoneConcentrationMgPerM3",
        ge=0.0,
    )
    inhaled_mass_mg_per_day: float | None = Field(
        default=None,
        alias="inhaledMassMgPerDay",
        ge=0.0,
    )
    normalized_external_dose_mg_per_kg_day: float | None = Field(
        default=None,
        alias="normalizedExternalDoseMgPerKgDay",
        ge=0.0,
    )
    determinant_snapshot: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="determinantSnapshot",
    )
    result_payload: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="resultPayload",
        description=(
            "Structured external ART-side result summary as emitted by a real runner or "
            "adapter. When provided, the import path can derive missing normalized fields "
            "directly from this payload and cross-check explicit summary metrics."
        ),
    )
    quality_notes: list[str] = Field(default_factory=list, alias="qualityNotes")
    raw_artifacts: list[WorkerArtExternalArtifact] = Field(
        default_factory=list,
        alias="rawArtifacts",
    )

    @model_validator(mode="after")
    def validate_metric_presence(self) -> WorkerArtExternalExecutionResult:
        if self.result_status == "failed":
            return self
        if all(
            value is None
            for value in (
                self.breathing_zone_concentration_mg_per_m3,
                self.inhaled_mass_mg_per_day,
                self.normalized_external_dose_mg_per_kg_day,
            )
        ) and not self.result_payload and not any(
            artifact.content_json or (artifact.content_text and artifact.content_text.strip())
            for artifact in self.raw_artifacts
        ):
            raise ValueError(
                "External ART execution results must include at least one concentration, "
                "mass, normalized-dose, structured resultPayload metric, or inline raw-artifact "
                "content unless resultStatus='failed'."
            )
        return self


class ExportWorkerArtExecutionPackageRequest(StrictModel):
    schema_version: Literal["exportWorkerArtExecutionPackageRequest.v1"] = (
        "exportWorkerArtExecutionPackageRequest.v1"
    )
    adapter_request: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    context_of_use: str = Field(
        default="worker-art-external-exchange",
        alias="contextOfUse",
    )


class WorkerArtExternalResultImportToolCall(StrictModel):
    schema_version: Literal["workerArtExternalResultImportToolCall.v1"] = (
        "workerArtExternalResultImportToolCall.v1"
    )
    tool_name: Literal["worker_import_inhalation_art_execution_result"] = Field(
        default="worker_import_inhalation_art_execution_result",
        alias="toolName",
    )
    argument_template: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="argumentTemplate",
    )


class WorkerArtExternalExecutionPackage(StrictModel):
    schema_version: Literal["workerArtExternalExecutionPackage.v1"] = (
        "workerArtExternalExecutionPackage.v1"
    )
    target_model_family: WorkerTier2ModelFamily = Field(..., alias="targetModelFamily")
    resolved_adapter: str | None = Field(default=None, alias="resolvedAdapter")
    ready_for_external_execution: bool = Field(..., alias="readyForExternalExecution")
    manual_review_required: bool = Field(..., alias="manualReviewRequired")
    adapter_request: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    art_task_envelope: WorkerInhalationArtTaskEnvelope | None = Field(
        default=None,
        alias="artTaskEnvelope",
    )
    external_execution_payload: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="externalExecutionPayload",
    )
    result_import_tool_call: WorkerArtExternalResultImportToolCall = Field(
        ...,
        alias="resultImportToolCall",
    )
    quality_flags: list[QualityFlag] = Field(default_factory=list, alias="qualityFlags")
    limitations: list[LimitationNote] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        alias="recommendedNextSteps",
    )
    provenance: ProvenanceBundle


class ImportWorkerArtExecutionResultRequest(StrictModel):
    schema_version: Literal["importWorkerArtExecutionResultRequest.v1"] = (
        "importWorkerArtExecutionResultRequest.v1"
    )
    adapter_request: WorkerInhalationTier2AdapterRequest = Field(
        ...,
        alias="adapterRequest",
    )
    external_result: WorkerArtExternalExecutionResult = Field(
        ...,
        alias="externalResult",
    )
    context_of_use: str = Field(
        default="worker-art-external-import",
        alias="contextOfUse",
    )


class WorkerInhalationTier2ExecutionResult(StrictModel):
    schema_version: Literal["workerInhalationTier2ExecutionResult.v1"] = (
        "workerInhalationTier2ExecutionResult.v1"
    )
    supported_by_adapter: bool = Field(..., alias="supportedByAdapter")
    ready_for_execution: bool = Field(..., alias="readyForExecution")
    manual_review_required: bool = Field(..., alias="manualReviewRequired")
    resolved_adapter: str | None = Field(default=None, alias="resolvedAdapter")
    target_model_family: WorkerTier2ModelFamily = Field(..., alias="targetModelFamily")
    chemical_id: str = Field(..., alias="chemicalId")
    chemical_name: str | None = Field(default=None, alias="chemicalName")
    route: Route = Field(default=Route.INHALATION)
    scenario_class: ScenarioClass = Field(default=ScenarioClass.REFINED, alias="scenarioClass")
    baseline_dose: ScenarioDose | None = Field(default=None, alias="baselineDose")
    external_dose: ScenarioDose | None = Field(default=None, alias="externalDose")
    product_use_profile: ProductUseProfile | None = Field(
        default=None,
        alias="productUseProfile",
    )
    population_profile: PopulationProfile | None = Field(
        default=None,
        alias="populationProfile",
    )
    task_context: WorkerInhalationTier2TaskContext = Field(..., alias="taskContext")
    art_task_envelope: WorkerInhalationArtTaskEnvelope | None = Field(
        default=None,
        alias="artTaskEnvelope",
    )
    execution_overrides: WorkerInhalationTier2ExecutionOverrides | None = Field(
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


class WorkerArtDeterminantTemplateMatch(StrictModel):
    schema_version: Literal["workerArtDeterminantTemplateMatch.v1"] = (
        "workerArtDeterminantTemplateMatch.v1"
    )
    template_catalog_version: str = Field(
        default=WORKER_ART_TEMPLATE_CATALOG_VERSION,
        alias="templateCatalogVersion",
        description="Version of the packaged ART determinant-template catalog.",
    )
    template_id: str | None = Field(
        default=None,
        alias="templateId",
        description="Matched determinant-template identifier, if any.",
    )
    template_label: str | None = Field(
        default=None,
        alias="templateLabel",
        description="Human-readable matched determinant-template label, if any.",
    )
    alignment_status: WorkerArtTemplateAlignmentStatus = Field(
        ...,
        alias="alignmentStatus",
        description="How strongly the current worker task aligns with the packaged template.",
    )
    match_score: float = Field(
        ...,
        alias="matchScore",
        description="Normalized match score for the selected determinant template.",
        ge=0.0,
        le=1.0,
    )
    match_basis: list[str] = Field(
        default_factory=list,
        alias="matchBasis",
        description="Short statements describing why the template matched.",
    )
    determinant_recommendations: dict[str, ScalarValue | dict | list] = Field(
        default_factory=dict,
        alias="determinantRecommendations",
        description="Packaged determinant recommendations for downstream ART-side execution.",
    )
    source_basis: list[str] = Field(
        default_factory=list,
        alias="sourceBasis",
        description="Template-pack basis preserved with the matched determinant suggestions.",
    )
    review_notes: list[str] = Field(
        default_factory=list,
        alias="reviewNotes",
        description="Review notes attached to the template match and remaining gaps.",
    )


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _contains_any_token(value: str | None, tokens: tuple[str, ...]) -> bool:
    normalized = _normalized_text(value)
    return any(token in normalized for token in tokens)


def _normalized_scalar_text(value: ScalarValue | object) -> str:
    return _normalized_text(value if isinstance(value, str) else None)


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


def _artifact_content_dict(
    artifact: WorkerArtExternalArtifact,
) -> tuple[
    dict[str, ScalarValue | dict | list],
    WorkerArtArtifactAdapterId | None,
]:
    explicit_hint = artifact.adapter_hint
    raw_payload: dict[str, ScalarValue | dict | list] = {}
    if artifact.content_json:
        raw_payload = artifact.content_json
    elif artifact.content_text and artifact.content_text.strip():
        media_type = _normalized_text(artifact.media_type)
        if media_type.endswith("json") or artifact.locator.lower().endswith(".json"):
            try:
                parsed = json.loads(artifact.content_text)
            except json.JSONDecodeError:
                raw_payload = {}
            else:
                if isinstance(parsed, dict):
                    raw_payload = parsed
        elif media_type.endswith("csv") or artifact.locator.lower().endswith(".csv"):
            payload, adapter_id = _artifact_csv_payload_and_adapter(
                artifact.content_text,
                explicit_hint=explicit_hint,
            )
            if payload:
                return payload, adapter_id
            raw_payload = {}

    candidate_adapters: list[WorkerArtArtifactAdapterId]
    if explicit_hint is not None and explicit_hint != WorkerArtArtifactAdapterId.AUTO_DETECT:
        candidate_adapters = [explicit_hint]
    else:
        candidate_adapters = [
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_JSON_V1,
            WorkerArtArtifactAdapterId.EXECUTION_REPORT_JSON_V1,
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_WIDE_V1,
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1,
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1,
        ]

    for adapter_id in candidate_adapters:
        payload = _artifact_payload_for_adapter(raw_payload, adapter_id=adapter_id)
        if payload:
            return payload, adapter_id
    return {}, None


def _coerce_artifact_cell(value: str) -> ScalarValue | dict | list:
    text = value.strip()
    if not text:
        return ""
    if text[0] in {"{", "["}:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return parsed
    numeric = _float_or_none(text)
    if numeric is not None:
        return numeric
    return text


def _artifact_csv_content_dict(text: str) -> dict[str, ScalarValue | dict | list]:
    payload, _ = _artifact_csv_payload_and_adapter(text, explicit_hint=None)
    return payload


def _artifact_csv_payload_and_adapter(
    text: str,
    *,
    explicit_hint: WorkerArtArtifactAdapterId | None,
) -> tuple[dict[str, ScalarValue | dict | list], WorkerArtArtifactAdapterId | None]:
    if explicit_hint == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1:
        payload = _artifact_csv_key_value_content_dict(text)
        return payload, (
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1 if payload else None
        )
    if explicit_hint == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_WIDE_V1:
        payload = _artifact_csv_wide_content_dict(text)
        return payload, (
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_WIDE_V1 if payload else None
        )
    if explicit_hint == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1:
        payload = _artifact_csv_semicolon_content_dict(text)
        return payload, (
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1 if payload else None
        )
    for adapter_id, parser in (
        (WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_WIDE_V1, _artifact_csv_wide_content_dict),
        (
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1,
            _artifact_csv_key_value_content_dict,
        ),
        (
            WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1,
            _artifact_csv_semicolon_content_dict,
        ),
    ):
        payload = parser(text)
        if payload:
            return payload, adapter_id
    return {}, None


def _artifact_csv_wide_content_dict(text: str) -> dict[str, ScalarValue | dict | list]:
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames:
        rows = list(reader)
        if len(rows) == 1:
            return {
                key: _coerce_artifact_cell(value)
                for key, value in rows[0].items()
                if key is not None and value is not None and value.strip()
            }
    return {}


def _artifact_csv_key_value_content_dict(text: str) -> dict[str, ScalarValue | dict | list]:
    key_value_rows = list(csv.reader(StringIO(text)))
    if key_value_rows:
        header = [_normalized_text(item) for item in key_value_rows[0]]
        if header[:2] == ["key", "value"]:
            payload: dict[str, ScalarValue | dict | list] = {}
            for row in key_value_rows[1:]:
                if len(row) >= 2 and row[0].strip():
                    payload[row[0].strip()] = _coerce_artifact_cell(row[1])
            return payload
    return {}


def _artifact_csv_semicolon_content_dict(text: str) -> dict[str, ScalarValue | dict | list]:
    wide_reader = csv.DictReader(StringIO(text), delimiter=";")
    if wide_reader.fieldnames:
        rows = list(wide_reader)
        if len(rows) == 1:
            return {
                key: _coerce_artifact_cell(value)
                for key, value in rows[0].items()
                if key is not None and value is not None and value.strip()
            }
    key_value_rows = list(csv.reader(StringIO(text), delimiter=";"))
    if key_value_rows:
        header = [_normalized_text(item) for item in key_value_rows[0]]
        if header[:2] == ["key", "value"]:
            payload: dict[str, ScalarValue | dict | list] = {}
            for row in key_value_rows[1:]:
                if len(row) >= 2 and row[0].strip():
                    payload[row[0].strip()] = _coerce_artifact_cell(row[1])
            return payload
    return {}


def _normalized_art_execution_report_payload(
    payload: dict[str, ScalarValue | dict | list],
) -> dict[str, ScalarValue | dict | list]:
    if payload.get("schemaVersion") != "artWorkerExecutionReport.v1":
        return {}
    run = payload.get("run")
    results = payload.get("results")
    determinants = payload.get("determinants")
    task = payload.get("task")
    if not isinstance(run, dict) or not isinstance(results, dict):
        return {}
    if not isinstance(determinants, dict):
        determinants = {}
    if not isinstance(task, dict):
        task = {}
    normalized: dict[str, ScalarValue | dict | list] = {
        "schemaVersion": "workerArtExternalResultSummary.v1",
    }
    run_id = _result_payload_text(run, "id", "runId", "sourceRunId")
    if run_id is not None:
        normalized["sourceRunId"] = run_id
    model_version = _result_payload_text(run, "modelVersion", "version")
    if model_version is not None:
        normalized["modelVersion"] = model_version
    result_status = _result_payload_text(results, "status", "resultStatus")
    if result_status is not None:
        normalized["resultStatus"] = result_status
    task_duration_hours = _result_payload_float(
        results,
        "taskDurationHours",
        "task_duration_hours",
    )
    if task_duration_hours is None:
        task_duration_hours = _result_payload_float(task, "durationHours", "taskDurationHours")
    if task_duration_hours is not None:
        normalized["taskDurationHours"] = task_duration_hours
    breathing_zone_concentration = _result_payload_float(
        results,
        "breathingZoneConcentrationMgPerM3",
        "breathing_zone_concentration_mg_per_m3",
    )
    if breathing_zone_concentration is not None:
        normalized["breathingZoneConcentrationMgPerM3"] = breathing_zone_concentration
    inhaled_mass = _result_payload_float(
        results,
        "inhaledMassMgPerDay",
        "inhaled_mass_mg_per_day",
    )
    if inhaled_mass is not None:
        normalized["inhaledMassMgPerDay"] = inhaled_mass
    normalized_dose = _result_payload_float(
        results,
        "normalizedExternalDoseMgPerKgDay",
        "normalized_external_dose_mg_per_kg_day",
    )
    if normalized_dose is not None:
        normalized["normalizedExternalDoseMgPerKgDay"] = normalized_dose
    if determinants:
        normalized["determinantSnapshot"] = determinants
    return normalized


def _artifact_payload_for_adapter(
    raw_payload: dict[str, ScalarValue | dict | list],
    *,
    adapter_id: WorkerArtArtifactAdapterId,
) -> dict[str, ScalarValue | dict | list]:
    if not raw_payload:
        return {}
    if adapter_id == WorkerArtArtifactAdapterId.RESULT_SUMMARY_JSON_V1:
        schema_version = _result_payload_text(raw_payload, "schemaVersion", "schema_version")
        has_metrics = any(
            _result_payload_float(raw_payload, key) is not None
            for key in (
                "breathingZoneConcentrationMgPerM3",
                "inhaledMassMgPerDay",
                "normalizedExternalDoseMgPerKgDay",
            )
        )
        if schema_version == "workerArtExternalResultSummary.v1" or has_metrics:
            return _result_payload_section(raw_payload)
        return {}
    if adapter_id == WorkerArtArtifactAdapterId.EXECUTION_REPORT_JSON_V1:
        return _normalized_art_execution_report_payload(raw_payload)
    if adapter_id == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_WIDE_V1:
        if {
            "sourceRunId",
            "modelVersion",
            "resultStatus",
        } & set(raw_payload):
            return raw_payload
        return {}
    if adapter_id == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1:
        normalized_keys = {_normalized_text(key) for key in raw_payload}
        if {"sourcerunid", "modelversion", "resultstatus"} & normalized_keys:
            return raw_payload
        return {}
    if adapter_id == WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1:
        normalized_keys = {_normalized_text(key) for key in raw_payload}
        if {"sourcerunid", "modelversion", "resultstatus"} & normalized_keys:
            return raw_payload
        return {}
    return {}


def _result_payload_from_artifacts(
    artifacts: list[WorkerArtExternalArtifact],
) -> tuple[
    dict[str, ScalarValue | dict | list],
    WorkerArtArtifactAdapterId | None,
    str | None,
]:
    for artifact in artifacts:
        payload, adapter_id = _artifact_content_dict(artifact)
        if not payload:
            continue
        summary = payload.get("resultSummary")
        if isinstance(summary, dict):
            return summary, adapter_id, artifact.locator
        nested = payload.get("externalResult")
        if isinstance(nested, dict):
            nested_summary = nested.get("resultSummary")
            if isinstance(nested_summary, dict):
                return nested_summary, adapter_id, artifact.locator
            return nested, adapter_id, artifact.locator
        return payload, adapter_id, artifact.locator
    return {}, None, None


def _result_payload_section(
    payload: dict[str, ScalarValue | dict | list] | None,
) -> dict[str, ScalarValue | dict | list]:
    if not payload:
        return {}
    nested = payload.get("resultSummary")
    if isinstance(nested, dict):
        return nested
    return payload


def _result_payload_text(
    payload: dict[str, ScalarValue | dict | list] | None,
    *keys: str,
) -> str | None:
    section = _result_payload_section(payload)
    for container in (section, payload or {}):
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _result_payload_float(
    payload: dict[str, ScalarValue | dict | list] | None,
    *keys: str,
) -> float | None:
    section = _result_payload_section(payload)
    for container in (section, payload or {}):
        for key in keys:
            value = _float_or_none(container.get(key))
            if value is not None:
                return value
    return None


def _result_payload_dict(
    payload: dict[str, ScalarValue | dict | list] | None,
    *keys: str,
) -> dict[str, ScalarValue | dict | list]:
    section = _result_payload_section(payload)
    for container in (section, payload or {}):
        for key in keys:
            value = container.get(key)
            if isinstance(value, dict):
                return value
    return {}


def _payload_matches_numeric(
    explicit_value: float | None,
    payload_value: float | None,
    *,
    rel_tol: float = 0.05,
) -> bool:
    if explicit_value is None or payload_value is None:
        return True
    return math.isclose(explicit_value, payload_value, rel_tol=rel_tol)


def _product_amount_unit(value: ScalarValue | object) -> ProductAmountUnit | None:
    if isinstance(value, ProductAmountUnit):
        return value
    if isinstance(value, str):
        for unit in ProductAmountUnit:
            if value.strip() == unit.value:
                return unit
    return None


def _execution_algorithm_source() -> AssumptionSourceReference:
    return AssumptionSourceReference(
        source_id="worker_art_execution_surrogate_v1",
        title="Direct-Use Exposure MCP worker ART-side execution surrogate",
        locator=WORKER_ART_EXECUTION_GUIDANCE_RESOURCE,
        version="2026.04.07.v1",
    )


def _external_art_result_source(
    external_result: WorkerArtExternalExecutionResult,
) -> AssumptionSourceReference:
    normalized_system = _normalized_text(external_result.source_system) or "art"
    payload_run_id = _result_payload_text(
        external_result.result_payload,
        "sourceRunId",
        "source_run_id",
        "runId",
    )
    primary_locator = (
        external_result.raw_artifacts[0].locator
        if external_result.raw_artifacts
        else f"run:{external_result.source_run_id or payload_run_id or 'unspecified'}"
    )
    return AssumptionSourceReference(
        source_id=f"worker_art_external_result:{normalized_system}",
        title=(
            f"External {external_result.source_system.strip() or 'ART'} worker inhalation "
            "execution result"
        ),
        locator=primary_locator,
        version=external_result.model_version or "unspecified",
    )


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


def _matches_worker_inhalation_benchmark(
    result: WorkerInhalationTier2ExecutionResult,
) -> bool:
    profile = result.product_use_profile
    overrides = result.execution_overrides
    envelope = result.art_task_envelope
    if profile is None or overrides is None or envelope is None:
        return False
    return (
        envelope.determinant_template_match.template_id
        == "janitorial_disinfectant_trigger_spray_v1"
        and profile.product_category == "disinfectant"
        and profile.application_method == "trigger_spray"
        and math.isclose(float(overrides.control_factor or 0.0), 0.7, rel_tol=1e-9)
        and math.isclose(
            float(overrides.respiratory_protection_factor or 0.0),
            0.5,
            rel_tol=1e-9,
        )
    )


def _matches_worker_inhalation_handheld_biocidal_benchmark(
    result: WorkerInhalationTier2ExecutionResult,
) -> bool:
    profile = result.product_use_profile
    overrides = result.execution_overrides
    envelope = result.art_task_envelope
    task_context = result.task_context
    if profile is None or overrides is None or envelope is None or task_context is None:
        return False
    return (
        envelope.determinant_template_match.template_id
        == "janitorial_disinfectant_trigger_spray_v1"
        and profile.product_category == "disinfectant"
        and profile.physical_form == "spray"
        and profile.application_method == "trigger_spray"
        and math.isclose(float(profile.concentration_fraction), 0.0016, rel_tol=1e-9)
        and math.isclose(float(profile.use_amount_per_event), 96.0, rel_tol=1e-9)
        and math.isclose(float(profile.room_volume_m3 or 0.0), 300.0, rel_tol=1e-9)
        and math.isclose(float(profile.exposure_duration_hours or 0.0), 2.0, rel_tol=1e-9)
        and math.isclose(float(task_context.task_duration_hours or 0.0), 2.0, rel_tol=1e-9)
        and _normalized_text(task_context.workplace_setting) == "workbench_area"
        and math.isclose(float(overrides.control_factor or 0.0), 1.0, rel_tol=1e-9)
        and math.isclose(
            float(overrides.respiratory_protection_factor or 0.0),
            1.0,
            rel_tol=1e-9,
        )
    )


def _matches_worker_inhalation_professional_cleaning_benchmark(
    result: WorkerInhalationTier2ExecutionResult,
) -> bool:
    profile = result.product_use_profile
    overrides = result.execution_overrides
    envelope = result.art_task_envelope
    task_context = result.task_context
    if profile is None or overrides is None or envelope is None or task_context is None:
        return False
    return (
        profile.product_category == "disinfectant"
        and profile.product_subtype == "professional_surface_disinfectant"
        and profile.physical_form == "spray"
        and profile.application_method == "trigger_spray"
        and math.isclose(float(profile.concentration_fraction), 0.005, rel_tol=1e-9)
        and math.isclose(float(profile.use_amount_per_event), 100.0, rel_tol=1e-9)
        and math.isclose(float(profile.room_volume_m3 or 0.0), 300.0, rel_tol=1e-9)
        and math.isclose(float(profile.exposure_duration_hours or 0.0), 2.0, rel_tol=1e-9)
        and math.isclose(float(task_context.task_duration_hours or 0.0), 2.0, rel_tol=1e-9)
        and _normalized_text(task_context.workplace_setting) == "indoor_room"
        and envelope.control_profile == "professional_cleaning_control_profile"
        and math.isclose(float(overrides.control_factor or 0.0), 0.45, rel_tol=1e-9)
        and math.isclose(
            float(overrides.respiratory_protection_factor or 0.0),
            1.0,
            rel_tol=1e-9,
        )
    )


def _append_worker_inhalation_benchmark_checks(
    result: WorkerInhalationTier2ExecutionResult,
    *,
    case_id: str,
    executed_validation_checks: list[ExecutedValidationCheck],
) -> None:
    if result.external_dose is None or result.baseline_dose is None:
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
            title=f"Worker inhalation external dose vs benchmark `{case_id}`",
            referenceDatasetId=case_id,
            status=_benchmark_status(
                result.external_dose.value,
                external_lower,
                external_upper,
            ),
            comparedMetric="normalized_worker_inhaled_dose",
            observedValue=round(result.external_dose.value, 8),
            referenceLower=round(external_lower, 8),
            referenceUpper=round(external_upper, 8),
            unit=result.external_dose.unit.value,
            note=(
                "Compares the current result against the packaged worker inhalation benchmark "
                f"`{case_id}` with a +/-5% acceptance band."
            ),
        )
    )

    baseline_expected = float(expected["baseline_dose_value"])
    baseline_lower, baseline_upper = _benchmark_bounds(baseline_expected)
    executed_validation_checks.append(
        ExecutedValidationCheck(
            checkId=f"{case_id}_baseline_dose_benchmark_2026",
            title=f"Worker inhalation baseline dose vs benchmark `{case_id}`",
            referenceDatasetId=case_id,
            status=_benchmark_status(
                result.baseline_dose.value,
                baseline_lower,
                baseline_upper,
            ),
            comparedMetric="normalized_external_dose",
            observedValue=round(result.baseline_dose.value, 8),
            referenceLower=round(baseline_lower, 8),
            referenceUpper=round(baseline_upper, 8),
            unit=result.baseline_dose.unit.value,
            note=(
                "Checks the preserved screening baseline against the packaged worker "
                f"inhalation benchmark `{case_id}`."
            ),
        )
    )

    control_adjusted = result.route_metrics.get("controlAdjustedAverageAirConcentrationMgPerM3")
    if isinstance(control_adjusted, int | float):
        expected_conc = float(
            expected["route_metrics"]["controlAdjustedAverageAirConcentrationMgPerM3"]
        )
        conc_lower, conc_upper = _benchmark_bounds(expected_conc)
        executed_validation_checks.append(
            ExecutedValidationCheck(
                checkId=f"{case_id}_control_adjusted_concentration_benchmark_2026",
                title=(
                    "Worker inhalation control-adjusted concentration vs benchmark "
                    f"`{case_id}`"
                ),
                referenceDatasetId=case_id,
                status=_benchmark_status(
                    float(control_adjusted),
                    conc_lower,
                    conc_upper,
                ),
                comparedMetric="control_adjusted_average_air_concentration_mg_per_m3",
                observedValue=round(float(control_adjusted), 8),
                referenceLower=round(conc_lower, 8),
                referenceUpper=round(conc_upper, 8),
                unit="mg/m3",
                note=(
                    "Checks the control-adjusted breathing-zone surrogate against the "
                    f"packaged worker inhalation benchmark `{case_id}`."
                ),
            )
        )


def _build_worker_inhalation_validation_summary(
    result: WorkerInhalationTier2ExecutionResult,
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
        and profile.product_category in {"disinfectant", "pest_control"}
        and profile.application_method == "trigger_spray"
    ):
        external_dataset_ids.append("worker_biocidal_spray_foam_inhalation_2023")
        evidence_readiness = ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES

    if _matches_worker_inhalation_benchmark(result):
        benchmark_case_ids.append(WORKER_INHALATION_BENCHMARK_CASE_ID)
        _append_worker_inhalation_benchmark_checks(
            result,
            case_id=WORKER_INHALATION_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )

    if _matches_worker_inhalation_handheld_biocidal_benchmark(result):
        benchmark_case_ids.append(WORKER_INHALATION_HANDHELD_BENCHMARK_CASE_ID)
        _append_worker_inhalation_benchmark_checks(
            result,
            case_id=WORKER_INHALATION_HANDHELD_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )
        control_adjusted = result.route_metrics.get(
            "controlAdjustedAverageAirConcentrationMgPerM3"
        )
        if isinstance(control_adjusted, int | float):
            reference_band = ValidationReferenceBandRegistry.load().band_for_check(
                WORKER_INHALATION_HANDHELD_EXTERNAL_CHECK_ID
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(control_adjusted)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            executed_validation_checks.append(
                ExecutedValidationCheck(
                    checkId=WORKER_INHALATION_HANDHELD_EXTERNAL_CHECK_ID,
                    title=(
                        "Small-scale handheld biocidal spray concentration vs occupational "
                        "monitoring study"
                    ),
                    referenceDatasetId="worker_biocidal_spray_foam_inhalation_2023",
                    status=status,
                    comparedMetric="control_adjusted_average_air_concentration_mg_per_m3",
                    observedValue=round(float(control_adjusted), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed control-adjusted breathing-zone concentration is compared "
                        "against the reported 9.06-61.7 ug/m3 band from the handheld BAC "
                        "spray scenarios in the 2023 occupational biocidal spray study, "
                        "converted to mg/m3."
                    ),
                )
            )
            evidence_readiness = ValidationEvidenceReadiness.EXTERNAL_PARTIAL

    if _matches_worker_inhalation_professional_cleaning_benchmark(result):
        benchmark_case_ids.append(WORKER_INHALATION_PROFESSIONAL_CLEANING_BENCHMARK_CASE_ID)
        _append_worker_inhalation_benchmark_checks(
            result,
            case_id=WORKER_INHALATION_PROFESSIONAL_CLEANING_BENCHMARK_CASE_ID,
            executed_validation_checks=executed_validation_checks,
        )
        control_adjusted = result.route_metrics.get(
            "controlAdjustedAverageAirConcentrationMgPerM3"
        )
        if isinstance(control_adjusted, int | float):
            reference_band = ValidationReferenceBandRegistry.load().band_for_check(
                WORKER_INHALATION_PROFESSIONAL_CLEANING_EXTERNAL_CHECK_ID
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(control_adjusted)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            executed_validation_checks.append(
                ExecutedValidationCheck(
                    checkId=WORKER_INHALATION_PROFESSIONAL_CLEANING_EXTERNAL_CHECK_ID,
                    title="Professional surface disinfectant concentration vs ART 1.5 calibration",
                    referenceDatasetId="worker_biocidal_professional_cleaning_2023",
                    status=status,
                    comparedMetric="control_adjusted_average_air_concentration_mg_per_m3",
                    observedValue=round(float(control_adjusted), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed control-adjusted breathing-zone concentration is compared "
                        "against the ART 1.5 calibration training-set band for professional "
                        "janitorial trigger-spraying."
                    ),
                )
            )
            evidence_readiness = ValidationEvidenceReadiness.EXTERNAL_PARTIAL

    if not benchmark_case_ids:
        benchmark_case_ids = [WORKER_INHALATION_BENCHMARK_CASE_ID]

    validation_status = (
        ValidationStatus.BENCHMARK_REGRESSION
        if benchmark_case_ids
        else ValidationStatus.VERIFICATION_ONLY
    )
    return ValidationSummary(
        validationStatus=validation_status,
        routeMechanism="worker_inhalation_control_aware_screening",
        benchmarkCaseIds=benchmark_case_ids,
        externalDatasetIds=external_dataset_ids,
        evidenceReadiness=evidence_readiness,
        heuristicAssumptionNames=heuristic_assumption_names,
        validationGapIds=[
            "worker_inhalation_external_validation_partial_only",
            "worker_art_execution_not_true_solver",
        ],
        executedValidationChecks=executed_validation_checks,
        highestSupportedUncertaintyTier=UncertaintyTier.TIER_B,
        probabilisticEnablement="blocked",
        notes=[
            "Worker inhalation validation is currently benchmark-regressed against packaged "
            "surrogate execution cases, not an external occupational solver.",
            (
                "A source-backed occupational biocidal spray/foam study is attached when the "
                "task family matches disinfectant or pest-control trigger spraying."
            ),
            (
                "Executable external concentration checks are available for small-scale handheld "
                "biocidal spray and professional surface cleaning benchmarks."
            ),
            (
                "Executable checks run only when the task matches one of the governed worker "
                "benchmark patterns."
            ),
        ],
    )


def _build_worker_inhalation_external_import_validation_summary(
    result: WorkerInhalationTier2ExecutionResult,
    external_result: WorkerArtExternalExecutionResult,
) -> ValidationSummary:
    heuristic_assumption_names = sorted(
        item.name
        for item in result.assumptions
        if (
            "heuristic" in item.source.source_id
            or item.source.source_id.startswith("benchmark_")
        )
    )
    dataset_id = (
        f"{external_result.source_system}:{external_result.source_run_id}"
        if external_result.source_run_id
        else (
            f"{external_result.source_system}:{external_result.model_version}"
            if external_result.model_version
            else external_result.source_system
        )
    )
    return ValidationSummary(
        validationStatus=ValidationStatus.EXTERNAL_VALIDATION_PARTIAL,
        routeMechanism="worker_inhalation_external_art_import",
        benchmarkCaseIds=[],
        externalDatasetIds=[dataset_id],
        evidenceReadiness=ValidationEvidenceReadiness.EXTERNAL_PARTIAL,
        heuristicAssumptionNames=heuristic_assumption_names,
        validationGapIds=["worker_inhalation_external_validation_partial_only"],
        executedValidationChecks=[],
        highestSupportedUncertaintyTier=UncertaintyTier.TIER_B,
        probabilisticEnablement="blocked",
        notes=[
            "This result was imported from an external occupational execution source rather "
            "than re-solved inside Direct-Use Exposure MCP.",
            "Review the attached rawArtifacts and any external qualityNotes before using the "
            "normalized dose downstream.",
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
    if source_kind == SourceKind.SYSTEM:
        return AssumptionGovernance(
            evidence_grade=EvidenceGrade.GRADE_3,
            evidence_basis=EvidenceBasis.DERIVED,
            default_visibility=DefaultVisibility.SILENT_TRACEABLE,
            applicability_status=ApplicabilityStatus.IN_DOMAIN,
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
            else "external_system"
            if source_kind == SourceKind.SYSTEM
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
) -> InhalationScenarioRequest | InhalationTier1ScenarioRequest | None:
    payload = supporting_handoffs.get("baseRequest")
    if not isinstance(payload, dict):
        return None
    if "sourceDistanceM" in payload or "source_distance_m" in payload:
        try:
            return InhalationTier1ScenarioRequest.model_validate(payload)
        except ValidationError:
            return None
    try:
        return InhalationScenarioRequest.model_validate(payload)
    except ValidationError:
        return None


def _control_profile_base_name(control_profile: str) -> str:
    normalized = _normalized_text(control_profile)
    return normalized.removesuffix("_with_rpe")


def _normalized_rpe_state(value: str | None) -> str:
    normalized = _normalized_text(value)
    return normalized or "none"


def _worker_task_intensity_label(task_context: WorkerInhalationTier2TaskContext) -> str | None:
    if task_context.task_intensity is None:
        return None
    return task_context.task_intensity.value


def _art_activity_class(
    params: WorkerInhalationTier2AdapterRequest,
) -> str:
    app = _normalized_scalar_text(params.exposure_inputs.get("applicationMethod"))
    form = _normalized_scalar_text(params.exposure_inputs.get("physicalForm"))
    if app == "trigger_spray":
        return "trigger_spray_surface_application"
    if app == "pump_spray":
        return "pump_spray_surface_application"
    if app == "aerosol_spray":
        return "pressurized_aerosol_application"
    if form in {"spray", "aerosol", "mist"}:
        return "spray_or_mist_inhalation_task"
    if _contains_any_token(params.task_context.emission_descriptor, ("vapor", "volatile")):
        return "vapor_generating_task"
    return "generic_inhalation_task"


def _art_emission_profile(
    params: WorkerInhalationTier2AdapterRequest,
) -> str:
    app = _normalized_scalar_text(params.exposure_inputs.get("applicationMethod"))
    form = _normalized_scalar_text(params.exposure_inputs.get("physicalForm"))
    if _contains_any_token(params.task_context.emission_descriptor, ("vapor", "volatile")):
        return "vapor_release_profile"
    if app == "aerosol_spray":
        return "pressurized_aerosol_release_profile"
    if form in {"spray", "aerosol", "mist"}:
        return "liquid_spray_mist_release_profile"
    return "generic_inhalation_release_profile"


def _art_control_profile(
    task_context: WorkerInhalationTier2TaskContext,
) -> str:
    controls = [_normalized_text(item) for item in task_context.local_controls]
    if task_context.ventilation_context == WorkerVentilationContext.ENCLOSED_PROCESS:
        base = "enclosed_process_control_profile"
    elif task_context.ventilation_context == WorkerVentilationContext.LOCAL_EXHAUST or any(
        token in control for control in controls for token in ("local_exhaust", "lev")
    ):
        base = "local_exhaust_control_profile"
    elif task_context.ventilation_context == WorkerVentilationContext.OUTDOOR:
        base = "outdoor_dilution_control_profile"
    elif (
        task_context.ventilation_context == WorkerVentilationContext.PROFESSIONAL_CLEANING
        or any(
            token in control
            for control in controls
            for token in ("professional_cleaning", "janitorial")
        )
    ):
        base = "professional_cleaning_control_profile"
    elif (
        task_context.ventilation_context == WorkerVentilationContext.SURFACE_DISINFECTION
        or any(
            token in control
            for control in controls
            for token in ("surface_disinfection", "sanitizing")
        )
    ):
        base = "surface_disinfection_control_profile"
    elif task_context.ventilation_context == WorkerVentilationContext.ENHANCED_GENERAL_VENTILATION:
        base = "enhanced_general_ventilation_control_profile"
    elif task_context.ventilation_context == WorkerVentilationContext.GENERAL_VENTILATION:
        base = "general_ventilation_control_profile"
    else:
        base = "ventilation_not_declared"

    respiratory_protection = _normalized_text(task_context.respiratory_protection)
    if respiratory_protection and respiratory_protection != "none":
        return f"{base}_with_rpe"
    return base


_ART_DETERMINANT_TEMPLATES: tuple[dict[str, object], ...] = (
    {
        "template_id": "janitorial_disinfectant_trigger_spray_v1",
        "template_label": "Janitorial Disinfectant Trigger Spray",
        "product_categories": {"disinfectant"},
        "product_subtypes": set(),
        "application_methods": {"trigger_spray"},
        "physical_forms": {"spray"},
        "workplace_tokens": {
            "janitorial",
            "cleaning",
            "housekeeping",
            "restroom",
            "custodial",
            "closet",
        },
        "activity_class": "trigger_spray_surface_application",
        "emission_profile": "liquid_spray_mist_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "janitorial_disinfectant_trigger_spray",
            "handlingPattern": "directed_surface_spray_and_wipe",
            "releaseMechanism": "short_manual_trigger_spray",
            "nearFieldOrientation": "toward_target_surface",
            "defaultExposureContext": {
                "workplaceSettingType": "indoor_service_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "worker_routing_trigger_spray_screening_bridge_v1",
        ],
    },
    {
        "template_id": "janitorial_cleaner_pump_spray_v1",
        "template_label": "Janitorial Cleaner Pump Spray",
        "product_categories": {"household_cleaner", "disinfectant"},
        "product_subtypes": set(),
        "application_methods": {"pump_spray"},
        "physical_forms": {"spray"},
        "workplace_tokens": {
            "janitorial",
            "cleaning",
            "housekeeping",
            "custodial",
            "cart",
            "restroom",
            "surface",
        },
        "activity_class": "pump_spray_surface_application",
        "emission_profile": "liquid_spray_mist_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "janitorial_cleaner_pump_spray",
            "handlingPattern": "manual_pump_surface_spray_and_wipe",
            "releaseMechanism": "manual_pump_spray",
            "nearFieldOrientation": "toward_target_surface",
            "defaultExposureContext": {
                "workplaceSettingType": "indoor_service_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "worker_pump_spray_surface_cleaner_expansion_2026",
        ],
    },
    {
        "template_id": "indoor_surface_pest_control_trigger_spray_v1",
        "template_label": "Indoor Surface Pest-Control Trigger Spray",
        "product_categories": {"pesticide", "pest_control", "biocide"},
        "product_subtypes": {
            "indoor_surface_insecticide",
            "targeted_spot_insecticide",
            "crack_and_crevice_insecticide",
        },
        "application_methods": {"trigger_spray"},
        "physical_forms": {"spray"},
        "workplace_tokens": {
            "pest",
            "vector",
            "insect",
            "crevice",
            "baseboard",
            "treatment",
        },
        "activity_class": "trigger_spray_surface_application",
        "emission_profile": "liquid_spray_mist_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "indoor_surface_pest_control_trigger_spray",
            "handlingPattern": "directed_surface_treatment",
            "releaseMechanism": "short_targeted_trigger_spray",
            "nearFieldOrientation": "directed_at_structural_surface",
            "defaultExposureContext": {
                "workplaceSettingType": "indoor_treatment_area",
                "workerProximity": "very_near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "consexpo_pest_control_subtype_bridge_2026",
        ],
    },
    {
        "template_id": "air_space_insecticide_aerosol_v1",
        "template_label": "Air-Space Insecticide Aerosol",
        "product_categories": {"pesticide", "pest_control", "biocide"},
        "product_subtypes": {"air_space_insecticide"},
        "application_methods": {"aerosol_spray"},
        "physical_forms": {"spray", "aerosol"},
        "workplace_tokens": {"fog", "space", "aerosol", "air_space", "knockdown"},
        "activity_class": "pressurized_aerosol_application",
        "emission_profile": "pressurized_aerosol_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "air_space_insecticide_aerosol",
            "handlingPattern": "room_scale_aerosol_release",
            "releaseMechanism": "pressurized_space_spray",
            "nearFieldOrientation": "whole_room_release",
            "defaultExposureContext": {
                "workplaceSettingType": "enclosed_treatment_space",
                "workerProximity": "operator_inside_room_or_doorway",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "consexpo_air_space_insecticide_bridge_2026",
        ],
    },
    {
        "template_id": "paint_coating_aerosol_spray_v1",
        "template_label": "Paint or Coating Aerosol Spray",
        "product_categories": {"paint_coating", "paint", "coating", "do_it_yourself"},
        "product_subtypes": set(),
        "application_methods": {"aerosol_spray"},
        "physical_forms": {"spray", "aerosol"},
        "workplace_tokens": {
            "paint",
            "coating",
            "lacquer",
            "primer",
            "booth",
            "finishing",
            "finish",
        },
        "activity_class": "pressurized_aerosol_application",
        "emission_profile": "pressurized_aerosol_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "paint_coating_aerosol_spray",
            "handlingPattern": "pressurized_surface_coating",
            "releaseMechanism": "pressurized_coating_aerosol",
            "nearFieldOrientation": "operator_to_target_surface_or_booth",
            "defaultExposureContext": {
                "workplaceSettingType": "coating_or_finishing_area",
                "workerProximity": "near_field_finishing_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_aerosol_expansion_2026",
        ],
    },
    {
        "template_id": "paint_coating_aerosol_spray_lev_booth_v1",
        "template_label": "Paint or Coating Aerosol Spray with Booth or LEV",
        "product_categories": {"paint_coating", "paint", "coating", "do_it_yourself"},
        "product_subtypes": set(),
        "application_methods": {"aerosol_spray"},
        "physical_forms": {"spray", "aerosol"},
        "workplace_tokens": {
            "paint",
            "coating",
            "booth",
            "finishing",
            "finish",
            "spray_booth",
        },
        "ventilation_contexts": {"local_exhaust", "enclosed_process"},
        "control_tokens": {"local_exhaust", "lev", "spray_booth", "booth"},
        "activity_class": "pressurized_aerosol_application",
        "emission_profile": "pressurized_aerosol_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "paint_coating_aerosol_spray_lev_booth",
            "handlingPattern": "pressurized_surface_coating_in_controlled_zone",
            "releaseMechanism": "pressurized_coating_aerosol",
            "nearFieldOrientation": "operator_in_booth_or_lev_capture_zone",
            "defaultExposureContext": {
                "workplaceSettingType": "spray_booth_or_controlled_finishing_area",
                "workerProximity": "near_field_finishing_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_control_context_expansion_2026",
        ],
    },
    {
        "template_id": "generic_worker_spray_mist_enhanced_ventilation_v1",
        "template_label": "Generic Worker Spray or Mist Task with Enhanced Ventilation",
        "product_categories": set(),
        "product_subtypes": set(),
        "application_methods": {"trigger_spray", "pump_spray", "aerosol_spray"},
        "physical_forms": {"spray", "aerosol", "mist"},
        "workplace_tokens": set(),
        "ventilation_contexts": {"enhanced_general_ventilation"},
        "activity_class": None,
        "emission_profile": None,
        "determinant_recommendations": {
            "artTaskFamily": "generic_worker_spray_mist_enhanced_ventilation",
            "handlingPattern": "spray_or_mist_release_with_engineered_room_ventilation",
            "releaseMechanism": "operator_generated_spray_with_high_room_dilution",
            "nearFieldOrientation": "operator_defined_with_enhanced_room_airflow",
            "defaultExposureContext": {
                "workplaceSettingType": "mechanically_ventilated_work_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_control_context_expansion_2026",
        ],
    },
    {
        "template_id": "generic_worker_spray_mist_outdoor_v1",
        "template_label": "Generic Worker Spray or Mist Task Outdoors",
        "product_categories": set(),
        "product_subtypes": set(),
        "application_methods": {"trigger_spray", "pump_spray", "aerosol_spray"},
        "physical_forms": {"spray", "aerosol", "mist"},
        "workplace_tokens": set(),
        "ventilation_contexts": {"outdoor"},
        "activity_class": None,
        "emission_profile": None,
        "determinant_recommendations": {
            "artTaskFamily": "generic_worker_spray_mist_outdoor",
            "handlingPattern": "spray_or_mist_release_in_open_air",
            "releaseMechanism": "operator_generated_spray_with_outdoor_dilution",
            "nearFieldOrientation": "operator_defined_in_open_environment",
            "defaultExposureContext": {
                "workplaceSettingType": "outdoor_service_or_application_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_control_context_expansion_2026",
        ],
    },
    {
        "template_id": "solvent_degreasing_vapor_task_v1",
        "template_label": "Solvent or Degreasing Vapor Task",
        "product_categories": {
            "solvent",
            "degreaser",
            "automotive_maintenance",
            "adhesive_sealant",
        },
        "product_subtypes": set(),
        "application_methods": set(),
        "physical_forms": {"liquid", "gel"},
        "workplace_tokens": {
            "solvent",
            "degreas",
            "vapor",
            "volatile",
            "parts",
            "washer",
            "tank",
            "wipe",
        },
        "activity_class": "vapor_generating_task",
        "emission_profile": "vapor_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "solvent_degreasing_vapor_task",
            "handlingPattern": "open_transfer_or_surface_degreasing",
            "releaseMechanism": "volatile_liquid_evaporation",
            "nearFieldOrientation": "operator_near_open_source",
            "defaultExposureContext": {
                "workplaceSettingType": "maintenance_or_parts_cleaning_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_vapor_expansion_2026",
        ],
    },
    {
        "template_id": "open_mixing_blending_vapor_task_v1",
        "template_label": "Open Mixing or Blending Vapor Task",
        "product_categories": {
            "solvent",
            "adhesive_sealant",
            "paint_coating",
            "coating",
        },
        "product_subtypes": set(),
        "application_methods": {"hand_application", "mixing", "pour_transfer"},
        "physical_forms": {"liquid", "gel"},
        "workplace_tokens": {
            "mix",
            "mixing",
            "blend",
            "blending",
            "batch",
            "kettle",
            "vessel",
            "open",
            "tank",
        },
        "activity_class": "vapor_generating_task",
        "emission_profile": "vapor_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "open_mixing_blending_vapor_task",
            "handlingPattern": "open_batch_mixing_or_blending",
            "releaseMechanism": "evaporation_from_open_mixture",
            "nearFieldOrientation": "operator_near_open_vessel",
            "defaultExposureContext": {
                "workplaceSettingType": "mixing_or_batch_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_open_mixing_expansion_2026",
        ],
    },
    {
        "template_id": "open_mixing_blending_vapor_task_controlled_v1",
        "template_label": "Open Mixing or Blending Vapor Task with LEV or Enclosure",
        "product_categories": {
            "solvent",
            "adhesive_sealant",
            "paint_coating",
            "coating",
        },
        "product_subtypes": set(),
        "application_methods": {"hand_application", "mixing", "pour_transfer"},
        "physical_forms": {"liquid", "gel"},
        "workplace_tokens": {
            "mix",
            "mixing",
            "blend",
            "blending",
            "batch",
            "kettle",
            "vessel",
            "tank",
        },
        "ventilation_contexts": {"local_exhaust", "enclosed_process"},
        "control_tokens": {"local_exhaust", "lev", "enclosed", "closed_lid", "sealed"},
        "activity_class": "vapor_generating_task",
        "emission_profile": "vapor_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "open_mixing_blending_vapor_task_controlled",
            "handlingPattern": "open_or_partially_enclosed_batch_mixing",
            "releaseMechanism": "evaporation_from_mixture_with_engineered_controls",
            "nearFieldOrientation": "operator_near_vessel_with_capture_or_enclosure",
            "defaultExposureContext": {
                "workplaceSettingType": "controlled_mixing_or_batch_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_control_context_expansion_2026",
        ],
    },
    {
        "template_id": "enclosed_pour_transfer_vapor_task_v1",
        "template_label": "Enclosed Pour or Transfer Vapor Task",
        "product_categories": {
            "solvent",
            "degreaser",
            "automotive_maintenance",
            "adhesive_sealant",
            "paint_coating",
            "coating",
        },
        "product_subtypes": set(),
        "application_methods": {"pour_transfer"},
        "physical_forms": {"liquid", "gel"},
        "workplace_tokens": {
            "pour",
            "transfer",
            "charging",
            "drum",
            "tote",
            "manifold",
            "line",
            "header",
            "vessel",
            "tank",
        },
        "ventilation_contexts": {"enclosed_process"},
        "control_tokens": {
            "enclosed",
            "sealed",
            "closed",
            "closed_lid",
            "closed_transfer",
            "hard_piped",
        },
        "activity_class": "vapor_generating_task",
        "emission_profile": "vapor_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "enclosed_pour_transfer_vapor_task",
            "handlingPattern": "closed_or_hard_piped_transfer",
            "releaseMechanism": "evaporation_during_enclosed_liquid_transfer",
            "nearFieldOrientation": "operator_near_enclosed_transfer_boundary",
            "defaultExposureContext": {
                "workplaceSettingType": "closed_transfer_or_charging_area",
                "workerProximity": "near_field_operator",
            },
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "exposure_platform_worker_control_context_expansion_2026",
        ],
    },
    {
        "template_id": "generic_worker_spray_mist_v1",
        "template_label": "Generic Worker Spray or Mist Task",
        "product_categories": set(),
        "product_subtypes": set(),
        "application_methods": {"trigger_spray", "pump_spray", "aerosol_spray"},
        "physical_forms": {"spray", "aerosol", "mist"},
        "workplace_tokens": set(),
        "activity_class": "spray_or_mist_inhalation_task",
        "emission_profile": "liquid_spray_mist_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "generic_worker_spray_mist",
            "handlingPattern": "manual_spray_or_mist_release",
            "releaseMechanism": "operator_generated_spray",
            "nearFieldOrientation": "operator_defined",
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "worker_inhalation_tier2_bridge_export_v1",
        ],
    },
    {
        "template_id": "generic_worker_vapor_task_v1",
        "template_label": "Generic Worker Vapor Task",
        "product_categories": set(),
        "product_subtypes": set(),
        "application_methods": set(),
        "physical_forms": {"liquid", "gel"},
        "workplace_tokens": {"vapor", "volatile", "evaporat", "solvent", "mixing"},
        "activity_class": "vapor_generating_task",
        "emission_profile": "vapor_release_profile",
        "determinant_recommendations": {
            "artTaskFamily": "generic_worker_vapor",
            "handlingPattern": "volatile_liquid_or_mixture_handling",
            "releaseMechanism": "evaporative_source_term",
            "nearFieldOrientation": "operator_defined",
        },
        "source_basis": [
            "worker_art_template_pack_2026_v1",
            "worker_inhalation_vapor_bridge_export_v1",
        ],
    },
)


def _template_sets(key: str, template: dict[str, object]) -> set[str]:
    return set(template.get(key, set()))


def _match_art_determinant_template(
    params: WorkerInhalationTier2AdapterRequest,
) -> WorkerArtDeterminantTemplateMatch:
    category = _normalized_scalar_text(params.exposure_inputs.get("productCategory"))
    subtype = _normalized_scalar_text(params.exposure_inputs.get("productSubtype"))
    application_method = _normalized_scalar_text(params.exposure_inputs.get("applicationMethod"))
    physical_form = _normalized_scalar_text(params.exposure_inputs.get("physicalForm"))
    ventilation_context = _normalized_text(params.task_context.ventilation_context.value)
    workplace_context = " ".join(
        _normalized_text(item)
        for item in (
            params.task_context.task_description,
            params.task_context.workplace_setting,
            params.task_context.emission_descriptor,
            *params.task_context.local_controls,
        )
        if item
    )

    best_payload: WorkerArtDeterminantTemplateMatch | None = None
    best_weight = -1
    best_specificity = -1
    best_score = -1.0

    for template in _ART_DETERMINANT_TEMPLATES:
        product_categories = _template_sets("product_categories", template)
        product_subtypes = _template_sets("product_subtypes", template)
        application_methods = _template_sets("application_methods", template)
        physical_forms = _template_sets("physical_forms", template)
        workplace_tokens = _template_sets("workplace_tokens", template)
        ventilation_contexts = _template_sets("ventilation_contexts", template)
        control_tokens = _template_sets("control_tokens", template)

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

        if product_subtypes:
            possible_weight += 2
            specificity += 1
            if subtype:
                if subtype in product_subtypes:
                    matched_weight += 2
                    match_basis.append(f"productSubtype=`{subtype}` matched the template subtype.")
                else:
                    continue
            else:
                review_notes.append(
                    "productSubtype was not declared, so the template matched on the broader "
                    "product family only."
                )

        if application_methods:
            possible_weight += 3
            specificity += 1
            if application_method in application_methods:
                matched_weight += 3
                match_basis.append(
                    f"applicationMethod=`{application_method}` matched the template release mode."
                )
            else:
                continue

        if physical_forms:
            possible_weight += 2
            specificity += 1
            if physical_form in physical_forms:
                matched_weight += 2
                match_basis.append(
                    f"physicalForm=`{physical_form}` matched the template aerosol form."
                )
            else:
                continue

        workplace_hit = False
        if workplace_tokens:
            possible_weight += 2
            specificity += 1
            if any(token in workplace_context for token in workplace_tokens):
                matched_weight += 2
                workplace_hit = True
                match_basis.append("Task text or workplace setting matched the template context.")
            else:
                review_notes.append(
                    "No workplace token matched the packaged template context, so alignment "
                    "remains partial."
                )

        if ventilation_contexts:
            possible_weight += 2
            specificity += 1
            if ventilation_context in ventilation_contexts:
                matched_weight += 2
                match_basis.append(
                    f"ventilationContext=`{ventilation_context}` matched the template control "
                    "state."
                )
            else:
                continue

        if control_tokens:
            possible_weight += 2
            specificity += 1
            if any(token in workplace_context for token in control_tokens):
                matched_weight += 2
                match_basis.append(
                    "Local control or workplace text matched the template control tokens."
                )
            else:
                continue

        match_score = matched_weight / possible_weight if possible_weight else 0.0
        template_id = str(template["template_id"])
        if template_id in {"generic_worker_spray_mist_v1", "generic_worker_vapor_task_v1"}:
            alignment_status = WorkerArtTemplateAlignmentStatus.HEURISTIC
        elif (product_subtypes and not subtype) or (workplace_tokens and not workplace_hit):
            alignment_status = WorkerArtTemplateAlignmentStatus.PARTIAL
        else:
            alignment_status = WorkerArtTemplateAlignmentStatus.ALIGNED

        payload = WorkerArtDeterminantTemplateMatch(
            template_id=template_id,
            template_label=str(template["template_label"]),
            alignment_status=alignment_status,
            match_score=round(match_score, 4),
            match_basis=match_basis,
            determinant_recommendations={
                **dict(template["determinant_recommendations"]),
                **(
                    {"activityClass": str(template["activity_class"])}
                    if template.get("activity_class") is not None
                    else {}
                ),
                **(
                    {"emissionProfile": str(template["emission_profile"])}
                    if template.get("emission_profile") is not None
                    else {}
                ),
            },
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

    return WorkerArtDeterminantTemplateMatch(
        alignment_status=WorkerArtTemplateAlignmentStatus.NONE,
        match_score=0.0,
        review_notes=[
            "No packaged determinant template matched the current worker inhalation task.",
            "Proceed with manual determinant selection before downstream ART-side execution.",
        ],
    )


def _bridge_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.inhalation_tier2_bridge.v1",
        plugin_id="worker_inhalation_tier2_bridge_export",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Bridge package only; no occupational Tier 2 solver is executed here.",
            "Routing decision and source inhalation request remain preserved as "
            "supporting handoffs.",
        ],
    )


def _adapter_ingest_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.inhalation_art_adapter_ingest.v1",
        plugin_id="worker_inhalation_art_adapter_ingest",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Adapter ingest only; no ART solver or regulatory worker model is executed here.",
            "The adapter envelope preserves screening hints and worker routing context as "
            "reviewable upstream evidence.",
        ],
    )


def _execution_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.inhalation_art_execution_surrogate.v1",
        plugin_id="worker_inhalation_art_execution_surrogate",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Execution reuses the existing inhalation screening kernels and then applies "
            "bounded worker control and respiratory-protection modifiers.",
            "The current output is an ART-aligned surrogate screening estimate, not a real "
            "ART run or occupational compliance result.",
        ],
    )


def _external_exchange_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.inhalation_art_external_exchange.v1",
        plugin_id="worker_inhalation_art_external_exchange",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Exports a normalized ART-side execution payload and result-import template.",
            "No occupational solver is executed during package export.",
        ],
    )


def _external_import_provenance(
    registry: DefaultsRegistry,
    *,
    generated_at: str | None = None,
) -> ProvenanceBundle:
    return ProvenanceBundle(
        algorithm_id="worker.inhalation_art_external_import.v1",
        plugin_id="worker_inhalation_art_external_result_import",
        plugin_version="0.1.0",
        defaults_version=registry.version,
        defaults_hash_sha256=registry.sha256,
        generated_at=generated_at or datetime.now(UTC).isoformat(),
        notes=[
            "Imports a normalized external ART-side execution result back into the governed "
            "worker inhalation execution schema.",
            "The imported result is preserved alongside screening-baseline comparison fields; "
            "it is not independently re-solved inside Direct-Use Exposure MCP.",
        ],
    )


def build_worker_inhalation_tier2_bridge(
    params: ExportWorkerInhalationTier2BridgeRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerInhalationTier2BridgePackage:
    registry = registry or DefaultsRegistry.load()
    base_request = params.base_request
    task_duration_hours = (
        params.task_duration_hours or base_request.product_use_profile.exposure_duration_hours
    )
    routing_decision = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id=getattr(base_request, "chemical_id", None),
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
            code="worker_tier2_bridge_export",
            severity=Severity.INFO,
            message=(
                "Worker Tier 2 bridge package was exported for a future occupational "
                "adapter path."
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
                    "Worker Tier 2 bridge was built without explicit worker-tag detection in "
                    "the population profile."
                ),
            )
        )

    if task_duration_hours is None:
        missing_fields.append("taskDurationHours")
        issues.append(
            LimitationNote(
                code="worker_tier2_task_duration_missing",
                severity=Severity.ERROR,
                message=(
                    "Tier 2 worker handoff requires taskDurationHours or an explicit "
                    "product_use_profile.exposure_duration_hours value."
                ),
            )
        )

    if params.ventilation_context == WorkerVentilationContext.UNKNOWN:
        missing_fields.append("ventilationContext")
        issues.append(
            LimitationNote(
                code="worker_tier2_ventilation_missing",
                severity=Severity.WARNING,
                message=(
                    "Tier 2 worker handoff is stronger when ventilationContext is declared "
                    "rather than left as unknown."
                ),
            )
        )

    if params.workplace_setting is None:
        missing_fields.append("workplaceSetting")
        issues.append(
            LimitationNote(
                code="worker_tier2_workplace_setting_missing",
                severity=Severity.WARNING,
                message=(
                    "Tier 2 worker handoff is stronger when workplaceSetting is declared for "
                    "the task context."
                ),
            )
        )

    if params.emission_descriptor is None:
        missing_fields.append("emissionDescriptor")
        issues.append(
            LimitationNote(
                code="worker_tier2_emission_descriptor_missing",
                severity=Severity.WARNING,
                message=(
                    "Tier 2 worker handoff is stronger when emissionDescriptor states the "
                    "mist, vapor, or aerosol generation context."
                ),
            )
        )

    if base_request.product_use_profile.physical_form.lower() != "spray":
        quality_flags.append(
            QualityFlag(
                code="worker_tier2_bridge_non_spray",
                severity=Severity.INFO,
                message=(
                    "The current bridge is inhalation-only and most mature for spray or aerosol "
                    "tasks, but the payload was still exported because the route is inhalation."
                ),
            )
        )

    issues.append(
        LimitationNote(
            code="worker_tier2_bridge_no_solver",
            severity=Severity.WARNING,
            message=(
                "This package prepares a future occupational Tier 2 handoff only. "
                "Direct-Use Exposure MCP does not execute ART, Stoffenmanager, or another "
                "occupational Tier 2 solver."
            ),
        )
    )

    ready_for_adapter = not any(item.severity == Severity.ERROR for item in issues) and not {
        "taskDurationHours",
    } & set(missing_fields)

    task_context = WorkerInhalationTier2TaskContext(
        task_description=params.task_description,
        workplace_setting=params.workplace_setting,
        task_duration_hours=task_duration_hours,
        task_intensity=params.task_intensity,
        ventilation_context=params.ventilation_context,
        local_controls=params.local_controls,
        lev_family=params.lev_family,
        hood_face_velocity_m_per_s=params.hood_face_velocity_m_per_s,
        respiratory_protection=params.respiratory_protection,
        emission_descriptor=params.emission_descriptor,
        notes=params.notes,
    )

    exposure_inputs: dict[str, ScalarValue | dict | list] = {
        "applicationMethod": base_request.product_use_profile.application_method,
        "physicalForm": base_request.product_use_profile.physical_form,
        "productCategory": base_request.product_use_profile.product_category,
        "productSubtype": base_request.product_use_profile.product_subtype,
        "concentrationFraction": base_request.product_use_profile.concentration_fraction,
        "useAmountPerEvent": base_request.product_use_profile.use_amount_per_event,
        "useAmountUnit": base_request.product_use_profile.use_amount_unit.value,
        "useEventsPerDay": base_request.product_use_profile.use_events_per_day,
        "eventDurationHours": base_request.product_use_profile.exposure_duration_hours,
        "roomVolumeM3": base_request.product_use_profile.room_volume_m3,
        "airExchangeRatePerHour": base_request.product_use_profile.air_exchange_rate_per_hour,
        "bodyWeightKg": base_request.population_profile.body_weight_kg,
        "inhalationRateM3PerHour": base_request.population_profile.inhalation_rate_m3_per_hour,
        "region": base_request.population_profile.region,
    }
    if isinstance(base_request, InhalationTier1ScenarioRequest):
        exposure_inputs["tier1Hints"] = {
            "sourceDistanceM": base_request.source_distance_m,
            "sprayDurationSeconds": base_request.spray_duration_seconds,
            "nearFieldVolumeM3": base_request.near_field_volume_m3,
            "airflowDirectionality": base_request.airflow_directionality.value,
            "particleSizeRegime": base_request.particle_size_regime.value,
        }

    adapter_request = WorkerInhalationTier2AdapterRequest(
        target_model_family=params.target_model_family,
        context_of_use=params.context_of_use,
        chemical_identity={
            "chemicalId": base_request.chemical_id,
            "preferredName": base_request.chemical_name or base_request.chemical_id,
            "sourceModule": "exposure-scenario-mcp",
        },
        task_context=task_context,
        exposure_inputs=exposure_inputs,
        supporting_handoffs={
            "baseRequest": base_request.model_dump(mode="json", by_alias=True),
            "workerRoutingDecision": routing_decision.model_dump(mode="json", by_alias=True),
        },
    )
    compatibility_report = WorkerInhalationTier2CompatibilityReport(
        source_request_schema=base_request.schema_version,
        target_model_family=params.target_model_family,
        worker_detected=routing_decision.worker_detected,
        ready_for_adapter=ready_for_adapter,
        missing_fields=sorted(set(missing_fields)),
        issues=issues,
        recommended_next_steps=[
            "Review compatibilityReport.missingFields and fill the worker-task gaps first.",
            "Preserve adapterRequest and toolCall as the exact Tier 2 handoff payload for a "
            "future occupational adapter.",
            "Use docs://worker-tier2-bridge-guide to keep the bridge bounded as a handoff "
            "artifact rather than a solved occupational estimate.",
        ],
    )
    return WorkerInhalationTier2BridgePackage(
        routing_decision=routing_decision.model_dump(mode="json", by_alias=True),
        adapter_request=adapter_request,
        tool_call=WorkerInhalationTier2AdapterToolCall(arguments=adapter_request),
        compatibility_report=compatibility_report,
        quality_flags=quality_flags,
        provenance=_bridge_provenance(registry, generated_at=generated_at),
    )


def ingest_worker_inhalation_tier2_task(
    params: WorkerInhalationTier2AdapterRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerInhalationTier2AdapterIngestResult:
    registry = registry or DefaultsRegistry.load()
    quality_flags = [
        QualityFlag(
            code="worker_tier2_adapter_request_ingested",
            severity=Severity.INFO,
            message=(
                "Worker Tier 2 adapter request was ingested and normalized into an "
                "ART-side intake envelope."
            ),
        )
    ]
    limitations = [
        LimitationNote(
            code="worker_art_adapter_no_solver",
            severity=Severity.WARNING,
            message=(
                "This ingest step does not execute ART, simulate workplace concentrations, "
                "or produce a compliance-ready occupational estimate."
            ),
        ),
        LimitationNote(
            code="worker_art_adapter_mapping_heuristic",
            severity=Severity.WARNING,
            message=(
                "Generic Direct-Use Exposure MCP task fields are mapped into an ART-aligned "
                "intake envelope using bounded, reviewable heuristics."
            ),
        ),
    ]
    missing_fields: list[str] = []

    supported_by_adapter = params.target_model_family == WorkerTier2ModelFamily.ART
    if not supported_by_adapter:
        quality_flags.append(
            QualityFlag(
                code="worker_tier2_adapter_family_unsupported",
                severity=Severity.ERROR,
                message=(
                    "The current ingestion boundary only supports `targetModelFamily=art`. "
                    "Use the bridge package as a preserved handoff for other worker-model "
                    "families."
                ),
            )
        )
        limitations.append(
            LimitationNote(
                code="worker_tier2_adapter_family_unsupported",
                severity=Severity.ERROR,
                message=(
                    "Stoffenmanager and other worker Tier 2 families are not implemented by "
                    "this ingest step yet."
                ),
            )
        )

    preferred_name = str(params.chemical_identity.get("preferredName", "") or "").strip()
    chemical_id = str(params.chemical_identity.get("chemicalId", "") or "").strip()
    application_method = str(params.exposure_inputs.get("applicationMethod", "") or "").strip()
    physical_form = str(params.exposure_inputs.get("physicalForm", "") or "").strip()
    if not (preferred_name or chemical_id):
        missing_fields.append("chemicalIdentity.preferredName")
    if not application_method:
        missing_fields.append("exposureInputs.applicationMethod")
    if not physical_form:
        missing_fields.append("exposureInputs.physicalForm")
    if params.task_context.task_duration_hours is None:
        missing_fields.append("taskContext.taskDurationHours")
    if params.task_context.workplace_setting is None:
        missing_fields.append("taskContext.workplaceSetting")
    if params.task_context.ventilation_context == WorkerVentilationContext.UNKNOWN:
        missing_fields.append("taskContext.ventilationContext")
    if params.task_context.emission_descriptor is None:
        missing_fields.append("taskContext.emissionDescriptor")

    if not params.task_context.local_controls:
        quality_flags.append(
            QualityFlag(
                code="worker_art_adapter_local_controls_not_declared",
                severity=Severity.WARNING,
                message=(
                    "No localControls were declared in the worker task context. If controls "
                    "are absent, keep the empty list explicitly during ART-side review."
                ),
            )
        )
    if params.task_context.respiratory_protection is None:
        quality_flags.append(
            QualityFlag(
                code="worker_art_adapter_rpe_not_declared",
                severity=Severity.WARNING,
                message=(
                    "Respiratory protection was not declared. Set `none` explicitly when no "
                    "RPE is used so downstream ART-side review can distinguish missing from "
                    "negative information."
                ),
            )
        )

    tier1_hints = params.exposure_inputs.get("tier1Hints")
    if isinstance(tier1_hints, dict) and tier1_hints:
        quality_flags.append(
            QualityFlag(
                code="worker_art_adapter_screening_hints_preserved",
                severity=Severity.INFO,
                message=(
                    "Tier 1 screening geometry and spray hints were preserved as ART-side "
                    "context only; they are not treated as solved occupational determinants."
                ),
            )
        )
        limitations.append(
            LimitationNote(
                code="worker_art_adapter_screening_hints_context_only",
                severity=Severity.INFO,
                message=(
                    "Tier 1 screening hints remain contextual surrogates and should not be "
                    "confused with measured workplace determinants."
                ),
            )
        )

    template_match = _match_art_determinant_template(params)
    if template_match.alignment_status == WorkerArtTemplateAlignmentStatus.ALIGNED:
        quality_flags.append(
            QualityFlag(
                code="worker_art_template_aligned",
                severity=Severity.INFO,
                message=(
                    f"Matched packaged ART determinant template "
                    f"`{template_match.template_id}` with aligned status."
                ),
            )
        )
    elif template_match.alignment_status == WorkerArtTemplateAlignmentStatus.PARTIAL:
        quality_flags.append(
            QualityFlag(
                code="worker_art_template_partial",
                severity=Severity.WARNING,
                message=(
                    f"Matched packaged ART determinant template "
                    f"`{template_match.template_id}` only partially. Review the remaining "
                    "template review notes before downstream execution."
                ),
            )
        )
    elif template_match.alignment_status == WorkerArtTemplateAlignmentStatus.HEURISTIC:
        quality_flags.append(
            QualityFlag(
                code="worker_art_template_heuristic",
                severity=Severity.WARNING,
                message=(
                    f"Only a heuristic packaged ART determinant template "
                    f"`{template_match.template_id}` matched the worker task."
                ),
            )
        )
    else:
        quality_flags.append(
            QualityFlag(
                code="worker_art_template_missing",
                severity=Severity.WARNING,
                message=(
                    "No packaged ART determinant template matched the worker task. Manual "
                    "determinant selection is required before downstream execution."
                ),
            )
        )
    if template_match.review_notes:
        limitations.append(
            LimitationNote(
                code="worker_art_template_review_notes",
                severity=(
                    Severity.WARNING
                    if template_match.alignment_status
                    in {
                        WorkerArtTemplateAlignmentStatus.PARTIAL,
                        WorkerArtTemplateAlignmentStatus.HEURISTIC,
                        WorkerArtTemplateAlignmentStatus.NONE,
                    }
                    else Severity.INFO
                ),
                message=" ".join(template_match.review_notes),
            )
        )

    ready_for_adapter_execution = supported_by_adapter and not missing_fields
    manual_review_required = (not ready_for_adapter_execution) or any(
        flag.severity in {Severity.WARNING, Severity.ERROR} for flag in quality_flags
    )

    art_task_envelope: WorkerInhalationArtTaskEnvelope | None = None
    if supported_by_adapter:
        activity_class = str(
            template_match.determinant_recommendations.get("activityClass")
            or _art_activity_class(params)
        )
        emission_profile = str(
            template_match.determinant_recommendations.get("emissionProfile")
            or _art_emission_profile(params)
        )
        control_profile = _art_control_profile(params.task_context)
        art_inputs: dict[str, ScalarValue | dict | list] = {
            "substanceName": preferred_name or chemical_id,
            "substanceIdentifier": chemical_id or preferred_name,
            "activityClass": activity_class,
            "emissionProfile": emission_profile,
            "controlProfile": control_profile,
            "templateId": template_match.template_id,
            "templateAlignmentStatus": template_match.alignment_status.value,
            "determinantTemplateRecommendations": template_match.determinant_recommendations,
            "taskDescription": params.task_context.task_description,
            "workplaceSetting": params.task_context.workplace_setting,
            "taskDurationHours": params.task_context.task_duration_hours,
            "ventilationContext": params.task_context.ventilation_context.value,
            "localControls": params.task_context.local_controls,
            "respiratoryProtection": params.task_context.respiratory_protection,
            "emissionDescriptor": params.task_context.emission_descriptor,
            "productCategory": params.exposure_inputs.get("productCategory"),
            "productSubtype": params.exposure_inputs.get("productSubtype"),
            "applicationMethod": params.exposure_inputs.get("applicationMethod"),
            "physicalForm": params.exposure_inputs.get("physicalForm"),
            "concentrationFraction": params.exposure_inputs.get("concentrationFraction"),
            "useAmountPerEvent": params.exposure_inputs.get("useAmountPerEvent"),
            "useAmountUnit": params.exposure_inputs.get("useAmountUnit"),
            "useEventsPerDay": params.exposure_inputs.get("useEventsPerDay"),
            "eventDurationHours": params.exposure_inputs.get("eventDurationHours"),
            "roomVolumeM3": params.exposure_inputs.get("roomVolumeM3"),
            "airExchangeRatePerHour": params.exposure_inputs.get("airExchangeRatePerHour"),
            "bodyWeightKg": params.exposure_inputs.get("bodyWeightKg"),
            "inhalationRateM3PerHour": params.exposure_inputs.get("inhalationRateM3PerHour"),
            "region": params.exposure_inputs.get("region"),
        }
        if isinstance(tier1_hints, dict) and tier1_hints:
            art_inputs["tier1ScreeningHints"] = tier1_hints

        supporting_handoffs = params.supporting_handoffs
        screening_handoff_summary: dict[str, ScalarValue | dict | list] = {
            "sourceModule": params.source_module,
            "contextOfUse": params.context_of_use,
            "guidanceResource": params.guidance_resource,
        }
        worker_routing = supporting_handoffs.get("workerRoutingDecision")
        if isinstance(worker_routing, dict):
            screening_handoff_summary["workerRoutingSupportStatus"] = worker_routing.get(
                "support_status"
            )
            screening_handoff_summary["workerRoutingTargetMcp"] = worker_routing.get("target_mcp")
            screening_handoff_summary["workerRoutingNextStep"] = worker_routing.get("next_step")
        base_request = supporting_handoffs.get("baseRequest")
        if isinstance(base_request, dict):
            screening_handoff_summary["sourceRequestSchema"] = base_request.get(
                "schemaVersion"
            ) or base_request.get("schema_version")
            screening_handoff_summary["sourceRoute"] = base_request.get("route")
        screening_handoff_summary["templateCatalogVersion"] = (
            template_match.template_catalog_version
        )

        art_task_envelope = WorkerInhalationArtTaskEnvelope(
            activity_class=activity_class,
            emission_profile=emission_profile,
            control_profile=control_profile,
            determinant_template_match=template_match,
            task_summary=[
                f"Matched determinant template=`{template_match.template_id or 'none'}` with "
                f"alignmentStatus=`{template_match.alignment_status.value}`.",
                f"Mapped applicationMethod=`{application_method or 'unknown'}` and "
                f"physicalForm=`{physical_form or 'unknown'}` to activityClass=`{activity_class}`.",
                f"Mapped ventilationContext=`{params.task_context.ventilation_context.value}` and "
                f"localControls count `{len(params.task_context.local_controls)}` to "
                f"controlProfile=`{control_profile}`.",
                f"Preserved contextOfUse=`{params.context_of_use}` and sourceModule="
                f"`{params.source_module}` for downstream ART-side review.",
            ],
            art_inputs=art_inputs,
            screening_handoff_summary=screening_handoff_summary,
        )

    recommended_next_steps = [
        "Preserve the ingest result, qualityFlags, limitations, and provenance alongside the "
        "ART-side intake envelope.",
    ]
    if ready_for_adapter_execution and art_task_envelope is not None:
        recommended_next_steps.extend(
            [
                "Pass `artTaskEnvelope.artInputs` into the next ART-side adapter or execution "
                "boundary.",
                "Keep `screeningHandoffSummary` and any preserved Tier 1 hints attached as "
                "reviewable upstream evidence rather than solved ART determinants.",
            ]
        )
    else:
        recommended_next_steps.extend(
            [
                "Fill every entry in `missingAdapterFields` before attempting ART-side "
                "execution.",
                "Use docs://worker-art-adapter-guide to keep the intake bounded as a "
                "normalized handoff rather than a solved worker exposure estimate.",
            ]
        )

    return WorkerInhalationTier2AdapterIngestResult(
        target_model_family=params.target_model_family,
        resolved_adapter="art_worker_inhalation_adapter" if supported_by_adapter else None,
        supported_by_adapter=supported_by_adapter,
        ready_for_adapter_execution=ready_for_adapter_execution,
        manual_review_required=manual_review_required,
        missing_adapter_fields=sorted(set(missing_fields)),
        art_task_envelope=art_task_envelope,
        quality_flags=quality_flags,
        limitations=limitations,
        recommended_next_steps=recommended_next_steps,
        provenance=_adapter_ingest_provenance(registry, generated_at=generated_at),
    )


def export_worker_inhalation_art_execution_package(
    params: ExportWorkerArtExecutionPackageRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerArtExternalExecutionPackage:
    registry = registry or DefaultsRegistry.load()
    adapter_request = params.adapter_request
    ingest_result = ingest_worker_inhalation_tier2_task(
        adapter_request,
        registry=registry,
        generated_at=generated_at,
    )
    quality_flags = list(ingest_result.quality_flags)
    limitations = list(ingest_result.limitations)
    envelope = ingest_result.art_task_envelope
    ready_for_external_execution = (
        ingest_result.ready_for_adapter_execution and envelope is not None
    )

    external_execution_payload: dict[str, ScalarValue | dict | list] = {
        "schemaVersion": "workerArtExternalExecutionPayload.v1",
        "contextOfUse": params.context_of_use,
        "targetModelFamily": adapter_request.target_model_family.value,
        "resolvedAdapter": ingest_result.resolved_adapter,
        "guidanceResource": WORKER_ART_EXTERNAL_EXCHANGE_GUIDANCE_RESOURCE,
    }
    if envelope is not None:
        external_execution_payload.update(
            {
                "artTaskEnvelope": envelope.model_dump(mode="json", by_alias=True),
                "artInputs": envelope.art_inputs,
                "screeningHandoffSummary": envelope.screening_handoff_summary,
                "expectedResultPayloadSchemaVersion": "workerArtExternalResultSummary.v1",
                "acceptedResultPayloadKeys": [
                    "schemaVersion",
                    "sourceRunId",
                    "modelVersion",
                    "resultStatus",
                    "taskDurationHours",
                    "breathingZoneConcentrationMgPerM3",
                    "inhaledMassMgPerDay",
                    "normalizedExternalDoseMgPerKgDay",
                    "determinantSnapshot",
                ],
                "requiredResultFields": [
                    "sourceSystem",
                    "resultStatus",
                    "rawArtifacts with contentJson/contentText, or resultPayload",
                    (
                        "One of: normalizedExternalDoseMgPerKgDay, inhaledMassMgPerDay, or "
                        "breathingZoneConcentrationMgPerM3, either directly or in resultPayload"
                    ),
                ],
            }
        )

    quality_flags.append(
        QualityFlag(
            code="worker_art_external_execution_package_exported",
            severity=Severity.INFO if ready_for_external_execution else Severity.WARNING,
            message=(
                "Exported an ART-side external execution package with a result-import template."
                if ready_for_external_execution
                else "Exported an ART-side external execution package, but the payload still "
                "needs manual review before external execution."
            ),
        )
    )

    result_import_tool_call = WorkerArtExternalResultImportToolCall(
        argument_template={
            "schemaVersion": "importWorkerArtExecutionResultRequest.v1",
            "adapterRequest": adapter_request.model_dump(mode="json", by_alias=True),
            "externalResult": {
                "schemaVersion": "workerArtExternalExecutionResult.v1",
                "sourceSystem": "ART",
                "sourceRunId": "fill-in-external-run-id",
                "modelVersion": "fill-in-art-version",
                "resultStatus": "completed",
                "breathingZoneConcentrationMgPerM3": None,
                "inhaledMassMgPerDay": None,
                "normalizedExternalDoseMgPerKgDay": None,
                "determinantSnapshot": {},
                "resultPayload": {
                    "schemaVersion": "workerArtExternalResultSummary.v1",
                    "sourceRunId": "fill-in-external-run-id",
                    "modelVersion": "fill-in-art-version",
                    "resultStatus": "completed",
                    "taskDurationHours": None,
                    "breathingZoneConcentrationMgPerM3": None,
                    "inhaledMassMgPerDay": None,
                    "normalizedExternalDoseMgPerKgDay": None,
                    "determinantSnapshot": {},
                },
                "qualityNotes": [],
                "rawArtifacts": [
                    {
                        "schemaVersion": "workerArtExternalArtifact.v1",
                        "label": "ART run summary",
                        "locator": "artifact://fill-in-external-run-id/summary.json",
                        "mediaType": "application/json",
                        "contentJson": {
                            "schemaVersion": "workerArtExternalResultSummary.v1",
                            "sourceRunId": "fill-in-external-run-id",
                            "modelVersion": "fill-in-art-version",
                            "resultStatus": "completed",
                            "taskDurationHours": None,
                            "breathingZoneConcentrationMgPerM3": None,
                            "inhaledMassMgPerDay": None,
                            "normalizedExternalDoseMgPerKgDay": None,
                            "determinantSnapshot": {},
                        },
                    }
                ],
            },
            "contextOfUse": "worker-art-external-import",
        }
    )

    recommended_next_steps = [
        "Send `externalExecutionPayload.artInputs` into the external ART-side execution path.",
        "Preserve `artTaskEnvelope`, `qualityFlags`, `limitations`, and `provenance` with the "
        "external run so the result stays auditable on re-import.",
    ]
    if ready_for_external_execution:
        recommended_next_steps.append(
            "When the external run completes, call "
            "`worker_import_inhalation_art_execution_result` with the normalized result payload."
        )
    else:
        recommended_next_steps.extend(ingest_result.recommended_next_steps)

    return WorkerArtExternalExecutionPackage(
        target_model_family=adapter_request.target_model_family,
        resolved_adapter=ingest_result.resolved_adapter,
        ready_for_external_execution=ready_for_external_execution,
        manual_review_required=ingest_result.manual_review_required,
        adapter_request=adapter_request,
        art_task_envelope=envelope,
        external_execution_payload=external_execution_payload,
        result_import_tool_call=result_import_tool_call,
        quality_flags=quality_flags,
        limitations=limitations,
        recommended_next_steps=recommended_next_steps,
        provenance=_external_exchange_provenance(registry, generated_at=generated_at),
    )


def execute_worker_inhalation_tier2_task(
    params: ExecuteWorkerInhalationTier2Request,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerInhalationTier2ExecutionResult:
    registry = registry or DefaultsRegistry.load()
    adapter_request = params.adapter_request
    ingest_result = ingest_worker_inhalation_tier2_task(
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

    if not ingest_result.supported_by_adapter or ingest_result.art_task_envelope is None:
        return WorkerInhalationTier2ExecutionResult(
            supported_by_adapter=False,
            ready_for_execution=False,
            manual_review_required=True,
            resolved_adapter=None,
            target_model_family=adapter_request.target_model_family,
            chemical_id=chemical_id,
            chemical_name=chemical_name,
            task_context=adapter_request.task_context,
            art_task_envelope=None,
            execution_overrides=overrides,
            quality_flags=quality_flags,
            limitations=limitations,
            provenance=_execution_provenance(registry, generated_at=generated_at),
            fit_for_purpose=FitForPurpose(
                label="unsupported_worker_inhalation_execution",
                suitable_for=[],
                not_suitable_for=[
                    "worker inhalation surrogate execution",
                    "ART-aligned worker concentration refinement",
                ],
            ),
            tier_semantics=TierSemantics(
                tier_claimed=TierLevel.TIER_0,
                tier_earned=TierLevel.TIER_0,
                tier_rationale=(
                    "The requested worker Tier 2 model family is not executable in the current "
                    "surrogate kernel."
                ),
                assumption_checks_passed=False,
                required_caveats=[
                    "No executable worker inhalation estimate was produced because the "
                    "requested model family is unsupported."
                ],
                forbidden_interpretations=[
                    "Do not treat this response as a solved occupational inhalation result."
                ],
            ),
            validation_summary=None,
            interpretation_notes=[
                "Supported executable worker inhalation output is currently limited to the "
                "`art` family."
            ],
        )

    envelope = ingest_result.art_task_envelope
    task_context = adapter_request.task_context
    art_inputs = envelope.art_inputs
    applicability_domain = {
        "product_category": art_inputs.get("productCategory"),
        "product_subtype": art_inputs.get("productSubtype"),
        "application_method": art_inputs.get("applicationMethod"),
        "physical_form": art_inputs.get("physicalForm"),
        "activity_class": envelope.activity_class,
        "control_profile": envelope.control_profile,
    }

    baseline_scenario: ExposureScenario | None = None
    baseline_model_family: str | None = None
    baseline_average_air_concentration = None
    baseline_inhaled_mass_mg_day = None
    baseline_external_dose = None
    body_weight = None
    inhalation_rate = None
    pressurized_aerosol_volume_factor = 1.0
    pressurized_aerosol_physchem_factor = 1.0
    pressurized_aerosol_physchem_label = "generic"
    pressurized_aerosol_carrier_factor = 1.0
    pressurized_aerosol_carrier_label = "generic"
    pressurized_aerosol_formulation_factor = 1.0
    pressurized_aerosol_formulation_label = "generic"

    if base_request is None:
        limitations.append(
            LimitationNote(
                code="worker_art_execution_base_request_missing",
                severity=Severity.ERROR,
                message=(
                    "Worker inhalation execution requires the preserved baseRequest in "
                    "supportingHandoffs."
                ),
            )
        )
    elif isinstance(base_request, InhalationTier1ScenarioRequest):
        task_duration_hours = (
            task_context.task_duration_hours
            or base_request.product_use_profile.exposure_duration_hours
            or 0.0
        )
        spray_duration_hours = base_request.spray_duration_seconds / 3600.0
        if task_duration_hours < spray_duration_hours:
            quality_flags.append(
                QualityFlag(
                    code="worker_art_execution_task_duration_below_spray_duration",
                    severity=Severity.WARNING,
                    message=(
                        "taskDurationHours was shorter than sprayDurationSeconds, so the "
                        "surrogate execution used the spray duration as the minimum event "
                        "window."
                    ),
                )
            )
            task_duration_hours = spray_duration_hours
        patched_request = base_request.model_copy(
            update={
                "product_use_profile": base_request.product_use_profile.model_copy(
                    update={"exposure_duration_hours": task_duration_hours}
                )
            },
            deep=True,
        )
        baseline_scenario = build_inhalation_tier_1_screening_scenario(
            patched_request,
            registry,
            profile_registry=Tier1InhalationProfileRegistry.load(),
            generated_at=generated_at,
        )
        baseline_model_family = "tier1_nf_ff_screening"
    else:
        application_method = _normalized_scalar_text(art_inputs.get("applicationMethod"))
        if application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}:
            task_duration_hours = (
                task_context.task_duration_hours
                or base_request.product_use_profile.exposure_duration_hours
            )
            patched_request = base_request.model_copy(
                update={
                    "product_use_profile": base_request.product_use_profile.model_copy(
                        update={"exposure_duration_hours": task_duration_hours}
                    )
                },
                deep=True,
            )
            plugin_registry = PluginRegistry()
            plugin_registry.register(InhalationScreeningPlugin())
            engine = ScenarioEngine(
                registry=plugin_registry,
                defaults_registry=registry,
            )
            baseline_scenario = engine.build(patched_request)
            baseline_model_family = "tier0_room_average_screening"
        else:
            use_amount_per_event = _float_or_none(art_inputs.get("useAmountPerEvent"))
            use_amount_unit = _product_amount_unit(art_inputs.get("useAmountUnit"))
            concentration_fraction = _float_or_none(art_inputs.get("concentrationFraction"))
            use_events_per_day = _float_or_none(art_inputs.get("useEventsPerDay")) or 1.0
            room_volume_m3 = _float_or_none(art_inputs.get("roomVolumeM3"))
            air_exchange_rate = _float_or_none(art_inputs.get("airExchangeRatePerHour"))
            task_duration_hours = (
                task_context.task_duration_hours
                or _float_or_none(art_inputs.get("eventDurationHours"))
            )
            inhalation_rate = _float_or_none(art_inputs.get("inhalationRateM3PerHour"))
            body_weight = _float_or_none(art_inputs.get("bodyWeightKg"))
            product_category = _normalized_scalar_text(art_inputs.get("productCategory"))
            product_subtype = _normalized_scalar_text(art_inputs.get("productSubtype"))
            physical_form = _normalized_scalar_text(art_inputs.get("physicalForm"))

            if room_volume_m3 is None or air_exchange_rate is None or task_duration_hours is None:
                limitations.append(
                    LimitationNote(
                        code="worker_art_execution_room_context_missing",
                        severity=Severity.ERROR,
                        message=(
                            "Worker inhalation vapor surrogate requires room volume, air "
                            "exchange rate, and task duration."
                        ),
                    )
                )
            if inhalation_rate is None and population_profile is not None:
                defaults, source = registry.population_defaults(population_profile.population_group)
                inhalation_rate = defaults["inhalation_rate_m3_per_hour"]
                assumptions.append(
                    _assumption_record(
                        name="inhalation_rate_m3_per_hour",
                        value=inhalation_rate,
                        unit="m3/h",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=source,
                        rationale=(
                            "Inhalation rate defaulted from the population group because the "
                            "worker adapter payload did not carry an explicit value."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            elif inhalation_rate is not None:
                assumptions.append(
                    _assumption_record(
                        name="inhalation_rate_m3_per_hour",
                        value=inhalation_rate,
                        unit="m3/h",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Inhalation rate was carried through the worker adapter request."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if body_weight is None and population_profile is not None:
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
                            "adapter payload did not carry an explicit value."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            elif body_weight is not None:
                assumptions.append(
                    _assumption_record(
                        name="body_weight_kg",
                        value=body_weight,
                        unit="kg",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Body weight was carried through the worker adapter request."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )

            density_g_per_ml = None
            pressurized_aerosol_volume_factor = 1.0
            pressurized_aerosol_physchem_factor = 1.0
            pressurized_aerosol_physchem_label = "generic"
            pressurized_aerosol_carrier_factor = 1.0
            pressurized_aerosol_carrier_label = "generic"
            pressurized_aerosol_formulation_factor = 1.0
            pressurized_aerosol_formulation_label = "generic"
            if use_amount_unit == ProductAmountUnit.G:
                product_mass_g_event = use_amount_per_event
                if product_mass_g_event is not None:
                    assumptions.append(
                        _assumption_record(
                            name="use_amount_per_event",
                            value=use_amount_per_event,
                            unit="g/event",
                            source_kind=SourceKind.USER_INPUT,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Use amount per event was carried through the worker adapter "
                                "request."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
            else:
                density_g_per_ml = _float_or_none(
                    base_request.product_use_profile.density_g_per_ml
                    if base_request is not None
                    else None
                )
                density_defaulted = density_g_per_ml is None
                if density_g_per_ml is None:
                    density_g_per_ml, density_source = registry.default_density_g_per_ml(
                        product_category or None,
                        physical_form or None,
                        product_subtype or None,
                    )
                    assumptions.append(
                        _assumption_record(
                            name="density_g_per_ml",
                            value=density_g_per_ml,
                            unit="g/mL",
                            source_kind=SourceKind.DEFAULT_REGISTRY,
                            source=density_source,
                            rationale=(
                                "Density defaulted because the worker vapor surrogate used a "
                                "volumetric product amount without an explicit density."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                elif density_g_per_ml is not None:
                    assumptions.append(
                        _assumption_record(
                            name="density_g_per_ml",
                            value=density_g_per_ml,
                            unit="g/mL",
                            source_kind=SourceKind.USER_INPUT,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Density was carried through the preserved base request."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                if (
                    density_defaulted
                    and use_amount_per_event is not None
                    and density_g_per_ml is not None
                    and base_request is not None
                    and base_request.product_use_profile.application_method == "aerosol_spray"
                ):
                    (
                        pressurized_aerosol_volume_factor,
                        aerosol_source,
                    ) = registry.pressurized_aerosol_volume_interpretation_factor(
                        product_category or None,
                        physical_form or None,
                        product_subtype or None,
                    )
                    aerosol_physchem_adjustment = (
                        registry.pressurized_aerosol_physchem_adjustment_factor(
                            product_category or None,
                            product_subtype or None,
                            None
                            if base_request is None or base_request.physchem_context is None
                            else _float_or_none(
                                base_request.physchem_context.vapor_pressure_mmhg
                            ),
                            None
                            if base_request is None or base_request.physchem_context is None
                            else _float_or_none(
                                base_request.physchem_context.molecular_weight_g_per_mol
                            ),
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
                                    "Worker aerosol mass semantics were further adjusted with "
                                    "a bounded volatility and low-molecular-weight heuristic "
                                    "because default density and supplied physchem context "
                                    "were both active."
                                ),
                                applicability_domain=applicability_domain,
                            )
                        )
                        if pressurized_aerosol_physchem_factor < 1.0:
                            quality_flags.append(
                                QualityFlag(
                                    code=(
                                        "worker_inhalation_pressurized_aerosol_physchem_"
                                        "adjustment_defaulted"
                                    ),
                                    severity=Severity.WARNING,
                                    message=(
                                        "Worker inhalation execution further reduced "
                                        "volumetric aerosol mass with a bounded aerosol "
                                        "volatility and carrier adjustment."
                                    ),
                                )
                            )
                    aerosol_carrier_adjustment = (
                        registry.pressurized_aerosol_carrier_family_adjustment_factor(
                            base_request.product_use_profile.aerosol_carrier_family
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
                                    "Worker aerosol mass semantics were further adjusted with "
                                    "a bounded carrier-family heuristic because explicit "
                                    "aerosol carrier context was supplied."
                                ),
                                applicability_domain=applicability_domain,
                            )
                        )
                        if pressurized_aerosol_carrier_factor < 1.0:
                            quality_flags.append(
                                QualityFlag(
                                    code=(
                                        "worker_inhalation_pressurized_aerosol_carrier_"
                                        "family_adjustment_defaulted"
                                    ),
                                    severity=Severity.WARNING,
                                    message=(
                                        "Worker inhalation execution further reduced "
                                        "volumetric aerosol mass with a bounded aerosol "
                                        "carrier-family adjustment."
                                    ),
                                )
                            )
                    aerosol_formulation_adjustment = (
                        registry.pressurized_aerosol_formulation_profile_adjustment_factor(
                            product_category=product_category or None,
                            product_subtype=product_subtype or None,
                            aerosol_formulation_profile=(
                                base_request.product_use_profile.aerosol_formulation_profile
                            ),
                        )
                    )
                    if aerosol_formulation_adjustment is not None:
                        (
                            pressurized_aerosol_formulation_label,
                            pressurized_aerosol_formulation_factor,
                            aerosol_formulation_source,
                        ) = aerosol_formulation_adjustment
                        assumptions.append(
                            _assumption_record(
                                name="pressurized_aerosol_formulation_profile_adjustment_factor",
                                value=pressurized_aerosol_formulation_factor,
                                unit="fraction",
                                source_kind=SourceKind.DEFAULT_REGISTRY,
                                source=aerosol_formulation_source,
                                rationale=(
                                    "Worker aerosol mass semantics were further adjusted with "
                                    "a bounded formulation-profile heuristic because explicit "
                                    "aerosol formulation context was supplied."
                                ),
                                applicability_domain=applicability_domain,
                            )
                        )
                        if pressurized_aerosol_formulation_factor < 1.0:
                            quality_flags.append(
                                QualityFlag(
                                    code=(
                                        "worker_inhalation_pressurized_aerosol_formulation_"
                                        "profile_adjustment_defaulted"
                                    ),
                                    severity=Severity.WARNING,
                                    message=(
                                        "Worker inhalation execution further reduced "
                                        "volumetric aerosol mass with a bounded aerosol "
                                        "formulation-profile adjustment."
                                    ),
                                )
                            )
                    pressurized_aerosol_volume_factor *= pressurized_aerosol_formulation_factor
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
                                "adapter request relied on default density."
                            ),
                            applicability_domain=applicability_domain,
                        )
                    )
                    if pressurized_aerosol_volume_factor < 1.0:
                        quality_flags.append(
                            QualityFlag(
                                code=(
                                    "worker_inhalation_pressurized_aerosol_volume_"
                                    "interpretation_defaulted"
                                ),
                                severity=Severity.WARNING,
                                message=(
                                    "Worker inhalation execution reduced volumetric aerosol "
                                    "mass with a bounded pressurized-aerosol interpretation "
                                    "factor because density was defaulted."
                                ),
                            )
                        )
                product_mass_g_event = (
                    None
                    if use_amount_per_event is None or density_g_per_ml is None
                    else use_amount_per_event
                    * density_g_per_ml
                    * pressurized_aerosol_volume_factor
                )
                if use_amount_per_event is not None:
                    assumptions.append(
                        _assumption_record(
                            name="use_amount_per_event",
                            value=use_amount_per_event,
                            unit="mL/event",
                            source_kind=SourceKind.USER_INPUT,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Use amount per event was carried through the worker adapter "
                                "request."
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
                            "Concentration fraction was carried through the worker adapter "
                            "request."
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
                    rationale="Use frequency was carried through the worker adapter request.",
                    applicability_domain=applicability_domain,
                )
            )
            if room_volume_m3 is not None:
                assumptions.append(
                    _assumption_record(
                        name="room_volume_m3",
                        value=room_volume_m3,
                        unit="m3",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale="Room volume was carried through the worker adapter request.",
                        applicability_domain=applicability_domain,
                    )
                )
            if air_exchange_rate is not None:
                assumptions.append(
                    _assumption_record(
                        name="air_exchange_rate_per_hour",
                        value=air_exchange_rate,
                        unit="1/h",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Air exchange rate was carried through the worker adapter request."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            if task_duration_hours is not None:
                assumptions.append(
                    _assumption_record(
                        name="task_duration_hours",
                        value=task_duration_hours,
                        unit="h",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Task duration was carried through the worker task context."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )

            vapor_release_override = None if overrides is None else overrides.vapor_release_fraction
            if vapor_release_override is not None:
                vapor_release_fraction = float(vapor_release_override)
                assumptions.append(
                    _assumption_record(
                        name="vapor_release_fraction",
                        value=vapor_release_fraction,
                        unit="fraction",
                        source_kind=SourceKind.USER_INPUT,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Vapor release fraction was supplied as an execution override."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            else:
                (
                    vapor_release_fraction,
                    release_source,
                ) = registry.worker_inhalation_vapor_release_fraction(
                    envelope.emission_profile
                )
                assumptions.append(
                    _assumption_record(
                        name="vapor_release_fraction",
                        value=vapor_release_fraction,
                        unit="fraction",
                        source_kind=SourceKind.DEFAULT_REGISTRY,
                        source=release_source,
                        rationale=(
                            "Vapor release fraction defaulted from the worker inhalation "
                            "execution heuristic pack for non-spray tasks."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )

            if (
                product_mass_g_event is not None
                and concentration_fraction is not None
                and room_volume_m3 is not None
                and air_exchange_rate is not None
                and task_duration_hours is not None
                and inhalation_rate is not None
                and body_weight is not None
            ):
                chemical_mass_mg_event = product_mass_g_event * 1000.0 * concentration_fraction
                released_mass_mg_event = chemical_mass_mg_event * vapor_release_fraction
                k = max(air_exchange_rate, 0.0)
                initial_air_concentration = released_mass_mg_event / room_volume_m3
                if k == 0:
                    baseline_average_air_concentration = initial_air_concentration
                else:
                    baseline_average_air_concentration = initial_air_concentration * (
                        (1.0 - math.exp(-k * task_duration_hours)) / (k * task_duration_hours)
                    )
                baseline_inhaled_mass_mg_day = (
                    baseline_average_air_concentration
                    * inhalation_rate
                    * task_duration_hours
                    * use_events_per_day
                )
                baseline_external_dose = baseline_inhaled_mass_mg_day / body_weight
                baseline_model_family = "room_average_vapor_release_surrogate"
                assumptions.extend(
                    [
                        _assumption_record(
                            name="chemical_mass_mg_per_event",
                            value=round(chemical_mass_mg_event, 8),
                            unit="mg/event",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Chemical mass per event was derived from product mass per "
                                "event and concentration fraction."
                            ),
                            applicability_domain=applicability_domain,
                        ),
                        _assumption_record(
                            name="released_mass_mg_per_event",
                            value=round(released_mass_mg_event, 8),
                            unit="mg/event",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Released mass per event was derived from chemical mass per "
                                "event and the vapor-release fraction."
                            ),
                            applicability_domain=applicability_domain,
                        ),
                        _assumption_record(
                            name="average_air_concentration_mg_per_m3",
                            value=round(baseline_average_air_concentration, 8),
                            unit="mg/m3",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Average air concentration was derived from a well-mixed room "
                                "surrogate with first-order air exchange removal."
                            ),
                            applicability_domain=applicability_domain,
                        ),
                        _assumption_record(
                            name="inhaled_mass_mg_per_day",
                            value=round(baseline_inhaled_mass_mg_day, 8),
                            unit="mg/day",
                            source_kind=SourceKind.DERIVED,
                            source=_execution_algorithm_source(),
                            rationale=(
                                "Inhaled mass per day was derived from average air "
                                "concentration, inhalation rate, task duration, and "
                                "use frequency."
                            ),
                            applicability_domain=applicability_domain,
                        ),
                    ]
                )
                limitations.append(
                    LimitationNote(
                        code="worker_art_execution_vapor_surrogate",
                        severity=Severity.WARNING,
                        message=(
                            "The current worker vapor execution path uses a room-average "
                            "release surrogate rather than a validated ART vapor model."
                        ),
                    )
                )
                baseline_scenario = ExposureScenario(
                    scenario_id="worker-inh-surrogate-baseline",
                    chemical_id=chemical_id,
                    chemical_name=chemical_name,
                    route=Route.INHALATION,
                    scenario_class=ScenarioClass.INHALATION,
                    external_dose=ScenarioDose(
                        metric="normalized_external_dose",
                        value=round(baseline_external_dose, 8),
                        unit=DoseUnit.MG_PER_KG_DAY,
                    ),
                    product_use_profile=base_request.product_use_profile.model_copy(
                        update={"exposure_duration_hours": task_duration_hours}
                    ),
                    population_profile=base_request.population_profile.model_copy(
                        update={
                            "body_weight_kg": body_weight,
                            "inhalation_rate_m3_per_hour": inhalation_rate,
                        }
                    ),
                    route_metrics={
                        "average_air_concentration_mg_per_m3": round(
                            baseline_average_air_concentration,
                            8,
                        ),
                        "inhaled_mass_mg_per_day": round(baseline_inhaled_mass_mg_day, 8),
                        "released_mass_mg_per_event": round(released_mass_mg_event, 8),
                    },
                    assumptions=[],
                    provenance=_execution_provenance(registry, generated_at=generated_at),
                    limitations=[],
                    quality_flags=[],
                    fit_for_purpose=FitForPurpose(
                        label="worker_vapor_surrogate_baseline",
                        suitable_for=[],
                        not_suitable_for=[],
                    ),
                    tier_semantics=TierSemantics(
                        tier_claimed=TierLevel.TIER_0,
                        tier_earned=TierLevel.TIER_0,
                        tier_rationale="Internal worker vapor surrogate baseline only.",
                        assumption_checks_passed=True,
                        required_caveats=[],
                        forbidden_interpretations=[],
                    ),
                    interpretation_notes=[],
                )

    if baseline_scenario is not None:
        assumptions = [*baseline_scenario.assumptions, *assumptions]
        quality_flags.extend(baseline_scenario.quality_flags)
        limitations.extend(baseline_scenario.limitations)
        baseline_average_air_concentration = _float_or_none(
            baseline_scenario.route_metrics.get("average_air_concentration_mg_per_m3")
        )
        baseline_inhaled_mass_mg_day = _float_or_none(
            baseline_scenario.route_metrics.get("inhaled_mass_mg_per_day")
        )
        baseline_external_dose = baseline_scenario.external_dose.value
        body_weight = baseline_scenario.population_profile.body_weight_kg
        inhalation_rate = baseline_scenario.population_profile.inhalation_rate_m3_per_hour
        product_profile = baseline_scenario.product_use_profile
        population_profile = baseline_scenario.population_profile

    task_intensity_label = _worker_task_intensity_label(task_context)
    task_intensity_factor = 1.0
    if task_intensity_label is not None:
        task_intensity_factor, task_intensity_source = (
            registry.worker_inhalation_task_intensity_factor(task_intensity_label)
        )
        assumptions.append(
            _assumption_record(
                name="worker_task_intensity_factor",
                value=task_intensity_factor,
                unit="factor",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=task_intensity_source,
                rationale=(
                    "Worker task-intensity factor defaulted from the bounded worker "
                    "inhalation physiology heuristics."
                ),
                applicability_domain=applicability_domain,
            )
        )
        limitations.append(
            LimitationNote(
                code="worker_task_intensity_screening",
                severity=Severity.WARNING,
                message=(
                    "Worker task intensity adjusts inhalation rate with a bounded screening "
                    "factor rather than a measured task-specific ventilation rate."
                ),
            )
        )
        if inhalation_rate is not None:
            assumptions.append(
                _assumption_record(
                    name="effective_inhalation_rate_m3_per_hour",
                    value=round(inhalation_rate * task_intensity_factor, 8),
                    unit="m3/h",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Effective inhalation rate was derived from the preserved "
                        "population inhalation rate and the worker task-intensity factor."
                    ),
                    applicability_domain=applicability_domain,
                )
            )

    effective_inhalation_rate = (
        inhalation_rate * task_intensity_factor if inhalation_rate is not None else None
    )
    if baseline_inhaled_mass_mg_day is not None:
        baseline_inhaled_mass_mg_day *= task_intensity_factor
    if baseline_external_dose is not None:
        baseline_external_dose *= task_intensity_factor

    source_distance_m = (
        None if base_request is None else getattr(base_request, "source_distance_m", None)
    )
    control_factor = None if overrides is None else overrides.control_factor
    control_context_label = "generic"
    control_context_factor = 1.0
    capture_zone_label = "generic"
    capture_zone_alignment_factor = 1.0
    capture_distance_label = "generic"
    capture_distance_context_label = "generic"
    capture_distance_alignment_factor = 1.0
    explicit_lev_family_label = (
        _normalized_text(task_context.lev_family) if task_context.lev_family is not None else None
    )
    hood_face_velocity_m_per_s = task_context.hood_face_velocity_m_per_s
    capture_velocity_label = "generic"
    capture_velocity_context_label = "generic"
    capture_velocity_velocity_label = "generic"
    capture_velocity_measured_profile_label = "generic"
    capture_velocity_factor = 1.0
    if control_factor is None:
        control_context_terms = [
            task_context.workplace_setting or "",
            *task_context.local_controls,
            task_context.emission_descriptor or "",
        ]
        control_factor, control_source = registry.worker_inhalation_control_profile_factor(
            envelope.control_profile
        )
        assumptions.append(
            _assumption_record(
                name="worker_control_factor",
                value=control_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=control_source,
                rationale=(
                    "Worker control factor defaulted from the controlProfile heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
        control_context_label, control_context_factor, control_context_source = (
            registry.worker_inhalation_control_context_factor(control_context_terms)
        )
        assumptions.append(
            _assumption_record(
                name="worker_control_context_factor",
                value=control_context_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=control_context_source,
                rationale=(
                    "Worker control-context factor defaulted from explicit local controls and "
                    "workplace descriptors using the bounded control-context heuristics."
                ),
                applicability_domain=applicability_domain,
            )
        )
        (
            capture_zone_label,
            capture_zone_alignment_factor,
            capture_zone_source,
        ) = registry.worker_inhalation_capture_zone_alignment_factor(
            control_context_terms,
            envelope.control_profile,
        )
        assumptions.append(
            _assumption_record(
                name="worker_capture_zone_alignment_factor",
                value=capture_zone_alignment_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=capture_zone_source,
                rationale=(
                    "Worker capture-zone alignment factor defaulted from explicit local "
                    "controls and source-capture descriptors using the bounded capture-zone "
                    "heuristics."
                ),
                applicability_domain=applicability_domain,
            )
        )
        (
            capture_distance_label,
            capture_distance_context_label,
            capture_distance_alignment_factor,
            capture_distance_source,
        ) = registry.worker_inhalation_capture_distance_alignment_factor(
            source_distance_m,
            envelope.control_profile,
            control_context_label,
        )
        assumptions.append(
            _assumption_record(
                name="worker_capture_distance_alignment_factor",
                value=capture_distance_alignment_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=capture_distance_source,
                rationale=(
                    "Worker capture-distance alignment factor defaulted from the declared "
                    "source distance and the bounded capture-distance heuristics for local "
                    "exhaust or enclosed-capture tasks, refined with the inferred hood or "
                    "enclosure profile when available."
                ),
                applicability_domain=applicability_domain,
            )
        )
        (
            capture_velocity_label,
            capture_velocity_context_label,
            capture_velocity_velocity_label,
            capture_velocity_measured_profile_label,
            capture_velocity_factor,
            capture_velocity_source,
        ) = registry.worker_inhalation_capture_velocity_factor(
            control_context_terms,
            envelope.control_profile,
            control_context_label,
            explicit_lev_family_label,
            hood_face_velocity_m_per_s,
        )
        assumptions.append(
            _assumption_record(
                name="worker_capture_velocity_factor",
                value=capture_velocity_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=capture_velocity_source,
                rationale=(
                    "Worker capture-velocity factor defaulted from explicit hood, booth, "
                    "and capture descriptors using the bounded LEV-family heuristics."
                ),
                applicability_domain=applicability_domain,
            )
        )
        if control_context_label != "generic":
            limitations.append(
                LimitationNote(
                    code="worker_control_context_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Explicit worker control context refined the control factor with a "
                        "bounded LEV/control-context heuristic rather than measured capture or "
                        "dilution efficiency."
                    ),
                )
            )
        if capture_zone_label != "generic":
            limitations.append(
                LimitationNote(
                    code="worker_capture_zone_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Worker capture-zone alignment refined the control factor with a "
                        "bounded source-capture heuristic rather than measured hood capture "
                        "or containment performance."
                    ),
                )
            )
        if capture_distance_label != "generic":
            limitations.append(
                LimitationNote(
                    code="worker_capture_distance_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Worker source distance refined the control factor with a bounded "
                        "capture-distance heuristic rather than a measured capture-velocity "
                        "or hood-performance profile."
                    ),
                )
            )
        if capture_velocity_label != "generic":
            limitations.append(
                LimitationNote(
                    code="worker_capture_velocity_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Worker hood-face or capture-velocity semantics refined the control "
                        "factor with a bounded LEV-family heuristic rather than measured hood-"
                        "face velocity or capture-efficiency data."
                    ),
                )
            )
        if explicit_lev_family_label is not None:
            limitations.append(
                LimitationNote(
                    code="worker_lev_family_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Explicit LEV family refined the control factor with a bounded "
                        "family-class heuristic rather than a measured LEV performance model."
                    ),
                )
            )
    else:
        assumptions.append(
            _assumption_record(
                name="worker_control_factor",
                value=control_factor,
                unit="fraction",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale="Worker control factor was supplied as an execution override.",
                applicability_domain=applicability_domain,
            )
        )

    effective_control_factor = min(
        control_factor
        * control_context_factor
        * capture_zone_alignment_factor
        * capture_distance_alignment_factor
        * capture_velocity_factor,
        1.0,
    )
    assumptions.append(
        _assumption_record(
            name="effective_worker_control_factor",
            value=effective_control_factor,
            unit="fraction",
            source_kind=SourceKind.DERIVED,
            source=_execution_algorithm_source(),
            rationale=(
                "Effective worker control factor was derived from the base control-profile "
                "factor, the bounded control-context refinement, and the bounded "
                "capture-zone, capture-distance, and capture-velocity alignment refinements."
            ),
            applicability_domain=applicability_domain,
        )
    )

    respiratory_protection_factor = (
        None if overrides is None else overrides.respiratory_protection_factor
    )
    if respiratory_protection_factor is None:
        respiratory_protection_factor, rpe_source = (
            registry.worker_inhalation_respiratory_protection_factor(
                _normalized_rpe_state(task_context.respiratory_protection)
            )
        )
        assumptions.append(
            _assumption_record(
                name="respiratory_protection_factor",
                value=respiratory_protection_factor,
                unit="fraction",
                source_kind=SourceKind.DEFAULT_REGISTRY,
                source=rpe_source,
                rationale=(
                    "Respiratory protection factor defaulted from the worker inhalation RPE "
                    "heuristic pack."
                ),
                applicability_domain=applicability_domain,
            )
        )
    else:
        assumptions.append(
            _assumption_record(
                name="respiratory_protection_factor",
                value=respiratory_protection_factor,
                unit="fraction",
                source_kind=SourceKind.USER_INPUT,
                source=_execution_algorithm_source(),
                rationale=(
                    "Respiratory protection factor was supplied as an execution override."
                ),
                applicability_domain=applicability_domain,
            )
        )

    adjusted_average_air_concentration = None
    intake_equivalent_air_concentration = None
    adjusted_inhaled_mass_mg_day = None
    external_dose = None
    baseline_dose = None
    route_metrics: dict[str, ScalarValue | dict | list] = {
        "baselineModelFamily": baseline_model_family,
        "templateId": envelope.determinant_template_match.template_id,
        "templateAlignmentStatus": envelope.determinant_template_match.alignment_status.value,
        "activityClass": envelope.activity_class,
        "emissionProfile": envelope.emission_profile,
        "controlProfile": envelope.control_profile,
    }
    if inhalation_rate is not None:
        route_metrics["baseInhalationRateM3PerHour"] = round(inhalation_rate, 8)
        route_metrics["effectiveInhalationRateM3PerHour"] = round(
            effective_inhalation_rate or inhalation_rate,
            8,
        )
    if task_intensity_label is not None:
        route_metrics["taskIntensity"] = task_intensity_label
        route_metrics["taskIntensityFactor"] = round(task_intensity_factor, 8)
    route_metrics["baseControlProfileFactor"] = round(control_factor, 8)
    route_metrics["controlContextFactor"] = round(control_context_factor, 8)
    route_metrics["captureZoneAlignmentFactor"] = round(capture_zone_alignment_factor, 8)
    route_metrics["captureDistanceAlignmentFactor"] = round(
        capture_distance_alignment_factor,
        8,
    )
    route_metrics["captureVelocityFactor"] = round(capture_velocity_factor, 8)
    route_metrics["effectiveWorkerControlFactor"] = round(effective_control_factor, 8)
    if control_context_label != "generic":
        route_metrics["controlContextProfile"] = control_context_label
    if capture_zone_label != "generic":
        route_metrics["captureZoneProfile"] = capture_zone_label
    if capture_distance_label != "generic":
        route_metrics["captureDistanceProfile"] = capture_distance_label
    if capture_distance_context_label != "generic":
        route_metrics["captureDistanceContextProfile"] = capture_distance_context_label
    if capture_velocity_label != "generic":
        route_metrics["captureVelocityProfile"] = capture_velocity_label
    if capture_velocity_context_label != "generic":
        route_metrics["captureVelocityContextProfile"] = capture_velocity_context_label
    if capture_velocity_velocity_label != "generic":
        route_metrics["captureVelocityVelocityBand"] = capture_velocity_velocity_label
    if capture_velocity_measured_profile_label != "generic":
        route_metrics["captureVelocityMeasuredProfileBand"] = (
            capture_velocity_measured_profile_label
        )
    if explicit_lev_family_label is not None:
        route_metrics["levFamily"] = explicit_lev_family_label
    if hood_face_velocity_m_per_s is not None:
        route_metrics["hoodFaceVelocityMPerS"] = round(hood_face_velocity_m_per_s, 8)
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
        route_metrics["pressurizedAerosolCarrierFamily"] = pressurized_aerosol_carrier_label
    if pressurized_aerosol_formulation_factor != 1.0:
        route_metrics["pressurizedAerosolFormulationProfileAdjustmentFactor"] = round(
            pressurized_aerosol_formulation_factor,
            8,
        )
        route_metrics["pressurizedAerosolFormulationProfile"] = (
            pressurized_aerosol_formulation_label
        )
    assumption_lookup = {item.name: item for item in assumptions}
    aerosol_assumption = assumption_lookup.get(
        "pressurized_aerosol_volume_interpretation_factor"
    )
    if (
        "pressurizedAerosolVolumeInterpretationFactor" not in route_metrics
        and aerosol_assumption is not None
        and float(aerosol_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolVolumeInterpretationFactor"] = round(
            float(aerosol_assumption.value),
            8,
        )
        if not any(
            flag.code == "worker_inhalation_pressurized_aerosol_volume_interpretation_defaulted"
            for flag in quality_flags
        ):
            quality_flags.append(
                QualityFlag(
                    code="worker_inhalation_pressurized_aerosol_volume_interpretation_defaulted",
                    severity=Severity.WARNING,
                    message=(
                        "Worker inhalation execution reduced volumetric aerosol mass with "
                        "a bounded pressurized-aerosol interpretation factor because "
                        "default density was used."
                    ),
                )
            )
    aerosol_physchem_assumption = assumption_lookup.get(
        "pressurized_aerosol_physchem_adjustment_factor"
    )
    if (
        "pressurizedAerosolPhyschemAdjustmentFactor" not in route_metrics
        and aerosol_physchem_assumption is not None
        and float(aerosol_physchem_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolPhyschemAdjustmentFactor"] = round(
            float(aerosol_physchem_assumption.value),
            8,
        )
        if not any(
            flag.code == "worker_inhalation_pressurized_aerosol_physchem_adjustment_defaulted"
            for flag in quality_flags
        ):
            quality_flags.append(
                QualityFlag(
                    code="worker_inhalation_pressurized_aerosol_physchem_adjustment_defaulted",
                    severity=Severity.WARNING,
                    message=(
                        "Worker inhalation execution further reduced volumetric aerosol "
                        "mass with a bounded vapor-pressure aerosol adjustment."
                    ),
                )
            )
    if (
        "pressurizedAerosolPhyschemProfile" not in route_metrics
        and base_request is not None
        and base_request.physchem_context is not None
    ):
        aerosol_physchem_adjustment = registry.pressurized_aerosol_physchem_adjustment_factor(
            base_request.product_use_profile.product_category,
            base_request.product_use_profile.product_subtype,
            _float_or_none(base_request.physchem_context.vapor_pressure_mmhg),
            _float_or_none(base_request.physchem_context.molecular_weight_g_per_mol),
        )
        if aerosol_physchem_adjustment is not None:
            aerosol_physchem_label, aerosol_physchem_factor, _ = aerosol_physchem_adjustment
            if aerosol_physchem_factor < 1.0:
                route_metrics["pressurizedAerosolPhyschemProfile"] = aerosol_physchem_label
    aerosol_carrier_assumption = assumption_lookup.get(
        "pressurized_aerosol_carrier_family_adjustment_factor"
    )
    if (
        "pressurizedAerosolCarrierFamilyAdjustmentFactor" not in route_metrics
        and aerosol_carrier_assumption is not None
        and float(aerosol_carrier_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolCarrierFamilyAdjustmentFactor"] = round(
            float(aerosol_carrier_assumption.value),
            8,
        )
    if (
        "pressurizedAerosolCarrierFamily" not in route_metrics
        and base_request is not None
        and base_request.product_use_profile.aerosol_carrier_family is not None
        and aerosol_carrier_assumption is not None
        and float(aerosol_carrier_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolCarrierFamily"] = (
            base_request.product_use_profile.aerosol_carrier_family
        )
    if (
        aerosol_carrier_assumption is not None
        and float(aerosol_carrier_assumption.value) < 1.0
        and not any(
            flag.code == "worker_inhalation_pressurized_aerosol_carrier_family_adjustment_defaulted"
            for flag in quality_flags
        )
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_inhalation_pressurized_aerosol_carrier_family_adjustment_defaulted",
                severity=Severity.WARNING,
                message=(
                    "Worker inhalation execution further reduced volumetric aerosol mass "
                    "with a bounded aerosol carrier-family adjustment."
                ),
            )
        )
    aerosol_formulation_assumption = assumption_lookup.get(
        "pressurized_aerosol_formulation_profile_adjustment_factor"
    )
    if (
        "pressurizedAerosolFormulationProfileAdjustmentFactor" not in route_metrics
        and aerosol_formulation_assumption is not None
        and float(aerosol_formulation_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolFormulationProfileAdjustmentFactor"] = round(
            float(aerosol_formulation_assumption.value),
            8,
        )
    if (
        "pressurizedAerosolFormulationProfile" not in route_metrics
        and base_request is not None
        and base_request.product_use_profile.aerosol_formulation_profile is not None
        and aerosol_formulation_assumption is not None
        and float(aerosol_formulation_assumption.value) < 1.0
    ):
        route_metrics["pressurizedAerosolFormulationProfile"] = (
            base_request.product_use_profile.aerosol_formulation_profile
        )
    if (
        aerosol_formulation_assumption is not None
        and float(aerosol_formulation_assumption.value) < 1.0
        and not any(
            flag.code
            == "worker_inhalation_pressurized_aerosol_formulation_profile_adjustment_defaulted"
            for flag in quality_flags
        )
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_inhalation_pressurized_aerosol_formulation_profile_adjustment_defaulted",
                severity=Severity.WARNING,
                message=(
                    "Worker inhalation execution further reduced volumetric aerosol mass "
                    "with a bounded aerosol formulation-profile adjustment."
                ),
            )
        )

    if baseline_average_air_concentration is not None:
        adjusted_average_air_concentration = (
            baseline_average_air_concentration * effective_control_factor
        )
        intake_equivalent_air_concentration = (
            adjusted_average_air_concentration * respiratory_protection_factor
        )
        route_metrics["baselineAverageAirConcentrationMgPerM3"] = round(
            baseline_average_air_concentration,
            8,
        )
        route_metrics["controlAdjustedAverageAirConcentrationMgPerM3"] = round(
            adjusted_average_air_concentration,
            8,
        )
        route_metrics["intakeEquivalentAirConcentrationMgPerM3"] = round(
            intake_equivalent_air_concentration,
            8,
        )
    if baseline_inhaled_mass_mg_day is not None:
        adjusted_inhaled_mass_mg_day = (
            baseline_inhaled_mass_mg_day
            * effective_control_factor
            * respiratory_protection_factor
        )
        route_metrics["baselineInhaledMassMgPerDay"] = round(baseline_inhaled_mass_mg_day, 8)
        route_metrics["adjustedInhaledMassMgPerDay"] = round(adjusted_inhaled_mass_mg_day, 8)
        assumptions.append(
            _assumption_record(
                name="adjusted_inhaled_mass_mg_per_day",
                value=round(adjusted_inhaled_mass_mg_day, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Adjusted inhaled mass per day was derived from the baseline inhaled mass, "
                    "effective worker control factor, and respiratory-protection factor."
                ),
                applicability_domain=applicability_domain,
            )
        )
    route_metrics["workerControlFactor"] = round(effective_control_factor, 8)
    route_metrics["respiratoryProtectionFactor"] = round(respiratory_protection_factor, 8)

    if body_weight is not None and baseline_external_dose is not None:
        baseline_dose = ScenarioDose(
            metric="normalized_external_dose",
            value=round(baseline_external_dose, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        )
        if adjusted_inhaled_mass_mg_day is not None:
            adjusted_normalized_dose = adjusted_inhaled_mass_mg_day / body_weight
            external_dose = ScenarioDose(
                metric="normalized_worker_inhaled_dose",
                value=round(adjusted_normalized_dose, 8),
                unit=DoseUnit.MG_PER_KG_DAY,
            )
            assumptions.append(
                _assumption_record(
                    name="normalized_worker_inhaled_dose_mg_per_kg_day",
                    value=round(adjusted_normalized_dose, 8),
                    unit="mg/kg-day",
                    source_kind=SourceKind.DERIVED,
                    source=_execution_algorithm_source(),
                    rationale=(
                        "Normalized worker inhaled dose was derived from the adjusted inhaled "
                        "mass and body weight."
                    ),
                    applicability_domain=applicability_domain,
                )
            )

    limitations.extend(
        [
            LimitationNote(
                code="worker_art_execution_not_art_solver",
                severity=Severity.WARNING,
                message=(
                    "The current execution path is an ART-aligned surrogate layered on top of "
                    "existing screening inhalation kernels; it is not a real ART solver."
                ),
            ),
            LimitationNote(
                code="worker_art_execution_control_factors_generic",
                severity=Severity.WARNING,
                message=(
                    "Worker control and respiratory-protection effects are applied as bounded "
                    "heuristic factors rather than determinant-specific model terms."
                ),
            ),
        ]
    )
    quality_flags.append(
        QualityFlag(
            code="worker_art_execution_completed",
            severity=Severity.INFO,
            message=(
                "Worker inhalation surrogate execution completed with explicit control and "
                "respiratory-protection modifiers."
            ),
        )
    )

    ready_for_execution = (
        ingest_result.ready_for_adapter_execution and baseline_scenario is not None
    )
    ready_for_execution = ready_for_execution and not any(
        item.severity == Severity.ERROR for item in limitations
    )
    manual_review_required = ingest_result.manual_review_required or baseline_model_family in {
        "room_average_vapor_release_surrogate",
    }

    fit_for_purpose = FitForPurpose(
        label="worker_inhalation_control_aware_screening",
        suitable_for=[
            "worker inhalation screening with explicit control modifiers",
            "ART-aligned occupational exposure triage",
            "PBPK-ready external inhalation dose handoff after expert review",
        ],
        not_suitable_for=[
            "measured workplace concentration replacement",
            "true ART execution",
            "occupational compliance determination",
        ],
    )
    baseline_tier = (
        TierLevel.TIER_1 if baseline_model_family == "tier1_nf_ff_screening" else TierLevel.TIER_0
    )
    tier_semantics = TierSemantics(
        tier_claimed=baseline_tier,
        tier_earned=baseline_tier if ready_for_execution else TierLevel.TIER_0,
        tier_rationale=(
            "Worker inhalation execution preserves the strongest available underlying "
            "screening kernel and layers explicit control and respiratory-protection factors "
            "on top."
        ),
        assumption_checks_passed=ready_for_execution,
        required_caveats=[
            "Interpret the result as a worker control-aware screening estimate rather than a "
            "validated occupational model output.",
            "Keep the determinant template match, quality flags, and limitations attached to "
            "any downstream use."
        ],
        forbidden_interpretations=[
            "Do not treat the result as a real ART or Stoffenmanager execution.",
            "Do not treat the respiratory-protection factor as a compliance-assured "
            "protection factor.",
            "Do not treat the output as a final occupational risk conclusion.",
        ],
    )
    interpretation_notes = [
        "The baseline concentration and dose come from the strongest available inhalation "
        "screening kernel preserved by the worker Tier 2 path.",
        "Worker control and respiratory-protection modifiers are then applied transparently as "
        "bounded factors.",
        "When the task is vapor-generating and no direct spray kernel applies, execution falls "
        "back to a labeled room-average vapor-release surrogate."
    ]

    result = WorkerInhalationTier2ExecutionResult(
        supported_by_adapter=True,
        ready_for_execution=ready_for_execution,
        manual_review_required=manual_review_required,
        resolved_adapter=ingest_result.resolved_adapter,
        target_model_family=adapter_request.target_model_family,
        chemical_id=chemical_id,
        chemical_name=chemical_name,
        baseline_dose=baseline_dose,
        external_dose=external_dose,
        product_use_profile=product_profile,
        population_profile=population_profile,
        task_context=task_context,
        art_task_envelope=envelope,
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
        update={"validation_summary": _build_worker_inhalation_validation_summary(result)},
        deep=True,
    )


def import_worker_inhalation_art_execution_result(
    params: ImportWorkerArtExecutionResultRequest,
    *,
    registry: DefaultsRegistry | None = None,
    generated_at: str | None = None,
) -> WorkerInhalationTier2ExecutionResult:
    registry = registry or DefaultsRegistry.load()
    adapter_request = params.adapter_request
    external_result = params.external_result
    ingest_result = ingest_worker_inhalation_tier2_task(
        adapter_request,
        registry=registry,
        generated_at=generated_at,
    )

    quality_flags = list(ingest_result.quality_flags)
    limitations = list(ingest_result.limitations)
    assumptions: list[ExposureAssumptionRecord] = []
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

    if not ingest_result.supported_by_adapter or ingest_result.art_task_envelope is None:
        return WorkerInhalationTier2ExecutionResult(
            supported_by_adapter=False,
            ready_for_execution=False,
            manual_review_required=True,
            resolved_adapter=None,
            target_model_family=adapter_request.target_model_family,
            chemical_id=chemical_id,
            chemical_name=chemical_name,
            task_context=adapter_request.task_context,
            art_task_envelope=None,
            execution_overrides=None,
            quality_flags=quality_flags,
            limitations=limitations,
            provenance=_external_import_provenance(registry, generated_at=generated_at),
            fit_for_purpose=FitForPurpose(
                label="unsupported_worker_inhalation_external_import",
                suitable_for=[],
                not_suitable_for=[
                    "worker inhalation external ART result import",
                    "Tier 2 occupational inhalation refinement",
                ],
            ),
            tier_semantics=TierSemantics(
                tier_claimed=TierLevel.TIER_2,
                tier_earned=TierLevel.TIER_0,
                tier_rationale=(
                    "The requested worker Tier 2 model family is not importable in the current "
                    "ART-side exchange boundary."
                ),
                assumption_checks_passed=False,
                required_caveats=[
                    "No external occupational inhalation result was imported because the "
                    "current adapter family is unsupported."
                ],
                forbidden_interpretations=[
                    "Do not treat this response as a solved occupational inhalation result."
                ],
            ),
            validation_summary=None,
            interpretation_notes=[
                "External ART-side result import is currently limited to the `art` family."
            ],
        )

    envelope = ingest_result.art_task_envelope
    task_context = adapter_request.task_context
    art_inputs = envelope.art_inputs
    applicability_domain = {
        "product_category": art_inputs.get("productCategory"),
        "product_subtype": art_inputs.get("productSubtype"),
        "application_method": art_inputs.get("applicationMethod"),
        "physical_form": art_inputs.get("physicalForm"),
        "activity_class": envelope.activity_class,
        "control_profile": envelope.control_profile,
        "external_source_system": external_result.source_system,
    }
    external_source = _external_art_result_source(external_result)

    surrogate_result = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=adapter_request,
            context_of_use=f"{params.context_of_use}-screening-baseline",
        ),
        registry=registry,
        generated_at=generated_at,
    )
    baseline_dose = surrogate_result.baseline_dose
    artifact_result_payload, artifact_adapter_id, artifact_locator = _result_payload_from_artifacts(
        external_result.raw_artifacts
    )
    result_payload = external_result.result_payload or artifact_result_payload
    payload_schema_version = _result_payload_text(
        result_payload,
        "schemaVersion",
        "schema_version",
    )
    payload_source_run_id = _result_payload_text(
        result_payload,
        "sourceRunId",
        "source_run_id",
        "runId",
    )
    payload_model_version = _result_payload_text(
        result_payload,
        "modelVersion",
        "model_version",
    )
    payload_result_status = _result_payload_text(
        result_payload,
        "resultStatus",
        "result_status",
    )
    payload_task_duration_hours = _result_payload_float(
        result_payload,
        "taskDurationHours",
        "task_duration_hours",
    )
    payload_concentration = _result_payload_float(
        result_payload,
        "breathingZoneConcentrationMgPerM3",
        "breathing_zone_concentration_mg_per_m3",
    )
    payload_inhaled_mass = _result_payload_float(
        result_payload,
        "inhaledMassMgPerDay",
        "inhaled_mass_mg_per_day",
    )
    payload_normalized_dose = _result_payload_float(
        result_payload,
        "normalizedExternalDoseMgPerKgDay",
        "normalized_external_dose_mg_per_kg_day",
    )
    payload_determinant_snapshot = _result_payload_dict(
        result_payload,
        "determinantSnapshot",
        "determinant_snapshot",
    )
    route_metrics: dict[str, ScalarValue | dict | list] = {
        "baselineModelFamily": surrogate_result.route_metrics.get("baselineModelFamily"),
        "templateId": envelope.determinant_template_match.template_id,
        "templateAlignmentStatus": envelope.determinant_template_match.alignment_status.value,
        "activityClass": envelope.activity_class,
        "emissionProfile": envelope.emission_profile,
        "controlProfile": envelope.control_profile,
        "importedSourceSystem": external_result.source_system,
        "importedResultStatus": external_result.result_status,
    }
    if payload_schema_version is not None:
        route_metrics["importedResultPayloadSchemaVersion"] = payload_schema_version
    if external_result.source_run_id is not None or payload_source_run_id is not None:
        route_metrics["externalRunId"] = external_result.source_run_id or payload_source_run_id
    if external_result.model_version is not None or payload_model_version is not None:
        route_metrics["externalModelVersion"] = (
            external_result.model_version or payload_model_version
        )
    if payload_determinant_snapshot:
        route_metrics["importedDeterminantSnapshot"] = payload_determinant_snapshot
    if result_payload:
        route_metrics["importedResultPayloadUsed"] = True
    if artifact_result_payload:
        route_metrics["importedArtifactPayloadUsed"] = True
    if artifact_adapter_id is not None:
        route_metrics["artifactFormatAdapterId"] = artifact_adapter_id.value
    if artifact_locator is not None:
        route_metrics["artifactFormatAdapterLocator"] = artifact_locator

    if external_result.result_status == "failed":
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_failed",
                severity=Severity.ERROR,
                message=(
                    "The imported external ART result was marked as failed and cannot be "
                    "normalized into a worker inhalation dose."
                ),
            )
        )
    elif payload_result_status is not None and _normalized_text(payload_result_status) == "failed":
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_payload_failed",
                severity=Severity.ERROR,
                message=(
                    "The imported resultPayload was marked as failed and cannot be normalized "
                    "into a worker inhalation dose."
                ),
            )
        )

    quality_flags.append(
        QualityFlag(
            code="worker_art_external_result_imported",
            severity=Severity.INFO,
            message=(
                "Imported an external ART-side worker inhalation result into the governed "
                "Direct-Use Exposure MCP execution schema."
            ),
        )
    )
    if result_payload:
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_present",
                severity=Severity.INFO,
                message=(
                    "The import included a structured resultPayload from an external ART-side "
                    "runner."
                ),
            )
        )
    if artifact_result_payload:
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_artifact_payload_present",
                severity=Severity.INFO,
                message=(
                    "The import included inline raw-artifact content that was parsed through "
                    "a named ART artifact-format adapter."
                ),
            )
        )
    if artifact_adapter_id is not None:
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_artifact_adapter_resolved",
                severity=Severity.INFO,
                message=(
                    "Resolved raw artifact content through the "
                    f"`{artifact_adapter_id.value}` adapter."
                ),
            )
        )
    if _normalized_text(external_result.source_system) != "art":
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_non_art_source",
                severity=Severity.WARNING,
                message=(
                    "The imported external result did not declare sourceSystem='ART'. Review "
                    "cross-tool compatibility before treating this as an ART-aligned import."
                ),
            )
        )
    if not external_result.raw_artifacts and not result_payload:
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_raw_artifacts_missing",
                severity=Severity.WARNING,
                message=(
                    "The imported external ART result did not include rawArtifacts. Preserve "
                    "an auditable run report or export file when possible."
                ),
            )
        )
    elif not external_result.raw_artifacts and result_payload:
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_without_raw_artifacts",
                severity=Severity.INFO,
                message=(
                    "The import included a structured resultPayload but no rawArtifacts. Keep "
                    "the original external run export when possible."
                ),
            )
        )
    elif (
        external_result.raw_artifacts
        and not external_result.result_payload
        and artifact_result_payload
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_artifact_payload_used_without_explicit_summary",
                severity=Severity.INFO,
                message=(
                    "The import derived its normalized summary from inline raw-artifact content "
                    "because no explicit resultPayload was supplied."
                ),
            )
        )
    if external_result.quality_notes:
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_quality_notes",
                severity=Severity.WARNING,
                message=" ".join(external_result.quality_notes),
            )
        )

    body_weight = None
    inhalation_rate = None
    if surrogate_result.population_profile is not None:
        body_weight = surrogate_result.population_profile.body_weight_kg
        inhalation_rate = surrogate_result.population_profile.inhalation_rate_m3_per_hour
        population_profile = surrogate_result.population_profile
    if body_weight is None:
        body_weight = _float_or_none(art_inputs.get("bodyWeightKg"))
    if inhalation_rate is None:
        inhalation_rate = _float_or_none(art_inputs.get("inhalationRateM3PerHour"))

    task_duration_hours = (
        external_result.task_duration_hours
        or payload_task_duration_hours
        or task_context.task_duration_hours
        or _float_or_none(art_inputs.get("eventDurationHours"))
    )
    use_events_per_day = _float_or_none(art_inputs.get("useEventsPerDay")) or 1.0
    if body_weight is not None:
        assumptions.append(
            _assumption_record(
                name="body_weight_kg",
                value=body_weight,
                unit="kg",
                source_kind=(
                    SourceKind.USER_INPUT
                    if _float_or_none(art_inputs.get("bodyWeightKg")) is not None
                    else SourceKind.DEFAULT_REGISTRY
                ),
                source=(
                    _execution_algorithm_source()
                    if _float_or_none(art_inputs.get("bodyWeightKg")) is not None
                    else registry.population_defaults(
                        population_profile.population_group if population_profile else "adult"
                    )[1]
                ),
                rationale=(
                    "Body weight was preserved from the worker adapter payload for external "
                    "ART-result normalization."
                    if _float_or_none(art_inputs.get("bodyWeightKg")) is not None
                    else "Body weight defaulted from the population group for external "
                    "ART-result normalization."
                ),
                applicability_domain=applicability_domain,
            )
        )
    if (
        inhalation_rate is not None
        and external_result.breathing_zone_concentration_mg_per_m3 is not None
    ):
        assumptions.append(
            _assumption_record(
                name="inhalation_rate_m3_per_hour",
                value=inhalation_rate,
                unit="m3/h",
                source_kind=(
                    SourceKind.USER_INPUT
                    if _float_or_none(art_inputs.get("inhalationRateM3PerHour")) is not None
                    else SourceKind.DEFAULT_REGISTRY
                ),
                source=(
                    _execution_algorithm_source()
                    if _float_or_none(art_inputs.get("inhalationRateM3PerHour")) is not None
                    else registry.population_defaults(
                        population_profile.population_group if population_profile else "adult"
                    )[1]
                ),
                rationale=(
                    "Inhalation rate was preserved from the worker adapter payload for "
                    "external ART-result normalization."
                    if _float_or_none(art_inputs.get("inhalationRateM3PerHour")) is not None
                    else "Inhalation rate defaulted from the population group for external "
                    "ART-result normalization."
                ),
                applicability_domain=applicability_domain,
            )
        )
    if external_result.task_duration_hours is not None or payload_task_duration_hours is not None:
        assumptions.append(
            _assumption_record(
                name="task_duration_hours",
                value=external_result.task_duration_hours or payload_task_duration_hours,
                unit="h",
                source_kind=SourceKind.SYSTEM,
                source=external_source,
                rationale=(
                    "Task duration was imported from the external ART execution result or its "
                    "structured resultPayload."
                ),
                applicability_domain=applicability_domain,
            )
        )

    task_intensity_label = _worker_task_intensity_label(task_context)
    task_intensity_factor = 1.0
    if task_intensity_label is not None:
        task_intensity_factor, task_intensity_source = (
            registry.worker_inhalation_task_intensity_factor(task_intensity_label)
        )
    effective_inhalation_rate = (
        inhalation_rate * task_intensity_factor if inhalation_rate is not None else None
    )

    imported_concentration = (
        external_result.breathing_zone_concentration_mg_per_m3 or payload_concentration
    )
    imported_inhaled_mass = external_result.inhaled_mass_mg_per_day or payload_inhaled_mass
    imported_dose_value = (
        external_result.normalized_external_dose_mg_per_kg_day or payload_normalized_dose
    )
    derivation_method = "explicit_normalized_external_dose"
    if (
        external_result.breathing_zone_concentration_mg_per_m3 is not None
        and payload_concentration is not None
        and not _payload_matches_numeric(
            external_result.breathing_zone_concentration_mg_per_m3,
            payload_concentration,
        )
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_concentration_mismatch",
                severity=Severity.WARNING,
                message=(
                    "The explicit breathingZoneConcentrationMgPerM3 field did not match the "
                    "structured resultPayload within 5%."
                ),
            )
        )
    if (
        external_result.inhaled_mass_mg_per_day is not None
        and payload_inhaled_mass is not None
        and not _payload_matches_numeric(
            external_result.inhaled_mass_mg_per_day,
            payload_inhaled_mass,
        )
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_mass_mismatch",
                severity=Severity.WARNING,
                message=(
                    "The explicit inhaledMassMgPerDay field did not match the structured "
                    "resultPayload within 5%."
                ),
            )
        )
    if (
        external_result.normalized_external_dose_mg_per_kg_day is not None
        and payload_normalized_dose is not None
        and not _payload_matches_numeric(
            external_result.normalized_external_dose_mg_per_kg_day,
            payload_normalized_dose,
        )
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_dose_mismatch",
                severity=Severity.WARNING,
                message=(
                    "The explicit normalizedExternalDoseMgPerKgDay field did not match the "
                    "structured resultPayload within 5%."
                ),
            )
        )
    if (
        external_result.source_run_id is not None
        and payload_source_run_id is not None
        and external_result.source_run_id != payload_source_run_id
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_run_id_mismatch",
                severity=Severity.WARNING,
                message=(
                    "The explicit sourceRunId field did not match the structured "
                    "resultPayload sourceRunId."
                ),
            )
        )
    if (
        external_result.model_version is not None
        and payload_model_version is not None
        and external_result.model_version != payload_model_version
    ):
        quality_flags.append(
            QualityFlag(
                code="worker_art_external_result_payload_model_version_mismatch",
                severity=Severity.WARNING,
                message=(
                    "The explicit modelVersion field did not match the structured "
                    "resultPayload modelVersion."
                ),
            )
        )

    if imported_concentration is not None:
        assumptions.append(
            _assumption_record(
                name="breathing_zone_concentration_mg_per_m3",
                value=round(imported_concentration, 8),
                unit="mg/m3",
                source_kind=SourceKind.SYSTEM,
                source=external_source,
                rationale=(
                    "Breathing-zone concentration was imported from the external ART "
                    "execution result."
                ),
                applicability_domain=applicability_domain,
            )
        )
        route_metrics["importedBreathingZoneConcentrationMgPerM3"] = round(
            imported_concentration,
            8,
        )
    if imported_inhaled_mass is not None:
        assumptions.append(
            _assumption_record(
                name="imported_inhaled_mass_mg_per_day",
                value=round(imported_inhaled_mass, 8),
                unit="mg/day",
                source_kind=SourceKind.SYSTEM,
                source=external_source,
                rationale=(
                    "Inhaled mass per day was imported from the external ART execution result."
                ),
                applicability_domain=applicability_domain,
            )
        )
        route_metrics["importedInhaledMassMgPerDay"] = round(imported_inhaled_mass, 8)

    if imported_dose_value is not None:
        assumptions.append(
            _assumption_record(
                name="normalized_worker_inhaled_dose_mg_per_kg_day",
                value=round(imported_dose_value, 8),
                unit="mg/kg-day",
                source_kind=SourceKind.SYSTEM,
                source=external_source,
                rationale=(
                    "Normalized worker inhaled dose was imported directly from the external "
                    "ART execution result."
                ),
                applicability_domain=applicability_domain,
            )
        )
        if imported_inhaled_mass is not None and body_weight is not None:
            expected_dose = imported_inhaled_mass / body_weight
            if not math.isclose(imported_dose_value, expected_dose, rel_tol=0.05):
                quality_flags.append(
                    QualityFlag(
                        code="worker_art_external_result_metric_divergence",
                        severity=Severity.WARNING,
                        message=(
                            "Imported normalizedExternalDoseMgPerKgDay and inhaledMassMgPerDay "
                            "were not mutually consistent within 5% after body-weight "
                            "normalization."
                        ),
                    )
                )
        elif imported_inhaled_mass is None and body_weight is not None:
            imported_inhaled_mass = imported_dose_value * body_weight
            route_metrics["importedInhaledMassMgPerDay"] = round(imported_inhaled_mass, 8)
    elif imported_inhaled_mass is not None and body_weight is not None:
        imported_dose_value = imported_inhaled_mass / body_weight
        derivation_method = "inhaled_mass_and_body_weight"
        assumptions.append(
            _assumption_record(
                name="normalized_worker_inhaled_dose_mg_per_kg_day",
                value=round(imported_dose_value, 8),
                unit="mg/kg-day",
                source_kind=SourceKind.DERIVED,
                source=_external_art_result_source(external_result),
                rationale=(
                    "Normalized worker inhaled dose was derived from imported inhaled mass "
                    "per day and body weight."
                ),
                applicability_domain=applicability_domain,
            )
        )
    elif (
        imported_concentration is not None
        and effective_inhalation_rate is not None
        and task_duration_hours is not None
        and body_weight is not None
    ):
        imported_inhaled_mass = (
            imported_concentration
            * effective_inhalation_rate
            * task_duration_hours
            * use_events_per_day
        )
        imported_dose_value = imported_inhaled_mass / body_weight
        derivation_method = "breathing_zone_concentration_mass_balance"
        assumptions.append(
            _assumption_record(
                name="imported_inhaled_mass_mg_per_day",
                value=round(imported_inhaled_mass, 8),
                unit="mg/day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Imported inhaled mass per day was derived from breathing-zone "
                    "concentration, inhalation rate, task duration, and use frequency."
                ),
                applicability_domain=applicability_domain,
            )
        )
        assumptions.append(
            _assumption_record(
                name="normalized_worker_inhaled_dose_mg_per_kg_day",
                value=round(imported_dose_value, 8),
                unit="mg/kg-day",
                source_kind=SourceKind.DERIVED,
                source=_execution_algorithm_source(),
                rationale=(
                    "Normalized worker inhaled dose was derived from imported breathing-zone "
                    "concentration and preserved inhalation/weight terms."
                ),
                applicability_domain=applicability_domain,
            )
        )
        route_metrics["importedInhaledMassMgPerDay"] = round(imported_inhaled_mass, 8)
        if inhalation_rate is not None:
            route_metrics["baseInhalationRateM3PerHour"] = round(inhalation_rate, 8)
            route_metrics["effectiveInhalationRateM3PerHour"] = round(
                effective_inhalation_rate or inhalation_rate,
                8,
            )
        if task_intensity_label is not None:
            route_metrics["taskIntensity"] = task_intensity_label
            route_metrics["taskIntensityFactor"] = round(task_intensity_factor, 8)
            assumptions.append(
                _assumption_record(
                    name="worker_task_intensity_factor",
                    value=task_intensity_factor,
                    unit="factor",
                    source_kind=SourceKind.DEFAULT_REGISTRY,
                    source=task_intensity_source,
                    rationale=(
                        "Worker task-intensity factor defaulted from the bounded worker "
                        "inhalation physiology heuristics."
                    ),
                    applicability_domain=applicability_domain,
                )
            )
            if inhalation_rate is not None:
                assumptions.append(
                    _assumption_record(
                        name="effective_inhalation_rate_m3_per_hour",
                        value=round(inhalation_rate * task_intensity_factor, 8),
                        unit="m3/h",
                        source_kind=SourceKind.DERIVED,
                        source=_execution_algorithm_source(),
                        rationale=(
                            "Effective inhalation rate was derived from the preserved "
                            "population inhalation rate and the worker task-intensity factor."
                        ),
                        applicability_domain=applicability_domain,
                    )
                )
            limitations.append(
                LimitationNote(
                    code="worker_task_intensity_screening",
                    severity=Severity.WARNING,
                    message=(
                        "Worker task intensity adjusts inhalation rate with a bounded "
                        "screening factor rather than a measured task-specific ventilation "
                        "rate."
                    ),
                )
            )
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_dose_derived_from_concentration",
                severity=Severity.INFO,
                message=(
                    "The imported worker inhalation dose was derived from breathing-zone "
                    "concentration plus preserved task and physiology terms because the "
                    "external result did not provide inhaled mass or normalized dose directly."
                ),
            )
        )
    else:
        limitations.append(
            LimitationNote(
                code="worker_art_external_result_metrics_incomplete",
                severity=Severity.ERROR,
                message=(
                    "The imported external ART result did not provide enough information to "
                    "normalize a worker inhalation dose."
                ),
            )
        )

    route_metrics["importedDoseDerivationMethod"] = derivation_method

    external_dose = None
    if imported_dose_value is not None:
        external_dose = ScenarioDose(
            metric="normalized_worker_inhaled_dose",
            value=round(imported_dose_value, 8),
            unit=DoseUnit.MG_PER_KG_DAY,
        )
    if surrogate_result.external_dose is not None:
        route_metrics["surrogateExternalDoseMgPerKgDay"] = round(
            surrogate_result.external_dose.value,
            8,
        )
        if imported_dose_value is not None:
            delta = imported_dose_value - surrogate_result.external_dose.value
            route_metrics["importedDoseDeltaVsSurrogateMgPerKgDay"] = round(delta, 8)
            if surrogate_result.external_dose.value > 0.0:
                ratio = imported_dose_value / surrogate_result.external_dose.value
                route_metrics["importedDoseRatioVsSurrogate"] = round(ratio, 8)
                if ratio > 2.0 or ratio < 0.5:
                    quality_flags.append(
                        QualityFlag(
                            code="worker_art_external_result_surrogate_divergence",
                            severity=Severity.WARNING,
                            message=(
                                "The imported external ART dose diverged materially from the "
                                "current internal surrogate execution result."
                            ),
                        )
                    )

    limitations.extend(
        [
            LimitationNote(
                code="worker_art_external_result_not_independently_verified",
                severity=Severity.WARNING,
                message=(
                    "Direct-Use Exposure MCP normalized the external ART result but did not "
                    "independently re-run or verify the external occupational solver."
                ),
            ),
            LimitationNote(
                code="worker_art_external_result_not_compliance_ready",
                severity=Severity.WARNING,
                message=(
                    "Treat the imported ART result as a structured occupational refinement "
                    "artifact for expert review, not as a final compliance determination."
                ),
            ),
        ]
    )

    ready_for_execution = (
        imported_dose_value is not None and external_result.result_status != "failed"
    )
    ready_for_execution = ready_for_execution and not any(
        item.severity == Severity.ERROR for item in limitations
    )
    manual_review_required = (
        ingest_result.manual_review_required
        or external_result.result_status != "completed"
        or bool(external_result.quality_notes)
        or (
            bool(result_payload)
            and any(
                flag.code.startswith("worker_art_external_result_payload_")
                and flag.severity == Severity.WARNING
                for flag in quality_flags
            )
        )
        or (not external_result.raw_artifacts and not result_payload)
    )

    fit_for_purpose = FitForPurpose(
        label="worker_inhalation_external_art_import",
        suitable_for=[
            "external occupational inhalation result normalization",
            "ART-aligned worker inhalation refinement with preserved screening comparison",
            "PBPK-ready external inhalation dose handoff after expert review",
        ],
        not_suitable_for=[
            "independent solver verification",
            "final occupational compliance determination",
            "raw ART report replacement",
        ],
    )
    tier_semantics = TierSemantics(
        tier_claimed=TierLevel.TIER_2,
        tier_earned=TierLevel.TIER_2 if ready_for_execution else TierLevel.TIER_0,
        tier_rationale=(
            "This result imports an external occupational inhalation execution payload and "
            "normalizes it into the governed MCP execution contract while preserving the "
            "internal screening baseline for comparison."
        ),
        assumption_checks_passed=ready_for_execution,
        required_caveats=[
            "Keep the external raw artifacts, quality notes, and import provenance attached to "
            "any downstream PBPK or NGRA use.",
            "Treat the imported dose as externally produced occupational model output that was "
            "normalized here, not independently solved here.",
        ],
        forbidden_interpretations=[
            "Do not treat this import as independent validation of the external solver.",
            "Do not use the normalized output as a final occupational compliance conclusion.",
        ],
    )
    interpretation_notes = [
        "The imported worker inhalation dose came from the external ART-side result when "
        "available, with internal derivation used only when the external result omitted a "
        "normalized dose.",
        "The preserved screening baseline remains attached for context and comparison, not as "
        "a replacement for the imported Tier 2 result.",
        "Review the attached raw artifacts before relying on the imported concentration or dose.",
    ]

    result = WorkerInhalationTier2ExecutionResult(
        supported_by_adapter=True,
        ready_for_execution=ready_for_execution,
        manual_review_required=manual_review_required,
        resolved_adapter="art_worker_inhalation_external_adapter",
        target_model_family=adapter_request.target_model_family,
        chemical_id=chemical_id,
        chemical_name=chemical_name,
        baseline_dose=baseline_dose,
        external_dose=external_dose,
        product_use_profile=product_profile,
        population_profile=population_profile,
        task_context=task_context,
        art_task_envelope=envelope,
        execution_overrides=None,
        route_metrics=route_metrics,
        assumptions=assumptions,
        quality_flags=quality_flags,
        limitations=limitations,
        provenance=_external_import_provenance(registry, generated_at=generated_at),
        fit_for_purpose=fit_for_purpose,
        tier_semantics=tier_semantics,
        validation_summary=None,
        interpretation_notes=interpretation_notes,
    )
    return result.model_copy(
        update={
            "validation_summary": _build_worker_inhalation_external_import_validation_summary(
                result,
                external_result,
            )
        },
        deep=True,
    )
