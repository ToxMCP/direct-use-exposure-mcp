"""Suite integration helpers for CompTox, ToxClaw, and PBPK-facing flows."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Literal

from pydantic import Field

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ensure
from exposure_scenario_mcp.models import (
    AggregateExposureSummary,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExportToxClawEvidenceBundleRequest,
    ExportToxClawRefinementBundleRequest,
    ExposureScenario,
    ExposureScenarioRequest,
    FitForPurpose,
    LimitationNote,
    ProvenanceBundle,
    QualityFlag,
    Route,
    ScalarValue,
    ScenarioComparisonRecord,
    Severity,
    StrictModel,
)
from exposure_scenario_mcp.runtime import compare_scenarios, export_pbpk_input


def _sorted_json(value):
    if isinstance(value, list):
        return [_sorted_json(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sorted_json(item)
            for key, item in sorted(value.items(), key=lambda entry: entry[0])
        }
    return value


def _stable_json_dumps(value: dict) -> str:
    return json.dumps(_sorted_json(value), indent=2)


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _hash_value(value: dict) -> str:
    return _hash_text(_stable_json_dumps(value))


def _deterministic_id(prefix: str, parts: list[str]) -> str:
    digest = sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return f"{prefix}-{digest.hexdigest()[:16]}"


def _normalize_section_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "section"


def _resolved_body_weight_kg(scenario: ExposureScenario) -> float | None:
    if scenario.population_profile.body_weight_kg is not None:
        return scenario.population_profile.body_weight_kg
    for assumption in scenario.assumptions:
        if assumption.name == "body_weight_kg" and assumption.value is not None:
            return float(assumption.value)
    return None


def _scenario_summary(scenario: ExposureScenario) -> str:
    return (
        f"{scenario.route.value} {scenario.scenario_class.value} scenario with "
        f"external dose {scenario.external_dose.value} {scenario.external_dose.unit.value}"
    )


def _scenario_timing_pattern(scenario: ExposureScenario) -> str:
    duration = scenario.product_use_profile.exposure_duration_hours
    if duration is not None:
        return (
            f"{scenario.product_use_profile.use_events_per_day:g} events/day "
            f"for {duration:g} hour(s) per event"
        )
    return f"{scenario.product_use_profile.use_events_per_day:g} events/day"


def _life_stage(population_group: str) -> str:
    normalized = population_group.strip().lower()
    if "infant" in normalized:
        return "infant"
    if "child" in normalized:
        return "child"
    if "adolescent" in normalized or "teen" in normalized:
        return "adolescent"
    if "preg" in normalized:
        return "adult"
    return "adult"


def _chemical_identity_context(scenario: ExposureScenario) -> dict[str, ScalarValue]:
    preferred_name = scenario.chemical_name or scenario.chemical_id
    return {
        "available": scenario.chemical_name is not None,
        "chemicalId": scenario.chemical_id,
        "preferredName": preferred_name,
        "label": preferred_name,
        "sourceModule": "exposure-scenario-mcp",
        "summary": f"Identity context derived from exposure scenario {scenario.scenario_id}.",
    }


def _upstream_uncertainty_summary(scenario: ExposureScenario) -> dict[str, ScalarValue]:
    issue_count = len(scenario.limitations) + len(scenario.quality_flags)
    return {
        "source": "exposure-scenario-mcp",
        "issueCount": issue_count,
        "hasResidualUncertainty": bool(issue_count),
        "summary": (
            "Exposure-scenario assumptions, limitations, and quality flags remain upstream "
            "and must be preserved during PBPK interpretation."
        ),
    }


TOXCLAW_REFINE_EXPOSURE_RECOMMENDATION = (
    "Refine exposure characterization before relying on the screening recommendation."
)


def _comparison_delta_direction(
    comparison: ScenarioComparisonRecord,
) -> Literal["increase", "decrease", "no_change"]:
    if comparison.absolute_delta > 0:
        return "increase"
    if comparison.absolute_delta < 0:
        return "decrease"
    return "no_change"


def _comparison_delta_note(comparison: ScenarioComparisonRecord) -> str:
    if comparison.percent_delta is None:
        return "Baseline dose was zero; percentage delta is undefined."
    if comparison.percent_delta > 0:
        return f"Comparison dose increased by {comparison.percent_delta:.2f}% relative to baseline."
    if comparison.percent_delta < 0:
        return (
            f"Comparison dose decreased by {abs(comparison.percent_delta):.2f}% "
            "relative to baseline."
        )
    return "Comparison dose is numerically identical to the baseline."


def _workflow_action_note(
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"],
) -> str:
    if workflow_action == "route_recalculation":
        return (
            "This comparison represents a route-specific recalculation candidate and should "
            "remain an exposure-context refinement trace only."
        )
    if workflow_action == "aggregate_variant":
        return (
            "This comparison represents an aggregate-variant refinement and should be "
            "interpreted alongside the component scenarios."
        )
    return (
        "This comparison should inform exposure refinement only; ToxClaw remains responsible "
        "for the final recommendation."
    )


def _comparison_summary(
    comparison: ScenarioComparisonRecord,
    workflow_action: Literal["scenario_comparison", "route_recalculation", "aggregate_variant"],
) -> str:
    action_label = workflow_action.replace("_", " ")
    direction = _comparison_delta_direction(comparison)
    if comparison.percent_delta is None:
        return (
            f"Exposure {action_label} recorded absolute delta "
            f"{comparison.absolute_delta} {comparison.baseline_dose.unit.value}."
        )
    if direction == "increase":
        return (
            f"Exposure {action_label} increased external dose by "
            f"{comparison.percent_delta:.2f}% relative to baseline."
        )
    if direction == "decrease":
        return (
            f"Exposure {action_label} decreased external dose by "
            f"{abs(comparison.percent_delta):.2f}% relative to baseline."
        )
    return f"Exposure {action_label} produced no numerical dose change relative to baseline."


def _route_recalculation_tool_name(
    scenario: ExposureScenario,
) -> Literal[
    "exposure_build_screening_exposure_scenario",
    "exposure_build_inhalation_screening_scenario",
]:
    if scenario.route == Route.INHALATION:
        return "exposure_build_inhalation_screening_scenario"
    return "exposure_build_screening_exposure_scenario"


class CompToxChemicalRecord(StrictModel):
    schema_version: Literal["compToxChemicalRecord.v1"] = "compToxChemicalRecord.v1"
    chemical_id: str = Field(..., description="Stable CompTox chemical identifier.")
    preferred_name: str = Field(..., description="Preferred chemical name.")
    casrn: str | None = Field(default=None, description="CAS Registry Number when known.")
    product_use_categories: list[str] = Field(
        default_factory=list,
        description="Relevant product-use categories discovered upstream.",
    )
    physchem_summary: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description="Physicochemical context that can support downstream scenario interpretation.",
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        description="Upstream evidence or record identifiers backing the CompTox record.",
    )


class ToxClawEvidenceEnvelope(StrictModel):
    schema_version: Literal["toxclawEvidenceEnvelope.v1"] = "toxclawEvidenceEnvelope.v1"
    source_module: Literal["exposure_scenario_mcp"] = "exposure_scenario_mcp"
    record_kind: str = Field(..., description="Scenario, aggregate summary, or comparison record.")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    context_of_use: str = Field(..., description="Why the evidence is being emitted.")
    route: str | None = Field(default=None, description="Primary route when applicable.")
    scenario_class: str | None = Field(
        default=None, description="Primary scenario class when applicable."
    )
    summary: str = Field(..., description="One-line evidence summary for orchestration.")
    fit_for_purpose: FitForPurpose | None = Field(
        default=None,
        description="Fit-for-purpose metadata if the wrapped record has it.",
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list,
        description="Limitations preserved from the wrapped record.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        description="Quality flags preserved from the wrapped record.",
    )
    provenance: ProvenanceBundle = Field(..., description="Provenance of the wrapped record.")
    payload: dict = Field(..., description="Wrapped record payload.")


class ToxClawEvidenceRecord(StrictModel):
    schema_version: Literal["toxclawEvidenceRecord.v1"] = Field(
        default="toxclawEvidenceRecord.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    content_hash: str = Field(..., alias="contentHash")
    data_classification: Literal["public", "internal", "restricted", "regulated"] = Field(
        ..., alias="dataClassification"
    )
    evidence_id: str = Field(..., alias="evidenceId")
    quality_flag: str | None = Field(default=None, alias="qualityFlag")
    raw_pointer: str | None = Field(default=None, alias="rawPointer")
    redaction_status: str | None = Field(default=None, alias="redactionStatus")
    retrieved_at: str = Field(..., alias="retrievedAt")
    run_id: str | None = Field(default=None, alias="runId")
    source: str = Field(..., description="ToxClaw evidence source string.")
    source_ref: str = Field(..., alias="sourceRef")
    summary: str = Field(..., description="Human-readable evidence summary.")
    tags: list[str] = Field(default_factory=list)
    trust_label: Literal[
        "module-output", "untrusted-document", "untrusted-external-data"
    ] = Field(..., alias="trustLabel")
    type: str = Field(..., description="ToxClaw evidence type label.")


class ToxClawReportEvidenceReference(StrictModel):
    schema_version: Literal["toxclawReportEvidenceReference.v1"] = Field(
        default="toxclawReportEvidenceReference.v1", alias="schemaVersion"
    )
    content_hash: str = Field(..., alias="contentHash")
    evidence_id: str = Field(..., alias="evidenceId")
    quality_flag: str | None = Field(default=None, alias="qualityFlag")
    raw_pointer: str | None = Field(default=None, alias="rawPointer")
    redaction_status: str | None = Field(default=None, alias="redactionStatus")
    retrieved_at: str = Field(..., alias="retrievedAt")
    source: str
    source_ref: str = Field(..., alias="sourceRef")
    summary: str
    tags: list[str] = Field(default_factory=list)
    trust_label: Literal[
        "module-output", "untrusted-document", "untrusted-external-data"
    ] = Field(..., alias="trustLabel")
    type: str


class ToxClawReportClaim(StrictModel):
    schema_version: Literal["toxclawReportClaim.v1"] = Field(
        default="toxclawReportClaim.v1", alias="schemaVersion"
    )
    claim_id: str = Field(..., alias="claimId")
    confidence: Literal["heuristic", "provisional", "supported", "unverified"]
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    text: str


class ToxClawReportSection(StrictModel):
    schema_version: Literal["toxclawReportSection.v1"] = Field(
        default="toxclawReportSection.v1", alias="schemaVersion"
    )
    body: str
    claims: list[ToxClawReportClaim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    section_key: str = Field(..., alias="sectionKey")
    title: str


class ToxClawEvidenceBundle(StrictModel):
    schema_version: Literal["toxclawEvidenceBundle.v1"] = Field(
        default="toxclawEvidenceBundle.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    report_id: str = Field(..., alias="reportId")
    context_of_use: str = Field(..., alias="contextOfUse")
    source_module: Literal["exposure-scenario-mcp"] = Field(
        default="exposure-scenario-mcp", alias="sourceModule"
    )
    summary: str
    evidence_record: ToxClawEvidenceRecord = Field(..., alias="evidenceRecord")
    report_evidence_reference: ToxClawReportEvidenceReference = Field(
        ..., alias="reportEvidenceReference"
    )
    report_section: ToxClawReportSection = Field(..., alias="reportSection")


class ExposureWorkflowHook(StrictModel):
    schema_version: Literal["exposureWorkflowHook.v1"] = Field(
        default="exposureWorkflowHook.v1", alias="schemaVersion"
    )
    action: Literal[
        "scenario_comparison", "route_recalculation", "aggregate_variant", "pbpk_export"
    ]
    tool_name: Literal[
        "exposure_compare_exposure_scenarios",
        "exposure_build_screening_exposure_scenario",
        "exposure_build_inhalation_screening_scenario",
        "exposure_build_aggregate_exposure_scenario",
        "exposure_export_pbpk_external_import_bundle",
    ] = Field(..., alias="toolName")
    when_to_use: str = Field(..., alias="whenToUse")
    required_inputs: list[str] = Field(default_factory=list, alias="requiredInputs")


class ToxClawExposureRefinementSignal(StrictModel):
    schema_version: Literal["toxclawExposureRefinementSignal.v1"] = Field(
        default="toxclawExposureRefinementSignal.v1", alias="schemaVersion"
    )
    recommendation: Literal["refine_exposure"] = "refine_exposure"
    refinement_recommendation: str = Field(
        default=TOXCLAW_REFINE_EXPOSURE_RECOMMENDATION,
        alias="refinementRecommendation",
    )
    loe_candidate_keys: list[str] = Field(
        default_factory=lambda: ["exposure_context"],
        alias="loeCandidateKeys",
    )
    workflow_action: Literal[
        "scenario_comparison", "route_recalculation", "aggregate_variant"
    ] = Field(..., alias="workflowAction")
    route_changed: bool = Field(..., alias="routeChanged")
    changed_assumption_names: list[str] = Field(
        default_factory=list, alias="changedAssumptionNames"
    )
    changed_assumption_count: int = Field(..., alias="changedAssumptionCount")
    dose_delta_direction: Literal["increase", "decrease", "no_change"] = Field(
        ..., alias="doseDeltaDirection"
    )
    percent_delta: float | None = Field(default=None, alias="percentDelta")
    material_change: bool = Field(..., alias="materialChange")
    boundary_note: str = Field(..., alias="boundaryNote")
    workflow_hooks: list[ExposureWorkflowHook] = Field(
        default_factory=list, alias="workflowHooks"
    )


class ToxClawExposureRefinementBundle(StrictModel):
    schema_version: Literal["toxclawExposureRefinementBundle.v1"] = Field(
        default="toxclawExposureRefinementBundle.v1", alias="schemaVersion"
    )
    case_id: str = Field(..., alias="caseId")
    report_id: str = Field(..., alias="reportId")
    context_of_use: str = Field(..., alias="contextOfUse")
    source_module: Literal["exposure-scenario-mcp"] = Field(
        default="exposure-scenario-mcp", alias="sourceModule"
    )
    workflow_action: Literal[
        "scenario_comparison", "route_recalculation", "aggregate_variant"
    ] = Field(..., alias="workflowAction")
    summary: str
    baseline_scenario: ExposureScenario = Field(..., alias="baselineScenario")
    comparison_scenario: ExposureScenario = Field(..., alias="comparisonScenario")
    comparison_record: ScenarioComparisonRecord = Field(..., alias="comparisonRecord")
    evidence_record: ToxClawEvidenceRecord = Field(..., alias="evidenceRecord")
    report_evidence_reference: ToxClawReportEvidenceReference = Field(
        ..., alias="reportEvidenceReference"
    )
    report_section: ToxClawReportSection = Field(..., alias="reportSection")
    refinement_signal: ToxClawExposureRefinementSignal = Field(
        ..., alias="refinementSignal"
    )


class PbpkExternalArtifact(StrictModel):
    type: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    checksum: str | None = None
    title: str | None = None


class PbpkExternalImportBundle(StrictModel):
    schema_version: Literal["pbpkExternalImportBundle.v1"] = Field(
        default="pbpkExternalImportBundle.v1", alias="schemaVersion"
    )
    source_platform: str = Field(..., alias="sourcePlatform")
    source_version: str | None = Field(default=None, alias="sourceVersion")
    model_name: str | None = Field(default=None, alias="modelName")
    model_type: str = Field(..., alias="modelType")
    execution_date: str | None = Field(default=None, alias="executionDate")
    run_id: str | None = Field(default=None, alias="runId")
    operator: str | None = None
    sponsor: str | None = None
    raw_artifacts: list[PbpkExternalArtifact] = Field(default_factory=list, alias="rawArtifacts")
    assessment_context: dict = Field(default_factory=dict, alias="assessmentContext")
    chemical_identity: dict = Field(default_factory=dict, alias="chemicalIdentity")
    supporting_handoffs: dict = Field(default_factory=dict, alias="supportingHandoffs")
    internal_exposure: dict = Field(default_factory=dict, alias="internalExposure")
    qualification: dict = Field(default_factory=dict)
    uncertainty: dict = Field(default_factory=dict)
    uncertainty_register: dict = Field(default_factory=dict, alias="uncertaintyRegister")
    pod: dict = Field(default_factory=dict)
    true_dose_adjustment: dict = Field(default_factory=dict, alias="trueDoseAdjustment")
    comparison_metric: str = Field(default="cmax", alias="comparisonMetric")


class PbpkExternalImportRequest(StrictModel):
    source_platform: str = Field(..., alias="sourcePlatform")
    source_version: str | None = Field(default=None, alias="sourceVersion")
    model_name: str | None = Field(default=None, alias="modelName")
    model_type: str = Field(..., alias="modelType")
    execution_date: str | None = Field(default=None, alias="executionDate")
    run_id: str | None = Field(default=None, alias="runId")
    operator: str | None = None
    sponsor: str | None = None
    raw_artifacts: list[PbpkExternalArtifact] = Field(default_factory=list, alias="rawArtifacts")
    assessment_context: dict = Field(default_factory=dict, alias="assessmentContext")
    internal_exposure: dict = Field(default_factory=dict, alias="internalExposure")
    qualification: dict = Field(default_factory=dict)
    uncertainty: dict = Field(default_factory=dict)
    uncertainty_register: dict = Field(default_factory=dict, alias="uncertaintyRegister")
    pod: dict = Field(default_factory=dict)
    true_dose_adjustment: dict = Field(default_factory=dict, alias="trueDoseAdjustment")
    comparison_metric: str = Field(default="cmax", alias="comparisonMetric")


class PbpkExternalImportToolCall(StrictModel):
    schema_version: Literal["pbpkExternalImportToolCall.v1"] = Field(
        default="pbpkExternalImportToolCall.v1", alias="schemaVersion"
    )
    tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="toolName"
    )
    arguments: PbpkExternalImportRequest


class ToxClawPbpkModuleParams(StrictModel):
    schema_version: Literal["toxclawPbpkModuleParams.v1"] = Field(
        default="toxclawPbpkModuleParams.v1", alias="schemaVersion"
    )
    ingest_tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="ingestToolName"
    )
    arguments: PbpkExternalImportRequest
    chemical_identity: dict = Field(default_factory=dict, alias="chemicalIdentity")
    supporting_handoffs: dict = Field(default_factory=dict, alias="supportingHandoffs")


class PbpkCompatibilityReport(StrictModel):
    schema_version: Literal["pbpkCompatibilityReport.v1"] = "pbpkCompatibilityReport.v1"
    source_scenario_id: str = Field(..., description="Source scenario identifier.")
    compatible: bool = Field(..., description="Whether the object is PBPK-compatible.")
    target_tool: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle",
        description="PBPK MCP tool evaluated for downstream readiness.",
    )
    checked_route: Route = Field(..., description="Route checked for compatibility.")
    checked_dose_unit: str = Field(..., description="Dose unit checked for compatibility.")
    ready_for_external_pbpk_import: bool = Field(
        ...,
        description=(
            "Whether the scenario alone contains enough data to populate the PBPK external-import "
            "path without additional PBPK execution outputs."
        ),
    )
    supported_pbpk_objects: list[str] = Field(
        default_factory=list,
        description="Published PBPK object families this scenario can prefill or support.",
    )
    missing_external_bundle_fields: list[str] = Field(
        default_factory=list,
        description="PBPK external-import fields still missing for a richer downstream handoff.",
    )
    checked_fields: list[str] = Field(
        default_factory=list,
        description="Fields explicitly checked during compatibility validation.",
    )
    issues: list[LimitationNote] = Field(
        default_factory=list,
        description="Compatibility issues or warnings.",
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="Concrete actions to strengthen the PBPK handoff.",
    )


class PbpkExternalImportPackage(StrictModel):
    schema_version: Literal["pbpkExternalImportPackage.v1"] = Field(
        default="pbpkExternalImportPackage.v1", alias="schemaVersion"
    )
    ingest_tool_name: Literal["ingest_external_pbpk_bundle"] = Field(
        default="ingest_external_pbpk_bundle", alias="ingestToolName"
    )
    bundle: PbpkExternalImportBundle
    request_payload: PbpkExternalImportRequest = Field(..., alias="requestPayload")
    tool_call: PbpkExternalImportToolCall = Field(..., alias="toolCall")
    toxclaw_module_params: ToxClawPbpkModuleParams = Field(..., alias="toxclawModuleParams")
    compatibility_report: PbpkCompatibilityReport = Field(..., alias="compatibilityReport")


def apply_comptox_enrichment(
    request: ExposureScenarioRequest,
    record: CompToxChemicalRecord,
) -> ExposureScenarioRequest:
    """Merge CompTox identity and discovery context into a scenario request."""

    ensure(
        request.chemical_id == record.chemical_id,
        "comptox_identity_mismatch",
        "CompTox enrichment record does not match the request chemical_id.",
        suggestion=(
            "Pass a CompTox record for the same chemical referenced by the scenario request."
        ),
        request_chemical_id=request.chemical_id,
        comp_tox_chemical_id=record.chemical_id,
    )

    updated_product_profile = request.product_use_profile
    if (
        record.product_use_categories
        and updated_product_profile.product_category not in record.product_use_categories
    ):
        updated_product_profile = updated_product_profile.model_copy(
            update={"product_category": record.product_use_categories[0]}
        )

    overrides = dict(request.assumption_overrides)
    if record.casrn:
        overrides["comptox_casrn"] = record.casrn
    if record.evidence_sources:
        overrides["comptox_primary_evidence"] = record.evidence_sources[0]

    return request.model_copy(
        update={
            "chemical_name": request.chemical_name or record.preferred_name,
            "product_use_profile": updated_product_profile,
            "assumption_overrides": overrides,
        }
    )


def build_toxclaw_evidence_envelope(
    payload: ExposureScenario | AggregateExposureSummary | ScenarioComparisonRecord,
    context_of_use: str,
) -> ToxClawEvidenceEnvelope:
    """Wrap exposure outputs in a ToxClaw-friendly evidence envelope."""

    if isinstance(payload, ExposureScenario):
        summary = (
            f"{payload.route.value} {payload.scenario_class.value} scenario "
            f"with external dose {payload.external_dose.value} {payload.external_dose.unit.value}"
        )
        return ToxClawEvidenceEnvelope(
            record_kind="exposureScenario",
            chemical_id=payload.chemical_id,
            context_of_use=context_of_use,
            route=payload.route.value,
            scenario_class=payload.scenario_class.value,
            summary=summary,
            fit_for_purpose=payload.fit_for_purpose,
            limitations=payload.limitations,
            quality_flags=payload.quality_flags,
            provenance=payload.provenance,
            payload=payload.model_dump(mode="json"),
        )

    if isinstance(payload, AggregateExposureSummary):
        summary = (
            f"aggregate screening summary across {len(payload.component_scenarios)} "
            "component scenarios"
        )
        return ToxClawEvidenceEnvelope(
            record_kind="aggregateExposureSummary",
            chemical_id=payload.chemical_id,
            context_of_use=context_of_use,
            route=None,
            scenario_class=payload.scenario_class,
            summary=summary,
            fit_for_purpose=None,
            limitations=payload.limitations,
            quality_flags=payload.quality_flags,
            provenance=payload.provenance,
            payload=payload.model_dump(mode="json"),
        )

    summary = (
        f"scenario comparison with absolute delta {payload.absolute_delta} "
        f"{payload.baseline_dose.unit.value}"
    )
    return ToxClawEvidenceEnvelope(
        record_kind="scenarioComparisonRecord",
        chemical_id=payload.chemical_id,
        context_of_use=context_of_use,
        route=None,
        scenario_class=None,
        summary=summary,
        fit_for_purpose=None,
        limitations=[],
        quality_flags=[],
        provenance=payload.provenance,
        payload=payload.model_dump(mode="json"),
    )


def build_toxclaw_evidence_bundle(
    params: ExportToxClawEvidenceBundleRequest,
) -> ToxClawEvidenceBundle:
    """Export a deterministic ToxClaw-ready evidence record and report section."""

    scenario = params.scenario
    evidence_payload = scenario.model_dump(mode="json", by_alias=True)
    content_hash = _hash_value(evidence_payload)
    summary = _scenario_summary(scenario)
    evidence_id = _deterministic_id(
        "evidence",
        [
            params.case_id,
            "exposure-scenario-mcp",
            scenario.scenario_id,
            scenario.provenance.generated_at,
            content_hash,
        ],
    )
    tags = sorted(
        {
            "exposure-scenario",
            scenario.route.value,
            scenario.scenario_class.value,
            scenario.product_use_profile.product_category,
            scenario.population_profile.population_group,
        }
    )
    evidence_record = ToxClawEvidenceRecord(
        case_id=params.case_id,
        content_hash=content_hash,
        data_classification=params.data_classification,
        evidence_id=evidence_id,
        quality_flag=scenario.quality_flags[0].code if scenario.quality_flags else None,
        retrieved_at=scenario.provenance.generated_at,
        run_id=params.run_id,
        source="exposure-scenario-mcp",
        source_ref=scenario.scenario_id,
        summary=summary,
        tags=tags,
        trust_label=params.trust_label,
        type="exposure-scenario",
    )
    evidence_reference = ToxClawReportEvidenceReference(
        content_hash=evidence_record.content_hash,
        evidence_id=evidence_record.evidence_id,
        quality_flag=evidence_record.quality_flag,
        raw_pointer=evidence_record.raw_pointer,
        redaction_status=evidence_record.redaction_status,
        retrieved_at=evidence_record.retrieved_at,
        source=evidence_record.source,
        source_ref=evidence_record.source_ref,
        summary=evidence_record.summary,
        tags=evidence_record.tags,
        trust_label=evidence_record.trust_label,
        type=evidence_record.type,
    )

    claim_texts = [
        (
            f"The {scenario.route.value} {scenario.scenario_class.value} scenario estimates "
            f"{scenario.external_dose.value} {scenario.external_dose.unit.value} external dose."
        ),
        (
            f"The scenario represents {scenario.population_profile.population_group} use of "
            f"{scenario.product_use_profile.product_category} with "
            f"{scenario.product_use_profile.use_events_per_day:g} event(s) per day."
        ),
    ]
    if scenario.limitations:
        claim_texts.append(
            
                f"The scenario includes {len(scenario.limitations)} explicit limitation(s) "
                "that require review."
            
        )
    else:
        claim_texts.append(
            
                f"The scenario is labeled {scenario.fit_for_purpose.label} for "
                "external-dose screening use."
            
        )

    section_key = _normalize_section_key(params.section_key)
    claims = [
        ToxClawReportClaim(
            claim_id=_deterministic_id(
                "claim",
                [params.report_id, section_key, str(index), _hash_text(text)],
            ),
            confidence="supported",
            evidence_ids=[evidence_id],
            text=text,
        )
        for index, text in enumerate(claim_texts, start=1)
    ]
    report_section = ToxClawReportSection(
        body="\n".join(f"- {text}" for text in claim_texts),
        claims=claims,
        evidence_ids=[evidence_id],
        section_key=section_key,
        title=params.section_title,
    )
    return ToxClawEvidenceBundle(
        case_id=params.case_id,
        report_id=params.report_id,
        context_of_use=params.context_of_use,
        summary=summary,
        evidence_record=evidence_record,
        report_evidence_reference=evidence_reference,
        report_section=report_section,
    )


def build_toxclaw_refinement_bundle(
    params: ExportToxClawRefinementBundleRequest,
) -> ToxClawExposureRefinementBundle:
    """Export a ToxClaw-facing refinement delta with evidence and workflow hooks."""

    comparison = compare_scenarios(
        CompareExposureScenariosInput(
            baseline=params.baseline,
            comparison=params.comparison,
        ),
        DefaultsRegistry.load(),
    )
    changed_assumption_names = [item.name for item in comparison.changed_assumptions]
    summary = _comparison_summary(comparison, params.workflow_action)
    evidence_payload = {
        "workflowAction": params.workflow_action,
        "baselineScenario": params.baseline.model_dump(mode="json", by_alias=True),
        "comparisonScenario": params.comparison.model_dump(mode="json", by_alias=True),
        "comparisonRecord": comparison.model_dump(mode="json", by_alias=True),
    }
    content_hash = _hash_value(evidence_payload)
    evidence_id = _deterministic_id(
        "evidence",
        [
            params.case_id,
            "exposure-scenario-mcp",
            params.baseline.scenario_id,
            params.comparison.scenario_id,
            content_hash,
        ],
    )
    tags = sorted(
        {
            "exposure-refinement",
            "refinement",
            "scenario-comparison",
            params.workflow_action,
            params.baseline.route.value,
            params.comparison.route.value,
            params.baseline.product_use_profile.product_category,
            params.comparison.product_use_profile.product_category,
            *(["route-changed"] if params.baseline.route != params.comparison.route else []),
        }
    )
    source_ref = (
        f"{params.baseline.scenario_id}::{params.comparison.scenario_id}"
    )
    evidence_record = ToxClawEvidenceRecord(
        case_id=params.case_id,
        content_hash=content_hash,
        data_classification=params.data_classification,
        evidence_id=evidence_id,
        quality_flag=None,
        retrieved_at=comparison.provenance.generated_at,
        run_id=params.run_id,
        source="exposure-scenario-mcp",
        source_ref=source_ref,
        summary=summary,
        tags=tags,
        trust_label=params.trust_label,
        type="exposure-refinement",
    )
    evidence_reference = ToxClawReportEvidenceReference(
        content_hash=evidence_record.content_hash,
        evidence_id=evidence_record.evidence_id,
        quality_flag=evidence_record.quality_flag,
        raw_pointer=evidence_record.raw_pointer,
        redaction_status=evidence_record.redaction_status,
        retrieved_at=evidence_record.retrieved_at,
        source=evidence_record.source,
        source_ref=evidence_record.source_ref,
        summary=evidence_record.summary,
        tags=evidence_record.tags,
        trust_label=evidence_record.trust_label,
        type=evidence_record.type,
    )
    claim_texts = [
        (
            f"Baseline scenario {comparison.baseline_scenario_id} estimates "
            f"{comparison.baseline_dose.value} {comparison.baseline_dose.unit.value}; "
            f"comparison scenario {comparison.comparison_scenario_id} estimates "
            f"{comparison.comparison_dose.value} {comparison.comparison_dose.unit.value}."
        ),
        _comparison_delta_note(comparison),
        (
            f"Changed assumptions: {', '.join(changed_assumption_names)}."
            if changed_assumption_names
            else "No assumption deltas were detected between the compared scenarios."
        ),
        _workflow_action_note(params.workflow_action),
    ]
    if params.baseline.route != params.comparison.route:
        claim_texts.append(
            "Routes differ between scenarios; interpret the delta as an audit trace, not a "
            "like-for-like route refinement."
        )

    section_key = _normalize_section_key(params.section_key)
    claims = [
        ToxClawReportClaim(
            claim_id=_deterministic_id(
                "claim",
                [params.report_id, section_key, str(index), _hash_text(text)],
            ),
            confidence="supported",
            evidence_ids=[evidence_id],
            text=text,
        )
        for index, text in enumerate(claim_texts, start=1)
    ]
    report_section = ToxClawReportSection(
        body="\n".join(f"- {text}" for text in claim_texts),
        claims=claims,
        evidence_ids=[evidence_id],
        section_key=section_key,
        title=params.section_title,
    )
    workflow_hooks = [
        ExposureWorkflowHook(
            action="scenario_comparison",
            tool_name="exposure_compare_exposure_scenarios",
            when_to_use=(
                "Use after generating a revised scenario to quantify the external-dose delta "
                "without making risk or PBPK claims."
            ),
            required_inputs=["baseline scenario", "comparison scenario"],
        ),
        ExposureWorkflowHook(
            action="route_recalculation",
            tool_name=_route_recalculation_tool_name(params.comparison),
            when_to_use=(
                "Use when ToxClaw needs a route-specific recomputation of the candidate "
                "scenario before comparing it against the current screening baseline."
            ),
            required_inputs=[
                "chemical_id",
                "route-specific product_use_profile",
                "population_profile",
            ],
        ),
        ExposureWorkflowHook(
            action="aggregate_variant",
            tool_name="exposure_build_aggregate_exposure_scenario",
            when_to_use=(
                "Use when the refinement question depends on a combined multi-component "
                "or multi-route screening variant."
            ),
            required_inputs=["shared chemical_id", "component scenarios", "aggregate label"],
        ),
        ExposureWorkflowHook(
            action="pbpk_export",
            tool_name="exposure_export_pbpk_external_import_bundle",
            when_to_use=(
                "Use only after selecting the scenario that should advance from external-dose "
                "refinement into PBPK translation."
            ),
            required_inputs=["selected source scenario"],
        ),
    ]
    refinement_signal = ToxClawExposureRefinementSignal(
        workflow_action=params.workflow_action,
        route_changed=params.baseline.route != params.comparison.route,
        changed_assumption_names=changed_assumption_names,
        changed_assumption_count=len(changed_assumption_names),
        dose_delta_direction=_comparison_delta_direction(comparison),
        percent_delta=comparison.percent_delta,
        material_change=bool(
            comparison.absolute_delta
            or changed_assumption_names
            or params.baseline.route != params.comparison.route
        ),
        boundary_note=(
            "This bundle supports exposure-context refinement only. ToxClaw still owns "
            "line-of-evidence synthesis and the final recommendation."
        ),
        workflow_hooks=workflow_hooks,
    )
    return ToxClawExposureRefinementBundle(
        case_id=params.case_id,
        report_id=params.report_id,
        context_of_use=params.context_of_use,
        workflow_action=params.workflow_action,
        summary=summary,
        baseline_scenario=params.baseline,
        comparison_scenario=params.comparison,
        comparison_record=comparison,
        evidence_record=evidence_record,
        report_evidence_reference=evidence_reference,
        report_section=report_section,
        refinement_signal=refinement_signal,
    )


def check_pbpk_compatibility(scenario: ExposureScenario) -> PbpkCompatibilityReport:
    """Check whether a source exposure scenario is mechanically ready for PBPK export."""

    issues: list[LimitationNote] = []
    missing_fields: list[str] = []
    if scenario.external_dose.unit.value not in {"mg/kg-day", "mg/day", "mg/event"}:
        issues.append(
            LimitationNote(
                code="pbpk_unit_unsupported",
                severity=Severity.ERROR,
                message=(
                    "PBPK handoff requires canonical external dose units of "
                    "mg/kg-day, mg/day, or mg/event."
                ),
            )
        )
    if scenario.product_use_profile.use_events_per_day <= 0:
        issues.append(
            LimitationNote(
                code="pbpk_events_invalid",
                severity=Severity.ERROR,
                message="PBPK handoff requires a positive use_events_per_day value.",
            )
        )
    if _resolved_body_weight_kg(scenario) is None:
        missing_fields.append("assessmentContext.doseScenario.bodyWeightKg")
        issues.append(
            LimitationNote(
                code="pbpk_body_weight_missing",
                severity=Severity.ERROR,
                message=(
                    "PBPK handoff requires a resolved body_weight_kg in the population profile."
                ),
            )
        )
    if (
        scenario.route == Route.INHALATION
        and scenario.product_use_profile.exposure_duration_hours is None
    ):
        missing_fields.append("assessmentContext.doseScenario.eventDurationHours")
        issues.append(
            LimitationNote(
                code="pbpk_inhalation_duration_missing",
                severity=Severity.ERROR,
                message=(
                    "Inhalation PBPK bundle export requires an explicit exposure_duration_hours "
                    "value to preserve event timing semantics."
                ),
            )
        )
    if not scenario.chemical_name:
        issues.append(
            LimitationNote(
                code="pbpk_identity_name_missing",
                severity=Severity.WARNING,
                message=(
                    "PBPK bundle export is stronger when a human-readable chemical_name is "
                    "available for auditability."
                ),
            )
        )
    issues.append(
        LimitationNote(
            code="pbpk_downstream_review_required",
            severity=Severity.WARNING,
            message=(
                "This bundle is an upstream external-exposure handoff only. PBPK execution, "
                "internal dose estimation, and qualification review remain downstream "
                "responsibilities."
            ),
        )
    )
    compatible = not any(item.severity == Severity.ERROR for item in issues)
    ready_for_external_import = compatible

    return PbpkCompatibilityReport(
        source_scenario_id=scenario.scenario_id,
        compatible=compatible,
        checked_route=scenario.route,
        checked_dose_unit=scenario.external_dose.unit.value,
        ready_for_external_pbpk_import=ready_for_external_import,
        supported_pbpk_objects=[
            "ingest_external_pbpk_bundle.arguments",
            "pbpk-mcp.ngraObjects.assessmentContext.v1",
            "pbpk-mcp.ngraObjects.pbpkQualificationSummary.v1",
            "pbpk-mcp.ngraObjects.uncertaintySummary.v1",
            "pbpk-mcp.ngraObjects.uncertaintyHandoff.v1",
            "pbpk-mcp.ngraObjects.internalExposureEstimate.v1",
            "pbpk-mcp.ngraObjects.pointOfDepartureReference.v1",
            "pbpk-mcp.ngraObjects.berInputBundle.v1",
        ],
        missing_external_bundle_fields=missing_fields,
        checked_fields=[
            "toolCall.arguments.assessmentContext.domain.route",
            "toolCall.arguments.assessmentContext.doseScenario.externalDose.unit",
            "toolCall.arguments.assessmentContext.doseScenario.eventsPerDay",
            "toolCall.arguments.assessmentContext.doseScenario.bodyWeightKg",
            "toolCall.arguments.assessmentContext.doseScenario.eventDurationHours",
            "toolCall.arguments.assessmentContext.domain.compound",
        ],
        issues=issues,
        recommended_next_steps=[
            "Call PBPK MCP `ingest_external_pbpk_bundle` with `toolCall.arguments`.",
            "Preserve `bundle.supportingHandoffs` and `toxclawModuleParams` as additive "
            "exposure-side context outside the exact PBPK request payload.",
            "Review returned internalExposureEstimate and pbpkQualificationSummary before "
            "downstream interpretation.",
        ],
    )


def build_pbpk_external_import_package(
    params: ExportPbpkExternalImportBundleRequest,
) -> PbpkExternalImportPackage:
    """Build a PBPK MCP external-import payload template from an exposure scenario."""

    scenario = params.scenario
    body_weight_kg = _resolved_body_weight_kg(scenario)
    pbpk_input = export_pbpk_input(
        ExportPbpkScenarioInputRequest(scenario=scenario),
        DefaultsRegistry.load(),
    )
    uncertainty_summary = _upstream_uncertainty_summary(scenario)
    assessment_context = {
        "contextOfUse": params.context_of_use,
        "scientificPurpose": params.scientific_purpose,
        "decisionContext": params.decision_context,
        "decisionOwner": "external-orchestrator",
        "handoffTarget": "pbpk-mcp",
        "requestedSubject": scenario.chemical_name or scenario.chemical_id,
        "sourceScenarioId": scenario.scenario_id,
        "domain": {
            "species": "human",
            "route": scenario.route.value,
            "lifeStage": _life_stage(scenario.population_profile.population_group),
            "population": scenario.population_profile.population_group,
            "compound": scenario.chemical_name or scenario.chemical_id,
            "region": scenario.population_profile.region,
        },
        "doseScenario": {
            "scenarioId": scenario.scenario_id,
            "externalDose": {
                "metric": scenario.external_dose.metric,
                "value": scenario.external_dose.value,
                "unit": scenario.external_dose.unit.value,
            },
            "eventsPerDay": scenario.product_use_profile.use_events_per_day,
            "eventDurationHours": scenario.product_use_profile.exposure_duration_hours,
            "timingPattern": _scenario_timing_pattern(scenario),
            "productCategory": scenario.product_use_profile.product_category,
            "applicationMethod": scenario.product_use_profile.application_method,
            "retentionType": scenario.product_use_profile.retention_type,
            "bodyWeightKg": body_weight_kg,
        },
        "targetOutput": params.requested_output or scenario.external_dose.metric,
    }
    bundle = PbpkExternalImportBundle(
        source_platform=params.source_platform,
        source_version=params.source_version,
        model_name=params.model_name or f"{scenario.scenario_id}-upstream-context",
        model_type="exposure-scenario-context",
        execution_date=scenario.provenance.generated_at,
        run_id=f"{scenario.scenario_id}-external-context",
        operator=params.operator,
        sponsor=params.sponsor,
        raw_artifacts=[],
        assessment_context=assessment_context,
        chemical_identity=_chemical_identity_context(scenario),
        supporting_handoffs={
            "exposureScenario": scenario.model_dump(mode="json", by_alias=True),
            "pbpkScenarioInput": pbpk_input.model_dump(mode="json", by_alias=True),
            "upstreamUncertaintySummary": uncertainty_summary,
        },
        internal_exposure={},
        qualification={
            "summary": (
                "Imported upstream external-exposure context only; PBPK execution and "
                "qualification outputs are expected downstream from PBPK MCP."
            ),
            "evidenceLevel": "upstream-context-only",
            "verificationStatus": "awaiting-pbpk-execution",
            "performanceEvidenceBoundary": "pbpk-results-not-yet-produced",
            "contextOfUse": params.context_of_use,
            "scientificPurpose": params.scientific_purpose,
            "missingEvidenceCount": 0,
        },
        uncertainty={
            "status": "declared",
            **uncertainty_summary,
            "sources": sorted({item.source.title for item in scenario.assumptions}),
            "residualUncertainty": "upstream-exposure-scenario-assumptions",
            "bundleMetadata": {"sourceScenarioId": scenario.scenario_id},
        },
        uncertainty_register={
            "source": "Exposure Scenario MCP",
            "scope": "upstream-external-exposure-context",
            "summary": (
                "Exposure-scenario limitations remain upstream and must be synthesized with "
                "PBPK and NAM uncertainty downstream."
            ),
        },
        pod={},
        true_dose_adjustment={
            "applied": False,
            "summary": "Not applicable at the upstream external-exposure stage.",
        },
        comparison_metric=params.comparison_metric,
    )
    request_payload = PbpkExternalImportRequest(
        source_platform=bundle.source_platform,
        source_version=bundle.source_version,
        model_name=bundle.model_name,
        model_type=bundle.model_type,
        execution_date=bundle.execution_date,
        run_id=bundle.run_id,
        operator=bundle.operator,
        sponsor=bundle.sponsor,
        raw_artifacts=bundle.raw_artifacts,
        assessment_context=bundle.assessment_context,
        internal_exposure=bundle.internal_exposure,
        qualification=bundle.qualification,
        uncertainty=bundle.uncertainty,
        uncertainty_register=bundle.uncertainty_register,
        pod=bundle.pod,
        true_dose_adjustment=bundle.true_dose_adjustment,
        comparison_metric=bundle.comparison_metric,
    )
    tool_call = PbpkExternalImportToolCall(arguments=request_payload)
    toxclaw_module_params = ToxClawPbpkModuleParams(
        arguments=request_payload,
        chemical_identity=bundle.chemical_identity,
        supporting_handoffs=bundle.supporting_handoffs,
    )
    return PbpkExternalImportPackage(
        bundle=bundle,
        request_payload=request_payload,
        tool_call=tool_call,
        toxclaw_module_params=toxclaw_module_params,
        compatibility_report=check_pbpk_compatibility(scenario),
    )


def suite_integration_guide() -> str:
    return """# Exposure Scenario MCP Suite Integration Guide

## Boundary

- Exposure Scenario MCP owns external dose construction only.
- PBPK MCP owns internal exposure and toxicokinetics.
- ToxClaw owns orchestration, line-of-evidence handling, refinement policy,
  and final interpretation.

## CompTox Integration

- Use CompTox identity records to enrich `chemical_name`, CASRN context,
  and upstream product-use discovery.
- Do not make CompTox enrichment mandatory for scenario construction.
- Preserve CompTox references in `assumption_overrides` or envelope metadata
  rather than hiding them.

## ToxClaw Integration

- Wrap `exposureScenario.v1`, `aggregateExposureSummary.v1`, and `scenarioComparisonRecord.v1`
  as evidence envelopes so ToxClaw can preserve context of use, fit-for-purpose, limitations,
  and provenance without custom glue logic.
- `build_toxclaw_evidence_bundle` emits deterministic ToxClaw-compatible evidence and report
  primitives: an evidence record, a report evidence reference, and a claim-linked report section.
- `build_toxclaw_refinement_bundle` emits an exposure-refinement delta package with an explicit
  `refine_exposure` signal for `exposure_context`, a preserved comparison ledger, and workflow hooks
  for compare, route recalculation, aggregate variants, and PBPK export.
- Treat comparison outputs as evidence about refinement deltas, not as final decisions.

## PBPK Integration

- Export only route, dose magnitude, timing pattern, duration, and population context.
- Do not leak product narratives, use-category prose, or refinement
  commentary into the PBPK contract.
- `build_pbpk_external_import_package` maps upstream exposure context into PBPK MCP's
  `ingest_external_pbpk_bundle` request shape and now emits exact top-level
  `toolCall.arguments` for direct invocation plus ToxClaw-ready module params with additive
  exposure-side handoffs kept outside the strict PBPK request payload.
- Treat `ready_for_external_pbpk_import=true` as "safe to invoke the PBPK MCP ingest tool",
  not as "PBPK outputs already exist."
"""
