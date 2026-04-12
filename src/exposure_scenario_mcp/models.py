"""Public data contracts for Direct-Use Exposure MCP."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScalarValue = str | float | int | bool | None


class StrictModel(BaseModel):
    """Common Pydantic configuration for all public models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


def _validate_required_auditable_text(value: str) -> str:
    if value == "":
        raise ValueError("Value must not be empty.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Value must not contain control characters.")
    return value


def _validate_optional_auditable_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _validate_required_auditable_text(value)


class Route(StrEnum):
    DERMAL = "dermal"
    ORAL = "oral"
    INHALATION = "inhalation"


class ScenarioClass(StrEnum):
    SCREENING = "screening"
    AGGREGATE = "aggregate"
    INHALATION = "inhalation"
    REFINED = "refined"
    POPULATION_DISTRIBUTION = "population_distribution"


class DoseUnit(StrEnum):
    MG_PER_DAY = "mg/day"
    MG_PER_EVENT = "mg/event"
    MG_PER_KG_DAY = "mg/kg-day"
    MG_PER_M3 = "mg/m3"


class ProductAmountUnit(StrEnum):
    G = "g"
    ML = "mL"


class SourceKind(StrEnum):
    USER_INPUT = "user_input"
    DEFAULT_REGISTRY = "default_registry"
    DERIVED = "derived"
    SYSTEM = "system"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceGrade(StrEnum):
    GRADE_4 = "grade_4"
    GRADE_3 = "grade_3"
    GRADE_2 = "grade_2"
    GRADE_1 = "grade_1"


class EvidenceBasis(StrEnum):
    EXPLICIT_INPUT = "explicit_input"
    CURATED_DEFAULT = "curated_default"
    HEURISTIC_DEFAULT = "heuristic_default"
    DERIVED = "derived"


class DefaultVisibility(StrEnum):
    SILENT_TRACEABLE = "silent_traceable"
    WARN = "warn"
    BLOCK = "block"


class ApplicabilityStatus(StrEnum):
    USER_ASSERTED = "user_asserted"
    IN_DOMAIN = "in_domain"
    SCREENING_EXTRAPOLATION = "screening_extrapolation"
    DERIVED = "derived"


class UncertaintyType(StrEnum):
    VARIABILITY = "variability"
    PARAMETER_UNCERTAINTY = "parameter_uncertainty"
    MODEL_UNCERTAINTY = "model_uncertainty"
    SCENARIO_UNCERTAINTY = "scenario_uncertainty"


class TierLevel(StrEnum):
    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class TierUpgradeStatus(StrEnum):
    RECOMMENDED_NOT_IMPLEMENTED = "recommended_not_implemented"
    REQUESTED_NOT_IMPLEMENTED = "requested_not_implemented"


class WorkerSupportStatus(StrEnum):
    SUPPORTED_IN_CURRENT_MCP = "supported_in_current_mcp"
    SUPPORTED_WITH_CAVEATS = "supported_with_caveats"
    FUTURE_ADAPTER_RECOMMENDED = "future_adapter_recommended"
    OUT_OF_SCOPE = "out_of_scope"


class AirflowDirectionality(StrEnum):
    QUIESCENT = "quiescent"
    CROSS_DRAFT = "cross_draft"
    SOURCE_TO_BREATHING_ZONE = "source_to_breathing_zone"
    BREATHING_ZONE_TO_SOURCE = "breathing_zone_to_source"
    GENERAL_ROOM_MIXING = "general_room_mixing"


class ParticleSizeRegime(StrEnum):
    FINE_AEROSOL = "fine_aerosol"
    MIXED_SPRAY = "mixed_spray"
    COARSE_SPRAY = "coarse_spray"


class UncertaintyTier(StrEnum):
    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"
    TIER_D = "tier_d"
    TIER_E = "tier_e"


class BiasDirection(StrEnum):
    LIKELY_OVER = "likely_overestimate"
    LIKELY_UNDER = "likely_underestimate"
    BIDIRECTIONAL = "bidirectional"
    UNKNOWN = "unknown"


class UncertaintyQuantificationStatus(StrEnum):
    QUALITATIVE_ONLY = "qualitative_only"
    BOUNDED = "bounded"
    PROBABILITY_BOUNDS = "probability_bounds"
    PROBABILISTIC = "probabilistic"


class SensitivityDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class DependencyRelationship(StrEnum):
    STRUCTURAL = "structural"
    PHYSIOLOGICAL = "physiological"
    BEHAVIORAL = "behavioral"
    MECHANISTIC = "mechanistic"
    SCENARIO_PACKAGE = "scenario_package"


class DependencyHandlingStrategy(StrEnum):
    SCENARIO_PACKAGED = "scenario_packaged"
    CONDITIONAL_MODEL_REQUIRED = "conditional_model_required"
    JOINT_MODEL_REQUIRED = "joint_model_required"
    NOT_QUANTIFIED = "not_quantified"


class ScenarioPackageFamily(StrEnum):
    USE_INTENSITY = "use_intensity"
    COMPOSITION_USE_BURDEN = "composition_use_burden"
    MICROENVIRONMENT_CONTEXT = "microenvironment_context"
    NEAR_FIELD_CONTEXT = "near_field_context"
    INGESTION_REGIMEN = "ingestion_regimen"


class DriverProfileFamily(StrEnum):
    USE_BURDEN = "use_burden"
    FORMULATION_STRENGTH = "formulation_strength"
    MICROENVIRONMENT = "microenvironment"
    INGESTION_REGIMEN = "ingestion_regimen"


class ValidationStatus(StrEnum):
    VERIFICATION_ONLY = "verification_only"
    BENCHMARK_REGRESSION = "benchmark_regression"
    EXTERNAL_VALIDATION_PARTIAL = "external_validation_partial"
    CALIBRATED = "calibrated"


class ValidationEvidenceReadiness(StrEnum):
    BENCHMARK_ONLY = "benchmark_only"
    BENCHMARK_PLUS_EXTERNAL_CANDIDATES = "benchmark_plus_external_candidates"
    EXTERNAL_CANDIDATES_ONLY = "external_candidates_only"
    EXTERNAL_PARTIAL = "external_partial"
    CALIBRATED = "calibrated"


class ExternalValidationDatasetStatus(StrEnum):
    CANDIDATE_ONLY = "candidate_only"
    PARTIAL = "partial"
    ACCEPTED_REFERENCE = "accepted_reference"


class ValidationGapSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ParticleMaterialClass(StrEnum):
    NANOMATERIAL = "nanomaterial"
    SYNTHETIC_POLYMER_MICROPARTICLE = "synthetic_polymer_microparticle"
    NON_PLASTIC_MICRO_NANO_PARTICLE = "non_plastic_micro_nano_particle"


class ParticleNanoStatus(StrEnum):
    NANO_SPECIFIC = "nano_specific"
    CONTAINS_NANO_FRACTION = "contains_nano_fraction"
    NON_NANO = "non_nano"
    UNKNOWN = "unknown"


class ParticleSizeDomain(StrEnum):
    NANO = "nano"
    MICRO = "micro"
    MIXED_MICRO_NANO = "mixed_micro_nano"
    UNKNOWN = "unknown"


class ParticleCompositionFamily(StrEnum):
    POLYMER = "polymer"
    METAL_OXIDE = "metal_oxide"
    SILICA = "silica"
    PIGMENT = "pigment"
    HYDROXYAPATITE = "hydroxyapatite"
    CARBON_BASED = "carbon_based"
    OTHER = "other"


class ParticleSolubilityClass(StrEnum):
    INSOLUBLE = "insoluble"
    POORLY_SOLUBLE = "poorly_soluble"
    SOLUBLE = "soluble"
    DISSOLVES_RAPIDLY = "dissolves_rapidly"
    UNKNOWN = "unknown"


class ParticleAgglomerationState(StrEnum):
    PRIMARY_PARTICLES = "primary_particles"
    AGGLOMERATED = "agglomerated"
    AGGREGATED = "aggregated"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ParticleShapeFamily(StrEnum):
    SPHERICAL = "spherical"
    FIBROUS = "fibrous"
    PLATELET = "platelet"
    IRREGULAR = "irregular"
    ROD_LIKE = "rod_like"
    UNKNOWN = "unknown"


class ResidualAirReentryMode(StrEnum):
    ANCHORED_REENTRY = "anchored_reentry"
    NATIVE_TREATED_SURFACE_REENTRY = "native_treated_surface_reentry"


class AggregationMode(StrEnum):
    EXTERNAL_SUMMARY = "external_summary"
    INTERNAL_EQUIVALENT = "internal_equivalent"


class ValidationCheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    OUT_OF_DOMAIN = "out_of_domain"


class DefaultsCurationStatus(StrEnum):
    CURATED = "curated"
    HEURISTIC = "heuristic"
    ROUTE_SEMANTIC = "route_semantic"


class AssumptionSourceReference(StrictModel):
    source_id: str = Field(..., description="Stable identifier for the source.")
    title: str = Field(..., description="Human-readable source title.")
    locator: str = Field(..., description="URL, file path, or logical locator.")
    version: str = Field(..., description="Version or effective date for the source.")
    hash_sha256: str | None = Field(default=None, description="Content hash when available.")


class LimitationNote(StrictModel):
    code: str = Field(..., description="Stable machine-readable limitation code.")
    severity: Severity = Field(default=Severity.WARNING, description="Limitation severity.")
    message: str = Field(..., description="Human-readable limitation text.")


class QualityFlag(StrictModel):
    code: str = Field(..., description="Stable machine-readable quality flag code.")
    severity: Severity = Field(default=Severity.INFO, description="Quality signal severity.")
    message: str = Field(..., description="Human-readable quality message.")


class FitForPurpose(StrictModel):
    label: str = Field(..., description="High-level fit-for-purpose label.")
    suitable_for: list[str] = Field(default_factory=list, description="Appropriate use cases.")
    not_suitable_for: list[str] = Field(default_factory=list, description="Known exclusions.")


class AssumptionGovernance(StrictModel):
    evidence_grade: EvidenceGrade | None = Field(
        default=None,
        description=(
            "Ordinal evidence grade for defaults or curated source families, where "
            "grade_4 is strongest and grade_1 is heuristic."
        ),
    )
    evidence_basis: EvidenceBasis = Field(
        ...,
        description=(
            "Whether the value was explicit input, curated default, heuristic, or derived."
        ),
    )
    default_visibility: DefaultVisibility = Field(
        ...,
        description=(
            "Whether the assumption can remain silently traceable, must warn, or would block."
        ),
    )
    applicability_status: ApplicabilityStatus = Field(
        ...,
        description=(
            "Whether the parameter is in-domain, user-asserted, or a screening extrapolation."
        ),
    )
    uncertainty_types: list[UncertaintyType] = Field(
        default_factory=list,
        description="Primary uncertainty families attached to the parameter.",
    )
    applicability_domain: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description=(
            "Structured scenario context that describes where this value is intended to apply."
        ),
    )


class TierSemantics(StrictModel):
    tier_claimed: TierLevel = Field(
        ..., description="Tier family implemented by the active model."
    )
    tier_earned: TierLevel = Field(
        ..., description="Tier earned after the current checks and defaults."
    )
    tier_rationale: str = Field(..., description="Short rationale for the current tier assignment.")
    assumption_checks_passed: bool = Field(
        ..., description="Whether the minimum checks for the earned tier passed."
    )
    required_caveats: list[str] = Field(
        default_factory=list,
        description="Caveats that should stay attached to interpretation of the result.",
    )
    forbidden_interpretations: list[str] = Field(
        default_factory=list,
        description="Interpretations that the result must not support at the current tier.",
    )


class TierUpgradeInputRequirement(StrictModel):
    field_name: str = Field(..., alias="fieldName")
    description: str = Field(..., description="What the future field is expected to capture.")
    reason: str = Field(..., description="Why the field matters for the requested tier.")


class TierUpgradeAdvisory(StrictModel):
    advisory_id: str = Field(..., alias="advisoryId")
    route: Route = Field(..., description="Route for which the tier upgrade applies.")
    current_tier: TierLevel = Field(..., alias="currentTier")
    target_tier: TierLevel = Field(..., alias="targetTier")
    status: TierUpgradeStatus = Field(..., description="Current upgrade availability status.")
    recommended_model_family: str = Field(..., alias="recommendedModelFamily")
    trigger_codes: list[str] = Field(default_factory=list, alias="triggerCodes")
    required_inputs: list[TierUpgradeInputRequirement] = Field(
        default_factory=list, alias="requiredInputs"
    )
    blocking_gaps: list[str] = Field(default_factory=list, alias="blockingGaps")
    guidance_resource: str = Field(..., alias="guidanceResource")
    rationale: str = Field(..., description="Why the upgrade is recommended or blocked.")


class UncertaintyRegisterEntry(StrictModel):
    entry_id: str = Field(..., alias="entryId")
    title: str
    uncertainty_types: list[UncertaintyType] = Field(
        default_factory=list, alias="uncertaintyTypes"
    )
    related_assumptions: list[str] = Field(default_factory=list, alias="relatedAssumptions")
    quantification_status: UncertaintyQuantificationStatus = Field(
        ..., alias="quantificationStatus"
    )
    bias_direction: BiasDirection = Field(..., alias="biasDirection")
    impact_level: Literal["low", "medium", "high"] = Field(..., alias="impactLevel")
    summary: str
    recommendation: str | None = None


class SensitivityRankingEntry(StrictModel):
    parameter_name: str = Field(..., alias="parameterName")
    source_kind: SourceKind = Field(..., alias="sourceKind")
    baseline_value: float = Field(..., alias="baselineValue")
    perturbed_value: float = Field(..., alias="perturbedValue")
    unit: str | None = None
    perturbation_fraction: float = Field(..., alias="perturbationFraction")
    response_metric: str = Field(..., alias="responseMetric")
    absolute_delta: float = Field(..., alias="absoluteDelta")
    percent_delta: float | None = Field(default=None, alias="percentDelta")
    elasticity: float | None = None
    direction: SensitivityDirection


class DependencyDescriptor(StrictModel):
    dependency_id: str = Field(..., alias="dependencyId")
    title: str
    relationship_type: DependencyRelationship = Field(..., alias="relationshipType")
    assumption_names: list[str] = Field(default_factory=list, alias="assumptionNames")
    handling_strategy: DependencyHandlingStrategy = Field(..., alias="handlingStrategy")
    note: str


class ValidationBenchmarkDomain(StrictModel):
    domain: str = Field(..., description="Named validation domain or route mechanism.")
    case_ids: list[str] = Field(default_factory=list, alias="caseIds")
    validation_status: ValidationStatus = Field(..., alias="validationStatus")
    highest_supported_uncertainty_tier: UncertaintyTier = Field(
        ..., alias="highestSupportedUncertaintyTier"
    )
    notes: list[str] = Field(default_factory=list)


class ExternalValidationDataset(StrictModel):
    dataset_id: str = Field(..., alias="datasetId")
    domain: str = Field(..., description="Target validation domain or route mechanism.")
    status: ExternalValidationDatasetStatus
    observable: str
    target_metrics: list[str] = Field(default_factory=list, alias="targetMetrics")
    applicable_tier_claims: list[TierLevel] = Field(
        default_factory=list, alias="applicableTierClaims"
    )
    product_families: list[str] = Field(default_factory=list, alias="productFamilies")
    reference_title: str | None = Field(
        default=None,
        alias="referenceTitle",
        description="Reference title when the validation target is tied to a concrete study.",
    )
    reference_locator: str | None = Field(
        default=None,
        alias="referenceLocator",
        description="URL or DOI for the cited validation reference, when available.",
    )
    note: str

    @model_validator(mode="after")
    def validate_reference_fields(self) -> ExternalValidationDataset:
        if self.status != ExternalValidationDatasetStatus.CANDIDATE_ONLY and (
            not self.reference_title or not self.reference_locator
        ):
            raise ValueError(
                "referenceTitle and referenceLocator are required when status is not "
                "candidate_only."
            )
        return self


class ValidationReferenceBand(StrictModel):
    reference_band_id: str = Field(..., alias="referenceBandId")
    check_id: str = Field(..., alias="checkId")
    reference_dataset_id: str = Field(..., alias="referenceDatasetId")
    domain: str = Field(..., description="Validation domain or route mechanism.")
    compared_metric: str = Field(..., alias="comparedMetric")
    reference_lower: float = Field(..., alias="referenceLower")
    reference_upper: float = Field(..., alias="referenceUpper")
    unit: str = Field(..., description="Unit for the compared metric.")
    applicable_selectors: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="applicableSelectors",
        description=(
            "Structured selectors describing where the reference band is intended to apply."
        ),
    )
    note: str


class ValidationReferenceBandManifest(StrictModel):
    schema_version: Literal["validationReferenceBandManifest.v1"] = (
        "validationReferenceBandManifest.v1"
    )
    reference_version: str = Field(..., alias="referenceVersion")
    reference_hash_sha256: str = Field(..., alias="referenceHashSha256")
    path: str = Field(
        ...,
        description="Package or repository path for the reference-band manifest.",
    )
    band_count: int = Field(..., alias="bandCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    bands: list[ValidationReferenceBand] = Field(default_factory=list)


class ValidationTimeSeriesReferencePoint(StrictModel):
    point_id: str = Field(..., alias="pointId")
    check_id: str = Field(..., alias="checkId")
    title: str
    scenario_metric_key: str = Field(..., alias="scenarioMetricKey")
    time_coordinate_hours: float = Field(..., alias="timeCoordinateHours", ge=0.0)
    reference_lower: float = Field(..., alias="referenceLower")
    reference_upper: float = Field(..., alias="referenceUpper")
    unit: str
    note: str


class ValidationTimeSeriesReferencePack(StrictModel):
    reference_pack_id: str = Field(..., alias="referencePackId")
    reference_dataset_id: str = Field(..., alias="referenceDatasetId")
    domain: str = Field(..., description="Validation domain or route mechanism.")
    time_coordinate_reference: str = Field(..., alias="timeCoordinateReference")
    applicable_selectors: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="applicableSelectors",
        description=(
            "Structured selectors describing where the time-series pack is intended to apply."
        ),
    )
    points: list[ValidationTimeSeriesReferencePoint] = Field(default_factory=list)
    note: str


class ValidationTimeSeriesReferenceManifest(StrictModel):
    schema_version: Literal["validationTimeSeriesReferenceManifest.v1"] = (
        "validationTimeSeriesReferenceManifest.v1"
    )
    reference_version: str = Field(..., alias="referenceVersion")
    reference_hash_sha256: str = Field(..., alias="referenceHashSha256")
    path: str = Field(
        ...,
        description="Package or repository path for the time-series reference-pack manifest.",
    )
    pack_count: int = Field(..., alias="packCount", ge=0)
    point_count: int = Field(..., alias="pointCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    packs: list[ValidationTimeSeriesReferencePack] = Field(default_factory=list)


class ValidationGap(StrictModel):
    gap_id: str = Field(..., alias="gapId")
    title: str
    severity: ValidationGapSeverity
    applies_to_domains: list[str] = Field(default_factory=list, alias="appliesToDomains")
    related_source_ids: list[str] = Field(default_factory=list, alias="relatedSourceIds")
    note: str
    recommendation: str


class ExecutedValidationCheck(StrictModel):
    check_id: str = Field(..., alias="checkId")
    title: str
    reference_dataset_id: str = Field(..., alias="referenceDatasetId")
    status: ValidationCheckStatus
    compared_metric: str = Field(..., alias="comparedMetric")
    observed_value: float = Field(..., alias="observedValue")
    reference_lower: float = Field(..., alias="referenceLower")
    reference_upper: float = Field(..., alias="referenceUpper")
    unit: str
    note: str


class ValidationDossierReport(StrictModel):
    schema_version: Literal["validationDossierReport.v1"] = "validationDossierReport.v1"
    policy_version: str = Field(..., alias="policyVersion")
    benchmark_domains: list[ValidationBenchmarkDomain] = Field(
        default_factory=list, alias="benchmarkDomains"
    )
    external_datasets: list[ExternalValidationDataset] = Field(
        default_factory=list, alias="externalDatasets"
    )
    heuristic_source_ids: list[str] = Field(default_factory=list, alias="heuristicSourceIds")
    open_gaps: list[ValidationGap] = Field(default_factory=list, alias="openGaps")
    notes: list[str] = Field(default_factory=list)


class ValidationCoverageDomainSummary(StrictModel):
    domain: str
    coverage_level: Literal[
        "benchmark_time_resolved",
        "benchmark_plus_executable_references",
        "benchmark_only",
        "source_backed_only",
        "verification_only",
    ] = Field(..., alias="coverageLevel")
    highest_supported_uncertainty_tier: UncertaintyTier = Field(
        ..., alias="highestSupportedUncertaintyTier"
    )
    benchmark_case_count: int = Field(..., alias="benchmarkCaseCount", ge=0)
    benchmark_case_ids: list[str] = Field(default_factory=list, alias="benchmarkCaseIds")
    goldset_case_count: int = Field(..., alias="goldsetCaseCount", ge=0)
    goldset_case_ids: list[str] = Field(default_factory=list, alias="goldsetCaseIds")
    external_dataset_count: int = Field(..., alias="externalDatasetCount", ge=0)
    external_dataset_ids: list[str] = Field(default_factory=list, alias="externalDatasetIds")
    executable_reference_band_count: int = Field(
        ..., alias="executableReferenceBandCount", ge=0
    )
    executable_reference_band_ids: list[str] = Field(
        default_factory=list, alias="executableReferenceBandIds"
    )
    time_series_pack_count: int = Field(..., alias="timeSeriesPackCount", ge=0)
    time_series_pack_ids: list[str] = Field(default_factory=list, alias="timeSeriesPackIds")
    open_gap_count: int = Field(..., alias="openGapCount", ge=0)
    open_gap_ids: list[str] = Field(default_factory=list, alias="openGapIds")
    summary: str


class ValidationCoverageReport(StrictModel):
    schema_version: Literal["validationCoverageReport.v1"] = Field(
        default="validationCoverageReport.v1", alias="schemaVersion"
    )
    policy_version: str = Field(..., alias="policyVersion")
    benchmark_defaults_version: str = Field(..., alias="benchmarkDefaultsVersion")
    reference_band_version: str = Field(..., alias="referenceBandVersion")
    time_series_reference_version: str = Field(..., alias="timeSeriesReferenceVersion")
    goldset_version: str = Field(..., alias="goldsetVersion")
    domain_count: int = Field(..., alias="domainCount", ge=0)
    benchmark_case_count: int = Field(..., alias="benchmarkCaseCount", ge=0)
    external_dataset_count: int = Field(..., alias="externalDatasetCount", ge=0)
    reference_band_count: int = Field(..., alias="referenceBandCount", ge=0)
    time_series_pack_count: int = Field(..., alias="timeSeriesPackCount", ge=0)
    goldset_case_count: int = Field(..., alias="goldsetCaseCount", ge=0)
    goldset_coverage_counts: dict[str, int] = Field(
        default_factory=dict, alias="goldsetCoverageCounts"
    )
    unmapped_goldset_case_ids: list[str] = Field(
        default_factory=list, alias="unmappedGoldsetCaseIds"
    )
    domain_summaries: list[ValidationCoverageDomainSummary] = Field(
        default_factory=list, alias="domainSummaries"
    )
    overall_notes: list[str] = Field(default_factory=list, alias="overallNotes")


class DefaultsCurationEntry(StrictModel):
    path_id: str = Field(..., alias="pathId")
    parameter_name: str = Field(..., alias="parameterName")
    applicability: dict[str, ScalarValue] = Field(default_factory=dict)
    value: ScalarValue = None
    unit: str | None = None
    source_id: str = Field(..., alias="sourceId")
    source_locator: str = Field(..., alias="sourceLocator")
    curation_status: DefaultsCurationStatus = Field(..., alias="curationStatus")
    note: str | None = None


class DefaultsCurationReport(StrictModel):
    schema_version: Literal["defaultsCurationReport.v1"] = Field(
        default="defaultsCurationReport.v1", alias="schemaVersion"
    )
    defaults_version: str = Field(..., alias="defaultsVersion")
    defaults_hash_sha256: str = Field(..., alias="defaultsHashSha256")
    entry_count: int = Field(..., alias="entryCount", ge=0)
    curated_entry_count: int = Field(..., alias="curatedEntryCount", ge=0)
    heuristic_entry_count: int = Field(..., alias="heuristicEntryCount", ge=0)
    route_semantic_entry_count: int = Field(..., alias="routeSemanticEntryCount", ge=0)
    entries: list[DefaultsCurationEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ValidationSummary(StrictModel):
    validation_status: ValidationStatus = Field(..., alias="validationStatus")
    route_mechanism: str = Field(..., alias="routeMechanism")
    benchmark_case_ids: list[str] = Field(default_factory=list, alias="benchmarkCaseIds")
    external_dataset_ids: list[str] = Field(default_factory=list, alias="externalDatasetIds")
    evidence_readiness: ValidationEvidenceReadiness = Field(
        ..., alias="evidenceReadiness"
    )
    heuristic_assumption_names: list[str] = Field(
        default_factory=list, alias="heuristicAssumptionNames"
    )
    validation_gap_ids: list[str] = Field(default_factory=list, alias="validationGapIds")
    executed_validation_checks: list[ExecutedValidationCheck] = Field(
        default_factory=list,
        alias="executedValidationChecks",
    )
    highest_supported_uncertainty_tier: UncertaintyTier = Field(
        ..., alias="highestSupportedUncertaintyTier"
    )
    probabilistic_enablement: Literal["blocked", "gated", "enabled"] = Field(
        ..., alias="probabilisticEnablement"
    )
    notes: list[str] = Field(default_factory=list)


class MonotonicDirection(StrEnum):
    INCREASE_INCREASES_DOSE = "increase_increases_dose"
    INCREASE_DECREASES_DOSE = "increase_decreases_dose"


class ParameterBoundInput(StrictModel):
    parameter_name: str = Field(..., alias="parameterName")
    lower_value: float = Field(..., alias="lowerValue")
    upper_value: float = Field(..., alias="upperValue")
    unit: str | None = None
    rationale: str = Field(..., description="Why this bounded driver belongs in the summary.")

    @model_validator(mode="after")
    def validate_bounds(self) -> ParameterBoundInput:
        if self.upper_value <= self.lower_value:
            raise ValueError("upperValue must be greater than lowerValue.")
        return self


class MonotonicityCheck(StrictModel):
    parameter_name: str = Field(..., alias="parameterName")
    expected_direction: MonotonicDirection = Field(..., alias="expectedDirection")
    lower_dose: float = Field(..., alias="lowerDose")
    upper_dose: float = Field(..., alias="upperDose")
    status: Literal["pass", "warning", "blocked"]
    note: str


class ProbabilityBoundSupportPointDefinition(StrictModel):
    point_id: str = Field(..., alias="pointId")
    parameter_value: float = Field(..., alias="parameterValue")
    cumulative_probability_lower: float = Field(
        ..., alias="cumulativeProbabilityLower", ge=0.0, le=1.0
    )
    cumulative_probability_upper: float = Field(
        ..., alias="cumulativeProbabilityUpper", ge=0.0, le=1.0
    )
    note: str

    @model_validator(mode="after")
    def validate_probability_bounds(self) -> ProbabilityBoundSupportPointDefinition:
        if self.cumulative_probability_upper < self.cumulative_probability_lower:
            raise ValueError(
                "cumulativeProbabilityUpper must be greater than or equal to "
                "cumulativeProbabilityLower."
            )
        return self


class ProbabilityBoundsDriverProfile(StrictModel):
    profile_id: str = Field(..., alias="profileId")
    label: str = Field(..., description="Human-readable driver-profile label.")
    description: str = Field(..., description="What this driver profile is intended to represent.")
    parameter_name: str = Field(..., alias="parameterName")
    route: Route = Field(..., description="Route for which the driver profile applies.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    archetype_library_set_id: str | None = Field(default=None, alias="archetypeLibrarySetId")
    product_family: str = Field(
        ...,
        alias="productFamily",
        description="Named product-family or use-family for the driver profile.",
    )
    driver_family: DriverProfileFamily = Field(
        ...,
        alias="driverFamily",
        description="Curated taxonomy family for the varied driver.",
    )
    dependency_cluster: str = Field(
        ...,
        alias="dependencyCluster",
        description="Named dependency cluster surrounding the varied driver.",
    )
    fixed_axes: list[str] = Field(
        default_factory=list,
        alias="fixedAxes",
        description="Related axes intentionally held fixed while the driver varies.",
    )
    relationship_type: DependencyRelationship = Field(
        ...,
        alias="relationshipType",
        description="Dependency relationship classification for the profile context.",
    )
    handling_strategy: DependencyHandlingStrategy = Field(
        ...,
        alias="handlingStrategy",
        description="How unmodeled dependencies are handled for the profile.",
    )
    applicability: dict[str, ScalarValue] = Field(default_factory=dict)
    support_points: list[ProbabilityBoundSupportPointDefinition] = Field(
        ..., alias="supportPoints", min_length=2
    )
    limitations: list[str] = Field(default_factory=list)


class ProbabilityBoundsProfileManifest(StrictModel):
    schema_version: Literal["probabilityBoundsProfileManifest.v1"] = (
        "probabilityBoundsProfileManifest.v1"
    )
    profile_version: str = Field(..., alias="profileVersion")
    profile_hash_sha256: str = Field(..., alias="profileHashSha256")
    path: str = Field(..., description="Package or repository path for the profile manifest.")
    profile_count: int = Field(..., alias="profileCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    profiles: list[ProbabilityBoundsDriverProfile] = Field(default_factory=list)


class ScenarioPackageProbabilityPointDefinition(StrictModel):
    point_id: str = Field(..., alias="pointId")
    template_id: str = Field(..., alias="templateId")
    cumulative_probability_lower: float = Field(
        ..., alias="cumulativeProbabilityLower", ge=0.0, le=1.0
    )
    cumulative_probability_upper: float = Field(
        ..., alias="cumulativeProbabilityUpper", ge=0.0, le=1.0
    )
    note: str

    @model_validator(mode="after")
    def validate_probability_bounds(self) -> ScenarioPackageProbabilityPointDefinition:
        if self.cumulative_probability_upper < self.cumulative_probability_lower:
            raise ValueError(
                "cumulativeProbabilityUpper must be greater than or equal to "
                "cumulativeProbabilityLower."
            )
        return self


class ScenarioPackageProbabilityProfile(StrictModel):
    profile_id: str = Field(..., alias="profileId")
    label: str = Field(..., description="Human-readable scenario-package profile label.")
    description: str = Field(
        ..., description="What coupled-driver package this probability profile represents."
    )
    route: Route = Field(..., description="Route for which the package profile applies.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    archetype_library_set_id: str = Field(..., alias="archetypeLibrarySetId")
    product_family: str = Field(
        ...,
        alias="productFamily",
        description="Named product-family or use-family for the package.",
    )
    package_family: ScenarioPackageFamily = Field(
        ...,
        alias="packageFamily",
        description="Curated dependency taxonomy family for the package.",
    )
    dependency_cluster: str = Field(
        ...,
        alias="dependencyCluster",
        description="Named coupled-driver cluster preserved by the package.",
    )
    dependency_axes: list[str] = Field(
        ...,
        alias="dependencyAxes",
        min_length=1,
        description="Curated driver axes preserved together.",
    )
    relationship_type: DependencyRelationship = Field(
        ...,
        alias="relationshipType",
        description="Dependency relationship classification for the packaged bundle.",
    )
    handling_strategy: DependencyHandlingStrategy = Field(
        ...,
        alias="handlingStrategy",
        description="How the coupled drivers are handled in the packaged summary.",
    )
    support_points: list[ScenarioPackageProbabilityPointDefinition] = Field(
        ..., alias="supportPoints", min_length=2
    )
    limitations: list[str] = Field(default_factory=list)


class ScenarioPackageProbabilityManifest(StrictModel):
    schema_version: Literal["scenarioPackageProbabilityManifest.v1"] = (
        "scenarioPackageProbabilityManifest.v1"
    )
    profile_version: str = Field(..., alias="profileVersion")
    profile_hash_sha256: str = Field(..., alias="profileHashSha256")
    path: str = Field(..., description="Package or repository path for the profile manifest.")
    profile_count: int = Field(..., alias="profileCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    profiles: list[ScenarioPackageProbabilityProfile] = Field(default_factory=list)


class ExposureAssumptionRecord(StrictModel):
    schema_version: Literal["exposureAssumptionRecord.v1"] = "exposureAssumptionRecord.v1"
    name: str = Field(..., description="Stable parameter name used by the engine.")
    value: ScalarValue = Field(..., description="The resolved assumption value.")
    unit: str | None = Field(default=None, description="Resolved unit, if applicable.")
    source_kind: SourceKind = Field(
        ..., description="Whether the value was user supplied, defaulted, or derived."
    )
    source: AssumptionSourceReference = Field(
        ..., description="Source reference for the assumption."
    )
    confidence: str = Field(..., description="Human-readable confidence label.")
    default_applied: bool = Field(..., description="Whether a default value was applied.")
    rationale: str = Field(..., description="Why this assumption was used.")
    governance: AssumptionGovernance = Field(
        ...,
        description=(
            "Scientific-governance metadata for defaulting, applicability, and uncertainty."
        ),
    )


class ProvenanceBundle(StrictModel):
    schema_version: Literal["provenanceBundle.v1"] = "provenanceBundle.v1"
    algorithm_id: str = Field(..., description="Stable algorithm identifier.")
    plugin_id: str = Field(..., description="Plugin that generated the result.")
    plugin_version: str = Field(..., description="Plugin version.")
    defaults_version: str = Field(..., description="Defaults pack version.")
    defaults_hash_sha256: str = Field(..., description="Hash for the defaults pack in use.")
    generated_at: str = Field(..., description="ISO-8601 UTC timestamp.")
    notes: list[str] = Field(default_factory=list, description="Additional provenance notes.")


class ParticleMaterialContext(StrictModel):
    schema_version: Literal["particleMaterialContext.v1"] = "particleMaterialContext.v1"
    material_class: ParticleMaterialClass = Field(
        ..., alias="materialClass", description="High-level particle material class."
    )
    nano_status: ParticleNanoStatus = Field(
        ..., alias="nanoStatus", description="Whether the context is nano-specific."
    )
    particle_size_domain: ParticleSizeDomain = Field(
        ..., alias="particleSizeDomain", description="Primary size-domain classification."
    )
    composition_family: ParticleCompositionFamily = Field(
        ..., alias="compositionFamily", description="Broad composition family."
    )
    intentionally_manufactured_particle: bool | None = Field(
        default=None,
        alias="intentionallyManufacturedParticle",
        description="Whether the material is an intentionally manufactured particle.",
    )
    insoluble_or_biopersistent: bool | None = Field(
        default=None,
        alias="insolubleOrBiopersistent",
        description="Whether the particle is treated as insoluble or biopersistent.",
    )
    solubility_class: ParticleSolubilityClass | None = Field(
        default=None, alias="solubilityClass", description="Screening solubility class."
    )
    agglomeration_state: ParticleAgglomerationState | None = Field(
        default=None,
        alias="agglomerationState",
        description="Agglomeration or aggregation state relevant to use.",
    )
    shape_family: ParticleShapeFamily | None = Field(
        default=None, alias="shapeFamily", description="Particle shape family."
    )
    surface_treated: bool | None = Field(
        default=None,
        alias="surfaceTreated",
        description="Whether the particle has a relevant surface treatment or coating.",
    )
    surface_treatment_notes: str | None = Field(
        default=None,
        alias="surfaceTreatmentNotes",
        description="Short notes on coatings or surface treatment when known.",
    )
    median_primary_particle_size_nm: float | None = Field(
        default=None,
        alias="medianPrimaryParticleSizeNm",
        description="Median primary particle size in nm when known.",
        gt=0.0,
    )
    size_range_nm_low: float | None = Field(
        default=None, alias="sizeRangeNmLow", description="Lower particle size bound in nm.", gt=0.0
    )
    size_range_nm_high: float | None = Field(
        default=None,
        alias="sizeRangeNmHigh",
        description="Upper particle size bound in nm.",
        gt=0.0,
    )
    respirable_fraction_relevance: bool | None = Field(
        default=None,
        alias="respirableFractionRelevance",
        description="Whether inhalation respirable-fraction context is materially relevant.",
    )
    dermal_penetration_concern: bool | None = Field(
        default=None,
        alias="dermalPenetrationConcern",
        description="Whether dermal particle penetration or retention is a relevant concern.",
    )
    article16_notification_relevant: bool | None = Field(
        default=None,
        alias="article16NotificationRelevant",
        description="Whether EU cosmetics Article 16 nanomaterial notification context applies.",
    )
    echa_spm_restriction_relevant: bool | None = Field(
        default=None,
        alias="echaSpmRestrictionRelevant",
        description=(
            "Whether EU synthetic polymer microparticle restriction/reporting context applies."
        ),
    )
    notes: list[str] = Field(default_factory=list, description="Additional material-context notes.")


class PhyschemContext(StrictModel):
    schema_version: Literal["physchemContext.v1"] = "physchemContext.v1"
    vapor_pressure_mmhg: float | None = Field(
        default=None,
        alias="vaporPressureMmhg",
        ge=0.0,
        description="Vapor pressure in mmHg for bounded volatility-aware calculations.",
    )
    molecular_weight_g_per_mol: float | None = Field(
        default=None,
        alias="molecularWeightGPerMol",
        gt=0.0,
        description="Molecular weight in g/mol for bounded thermodynamic conversions.",
    )
    log_kow: float | None = Field(
        default=None,
        alias="logKow",
        description="logKow descriptor preserved for chemistry-aware screening refinements.",
    )
    water_solubility_mg_per_l: float | None = Field(
        default=None,
        alias="waterSolubilityMgPerL",
        ge=0.0,
        description="Water solubility in mg/L preserved for chemistry-aware screening refinements.",
    )


class ProductUseProfile(StrictModel):
    schema_version: Literal["productUseProfile.v1"] = "productUseProfile.v1"
    product_name: str | None = Field(
        default=None, description="Optional human-readable product label."
    )
    product_subtype: str | None = Field(
        default=None,
        description=(
            "Optional narrower product-use subtype such as indoor_surface_insecticide "
            "or surface_trigger_spray_disinfectant."
        ),
    )
    aerosol_carrier_family: str | None = Field(
        default=None,
        alias="aerosolCarrierFamily",
        description=(
            "Optional explicit aerosol carrier family such as hydrocarbon_propellant_solvent "
            "or water_ethanol_propellant when formulation-level spray semantics are known."
        ),
    )
    product_category: str = Field(..., description="Product category or PUC-like category.")
    physical_form: str = Field(
        ..., description="Physical form such as cream, liquid, spray, or gel."
    )
    application_method: str = Field(
        ...,
        description="How the product is applied, for example hand_application or trigger_spray.",
    )
    retention_type: str = Field(
        default="leave_on", description="Retention class such as leave_on or rinse_off."
    )
    concentration_fraction: float = Field(
        ..., description="Fraction of the target chemical in the product, 0-1.", ge=0.0, le=1.0
    )
    use_amount_per_event: float = Field(..., description="Product amount used per event.", gt=0.0)
    use_amount_unit: ProductAmountUnit = Field(
        ..., description="Unit for the use amount per event."
    )
    use_events_per_day: float = Field(
        ..., description="Number of product-use events per day.", gt=0.0
    )
    density_g_per_ml: float | None = Field(
        default=None, description="Density when the product amount is in mL.", gt=0.0
    )
    particle_material_context: ParticleMaterialContext | None = Field(
        default=None,
        alias="particleMaterialContext",
        description="Optional particle or nanomaterial context carried with the use profile.",
    )
    transfer_efficiency: float | None = Field(
        default=None, description="Route modifier for external transfer.", gt=0.0, le=1.0
    )
    retention_factor: float | None = Field(
        default=None, description="Retention modifier for dermal screening.", gt=0.0, le=1.0
    )
    ingestion_fraction: float | None = Field(
        default=None,
        description="Fraction of chemical mass incidentally or directly ingested.",
        gt=0.0,
        le=1.0,
    )
    aerosolized_fraction: float | None = Field(
        default=None, description="Fraction of chemical mass released to air.", gt=0.0, le=1.0
    )
    room_volume_m3: float | None = Field(
        default=None, description="Indoor room volume for inhalation screening.", gt=0.0
    )
    air_exchange_rate_per_hour: float | None = Field(
        default=None, description="Air exchange rate for inhalation screening.", ge=0.0
    )
    exposure_duration_hours: float | None = Field(
        default=None, description="Duration of exposure per event.", gt=0.0
    )

    @field_validator(
        "product_name",
        "product_subtype",
        "aerosol_carrier_family",
        "product_category",
        "physical_form",
        "application_method",
        "retention_type",
    )
    @classmethod
    def validate_auditable_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class PopulationProfile(StrictModel):
    schema_version: Literal["populationProfile.v1"] = "populationProfile.v1"
    population_group: str = Field(..., description="Population group, for example adult or child.")
    body_weight_kg: float | None = Field(
        default=None, description="Body weight in kilograms.", gt=0.0
    )
    inhalation_rate_m3_per_hour: float | None = Field(
        default=None, description="Inhalation rate for inhalation screening.", gt=0.0
    )
    exposed_surface_area_cm2: float | None = Field(
        default=None, description="Exposed surface area for dermal scenarios.", gt=0.0
    )
    demographic_tags: list[str] = Field(
        default_factory=list, description="Demographic descriptors for auditability."
    )
    region: str = Field(
        default="global", description="Regional context for defaults or interpretation."
    )

    @field_validator("population_group", "region")
    @classmethod
    def validate_population_text_fields(cls, value: str) -> str:
        return _validate_required_auditable_text(value)


class ChemicalIdentity(StrictModel):
    schema_version: Literal["chemicalIdentity.v1"] = "chemicalIdentity.v1"
    chemical_id: str = Field(
        ...,
        alias="chemicalId",
        description="Stable suite-level chemical identifier used across MCP boundaries.",
    )
    preferred_name: str | None = Field(
        default=None,
        alias="preferredName",
        description="Preferred human-readable chemical name for cross-MCP handoffs.",
    )
    casrn: str | None = Field(
        default=None,
        description="CAS Registry Number when available for reconciliation or review.",
    )
    dtxsid: str | None = Field(
        default=None,
        description="EPA CompTox DTXSID when available.",
    )
    smiles: str | None = Field(
        default=None,
        description="Canonical or representative SMILES string when available.",
    )
    inchi_key: str | None = Field(
        default=None,
        alias="inchiKey",
        description="InChIKey when available for downstream identity reconciliation.",
    )
    external_identifiers: dict[str, str] = Field(
        default_factory=dict,
        alias="externalIdentifiers",
        description="Additional external identifiers preserved verbatim for auditability.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional identity notes that should remain attached to handoffs.",
    )

    @field_validator("chemical_id", "preferred_name", "casrn", "dtxsid", "smiles", "inchi_key")
    @classmethod
    def validate_identity_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class ExposureScenarioDefinition(StrictModel):
    schema_version: Literal["exposureScenarioDefinition.v1"] = (
        "exposureScenarioDefinition.v1"
    )
    scenario_definition_id: str = Field(
        ...,
        alias="scenarioDefinitionId",
        description="Stable identifier for a shared scenario-definition handoff.",
    )
    chemical_identity: ChemicalIdentity = Field(
        ...,
        alias="chemicalIdentity",
        description="Normalized chemical identity preserved across MCP boundaries.",
    )
    route: Route = Field(..., description="Route owned by the scenario definition.")
    scenario_class: ScenarioClass = Field(
        ...,
        alias="scenarioClass",
        description="Scenario class family for the shared scenario-definition handoff.",
    )
    pathway_semantics: str = Field(
        ...,
        alias="pathwaySemantics",
        description=(
            "Short label describing the pathway grammar, for example direct_use, "
            "near_field, or concentration_to_dose."
        ),
    )
    product_use_profile: ProductUseProfile | None = Field(
        default=None,
        alias="productUseProfile",
        description="Resolved product-use profile for direct-use or near-field scenarios.",
    )
    population_profile: PopulationProfile = Field(
        ...,
        alias="populationProfile",
        description="Population context for the shared scenario definition.",
    )
    source_concentration_surface_ids: list[str] = Field(
        default_factory=list,
        alias="sourceConcentrationSurfaceIds",
        description=(
            "Upstream concentration-surface identifiers when the scenario definition "
            "consumes a Fate MCP handoff rather than direct-use inputs."
        ),
    )
    assumption_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="assumptionOverrides",
        description="Explicit override ledger preserved for review and orchestration.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional scenario-definition notes that should survive handoffs.",
    )

    @field_validator("scenario_definition_id", "pathway_semantics")
    @classmethod
    def validate_definition_text_fields(cls, value: str) -> str:
        return _validate_required_auditable_text(value)

    @model_validator(mode="after")
    def validate_supporting_context(self) -> ExposureScenarioDefinition:
        if self.product_use_profile is None and not self.source_concentration_surface_ids:
            raise ValueError(
                "ExposureScenarioDefinition requires productUseProfile or at least one "
                "sourceConcentrationSurfaceId."
            )
        return self


class RouteDoseEstimate(StrictModel):
    schema_version: Literal["routeDoseEstimate.v1"] = "routeDoseEstimate.v1"
    chemical_identity: ChemicalIdentity = Field(
        ...,
        alias="chemicalIdentity",
        description="Normalized chemical identity preserved on the route-dose output.",
    )
    route: Route = Field(..., description="Route represented by this dose estimate.")
    scenario_class: ScenarioClass = Field(
        ...,
        alias="scenarioClass",
        description="Scenario class context for the route-dose estimate.",
    )
    dose: ScenarioDose = Field(
        ...,
        description="Canonical dose metric and unit for downstream consumption.",
    )
    source_scenario_definition_id: str | None = Field(
        default=None,
        alias="sourceScenarioDefinitionId",
        description="Scenario-definition identifier that produced this dose estimate.",
    )
    source_scenario_id: str | None = Field(
        default=None,
        alias="sourceScenarioId",
        description="Concrete scenario identifier when the dose came from a scenario build.",
    )
    source_concentration_surface_ids: list[str] = Field(
        default_factory=list,
        alias="sourceConcentrationSurfaceIds",
        description=(
            "Upstream concentration-surface identifiers when this dose was derived from "
            "environmental concentrations."
        ),
    )
    population_profile: PopulationProfile | None = Field(
        default=None,
        alias="populationProfile",
        description="Population normalization context preserved for downstream review.",
    )
    fit_for_purpose: FitForPurpose = Field(
        ...,
        alias="fitForPurpose",
        description="Fit-for-purpose statement for the shared route-dose estimate.",
    )
    provenance: ProvenanceBundle = Field(
        ...,
        description="Provenance for the dose estimate and any defaults or adapters used.",
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list,
        description="Known limitations that should remain visible downstream.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        alias="qualityFlags",
        description="Quality flags that should remain visible downstream.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional route-dose notes preserved for handoffs.",
    )

    @field_validator("source_scenario_definition_id", "source_scenario_id")
    @classmethod
    def validate_route_dose_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class ReleaseMediumFraction(StrictModel):
    medium: str = Field(
        ...,
        description="Target release medium, for example air, water, soil, or sediment.",
    )
    fraction: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of the release allocated to the named medium.",
    )

    @field_validator("medium")
    @classmethod
    def validate_release_medium_text(cls, value: str) -> str:
        return _validate_required_auditable_text(value)


class EnvironmentalReleaseScenario(StrictModel):
    schema_version: Literal["environmentalReleaseScenario.v1"] = (
        "environmentalReleaseScenario.v1"
    )
    release_scenario_id: str = Field(
        ...,
        alias="releaseScenarioId",
        description="Stable identifier for the environmental release scenario.",
    )
    chemical_identity: ChemicalIdentity = Field(
        ...,
        alias="chemicalIdentity",
        description="Normalized chemical identity preserved across MCP boundaries.",
    )
    source_term_type: Literal["mass", "emission_rate"] = Field(
        ...,
        alias="sourceTermType",
        description="Whether the release is expressed as a one-time mass or an emission rate.",
    )
    release_mass_mg: float | None = Field(
        default=None,
        alias="releaseMassMg",
        gt=0.0,
        description="Released mass when the source term is expressed as a finite mass.",
    )
    emission_rate_mg_per_hour: float | None = Field(
        default=None,
        alias="emissionRateMgPerHour",
        gt=0.0,
        description="Emission rate when the source term is expressed as a release rate.",
    )
    release_duration_hours: float = Field(
        ...,
        alias="releaseDurationHours",
        gt=0.0,
        description="Duration of the release window in hours.",
    )
    timing_pattern: str = Field(
        ...,
        alias="timingPattern",
        description="Human-readable timing pattern such as one-time, episodic, or seasonal.",
    )
    region_scope: str = Field(
        ...,
        alias="regionScope",
        description="Region or site scope used for the future fate handoff.",
    )
    site_context: str | None = Field(
        default=None,
        alias="siteContext",
        description="Optional site or setting label such as residential fringe or warehouse.",
    )
    release_media_fractions: list[ReleaseMediumFraction] = Field(
        ...,
        alias="releaseMediaFractions",
        min_length=1,
        description="Media-fraction ledger for the environmental release scenario.",
    )
    treatment_or_removal_fraction: float | None = Field(
        default=None,
        alias="treatmentOrRemovalFraction",
        ge=0.0,
        le=1.0,
        description="Optional treatment or removal fraction applied before environmental entry.",
    )
    evidence_sources: list[str] = Field(
        default_factory=list,
        alias="evidenceSources",
        description="Upstream evidence references backing the release scenario.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional notes that should remain attached to the release scenario.",
    )

    @field_validator("release_scenario_id", "timing_pattern", "region_scope", "site_context")
    @classmethod
    def validate_environmental_release_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)

    @model_validator(mode="after")
    def validate_release_terms(self) -> EnvironmentalReleaseScenario:
        media_fraction_total = sum(item.fraction for item in self.release_media_fractions)
        if media_fraction_total <= 0.0:
            raise ValueError("releaseMediaFractions must contain a positive total fraction.")
        if media_fraction_total > 1.0 + 1e-9:
            raise ValueError("releaseMediaFractions must sum to 1.0 or less.")
        if self.source_term_type == "mass":
            if self.release_mass_mg is None:
                raise ValueError("releaseMassMg is required when sourceTermType='mass'.")
            if self.emission_rate_mg_per_hour is not None:
                raise ValueError(
                    "emissionRateMgPerHour must be omitted when sourceTermType='mass'."
                )
        if self.source_term_type == "emission_rate":
            if self.emission_rate_mg_per_hour is None:
                raise ValueError(
                    "emissionRateMgPerHour is required when sourceTermType='emission_rate'."
                )
            if self.release_mass_mg is not None:
                raise ValueError(
                    "releaseMassMg must be omitted when sourceTermType='emission_rate'."
                )
        return self


class ConcentrationSurface(StrictModel):
    schema_version: Literal["concentrationSurface.v1"] = "concentrationSurface.v1"
    surface_id: str = Field(
        ...,
        alias="surfaceId",
        description="Stable identifier for the concentration surface output.",
    )
    chemical_identity: ChemicalIdentity = Field(
        ...,
        alias="chemicalIdentity",
        description="Normalized chemical identity preserved across MCP boundaries.",
    )
    medium: str = Field(..., description="Medium represented by the concentration surface.")
    compartment: str = Field(
        ...,
        description="Compartment or context represented by the surface, such as outdoor_air.",
    )
    geographic_scope: str = Field(
        ...,
        alias="geographicScope",
        description="Geographic scope or regional context for the concentration output.",
    )
    compartment_context: dict[str, ScalarValue] = Field(
        default_factory=dict,
        alias="compartmentContext",
        description="Structured context such as distance band, microenvironment, or receptor zone.",
    )
    time_semantics: str = Field(
        ...,
        alias="timeSemantics",
        description="Time semantics such as steady_state, 24h average, or post-application hour 4.",
    )
    concentration_value: float = Field(
        ...,
        alias="concentrationValue",
        description="Numeric concentration estimate for the defined surface.",
    )
    concentration_unit: str = Field(
        ...,
        alias="concentrationUnit",
        description="Canonical concentration unit for the defined surface.",
    )
    model_family: str = Field(
        ...,
        alias="modelFamily",
        description="Model-family tag used to create the concentration surface.",
    )
    source_release_scenario_id: str | None = Field(
        default=None,
        alias="sourceReleaseScenarioId",
        description="Upstream environmental release scenario identifier when available.",
    )
    fit_for_purpose: FitForPurpose = Field(
        ...,
        alias="fitForPurpose",
        description="Fit-for-purpose statement for downstream concentration consumers.",
    )
    provenance: ProvenanceBundle = Field(
        ...,
        description="Provenance for the concentration surface and any defaults or adapters used.",
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list,
        description="Known limitations that should remain visible downstream.",
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        alias="qualityFlags",
        description="Quality flags that should remain visible downstream.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional surface notes preserved for downstream consumers.",
    )

    @field_validator(
        "surface_id",
        "medium",
        "compartment",
        "geographic_scope",
        "time_semantics",
        "concentration_unit",
        "model_family",
        "source_release_scenario_id",
    )
    @classmethod
    def validate_concentration_surface_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class ExposureScenarioRequest(StrictModel):
    schema_version: Literal["exposureScenarioRequest.v1"] = "exposureScenarioRequest.v1"
    chemical_id: str = Field(..., description="Stable chemical identifier.")
    chemical_name: str | None = Field(default=None, description="Optional chemical name.")
    route: Route = Field(..., description="Requested exposure route.")
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.SCREENING, description="Requested scenario class."
    )
    product_use_profile: ProductUseProfile = Field(
        ..., description="Product and use-context profile."
    )
    population_profile: PopulationProfile = Field(
        ..., description="Population profile for the exposed cohort."
    )
    physchem_context: PhyschemContext | None = Field(
        default=None,
        alias="physchemContext",
        description=(
            "Optional physchem descriptors preserved on direct-use requests for bounded "
            "mechanistic refinements."
        ),
    )
    assumption_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict, description="Additional explicit overrides for auditability."
    )

    @field_validator("chemical_id", "chemical_name")
    @classmethod
    def validate_request_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class InhalationScenarioRequest(ExposureScenarioRequest):
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.INHALATION, description="Requested scenario class."
    )
    requested_tier: TierLevel = Field(
        default=TierLevel.TIER_0,
        alias="requestedTier",
        description=(
            "Requested inhalation modeling tier. Tier 1 is reserved as a future contract "
            "hook and is not implemented in v0.1.0."
        ),
    )

    @model_validator(mode="after")
    def validate_route_is_inhalation(self) -> InhalationScenarioRequest:
        if self.route != Route.INHALATION:
            raise ValueError("InhalationScenarioRequest requires route='inhalation'.")
        return self


class InhalationResidualAirReentryScenarioRequest(InhalationScenarioRequest):
    reentry_mode: ResidualAirReentryMode = Field(
        default=ResidualAirReentryMode.ANCHORED_REENTRY,
        alias="reentryMode",
        description=(
            "Residual-air reentry mode. `anchored_reentry` preserves the existing caller-"
            "anchored concentration workflow. `native_treated_surface_reentry` derives the "
            "reentry air profile from treated-surface chemical mass and a bounded first-order "
            "surface-emission term."
        ),
    )
    air_concentration_at_reentry_start_mg_per_m3: float | None = Field(
        default=None,
        alias="airConcentrationAtReentryStartMgPerM3",
        description=(
            "Room-air concentration at the start of the reentry exposure window, typically "
            "anchored to measured, monitored, or externally estimated post-application air."
        ),
        gt=0.0,
    )
    treated_surface_chemical_mass_mg: float | None = Field(
        default=None,
        alias="treatedSurfaceChemicalMassMg",
        description=(
            "Optional treated-surface chemical mass available for post-application emission "
            "in native treated-surface reentry mode."
        ),
        gt=0.0,
    )
    treated_surface_residue_fraction: float | None = Field(
        default=None,
        alias="treatedSurfaceResidueFraction",
        description=(
            "Optional fraction of per-event chemical mass assumed to remain on the treated "
            "surface after application when native treated-surface reentry derives the "
            "emission source from the product-use profile."
        ),
        gt=0.0,
        le=1.0,
    )
    surface_emission_rate_per_hour: float | None = Field(
        default=None,
        alias="surfaceEmissionRatePerHour",
        description=(
            "Optional first-order treated-surface emission rate used only for native "
            "treated-surface reentry mode."
        ),
        ge=0.0,
    )
    additional_decay_rate_per_hour: float | None = Field(
        default=None,
        alias="additionalDecayRatePerHour",
        description=(
            "Optional first-order decay term beyond air exchange, used to represent residual "
            "air decline during the reentry window."
        ),
        ge=0.0,
    )
    post_application_delay_hours: float | None = Field(
        default=None,
        alias="postApplicationDelayHours",
        description=(
            "Elapsed time between the end of application and the start of the reentry exposure "
            "window. This is carried for auditability and interpretation even when the supplied "
            "starting concentration already reflects that delay."
        ),
        ge=0.0,
    )

    @model_validator(mode="after")
    def validate_inhalation_route(self) -> InhalationScenarioRequest:
        if self.route != Route.INHALATION:
            raise ValueError("InhalationScenarioRequest requires route='inhalation'.")
        if self.requested_tier not in {TierLevel.TIER_0, TierLevel.TIER_1}:
            raise ValueError("InhalationScenarioRequest supports requestedTier tier_0 or tier_1.")
        if (
            self.reentry_mode == ResidualAirReentryMode.ANCHORED_REENTRY
            and self.air_concentration_at_reentry_start_mg_per_m3 is None
        ):
            raise ValueError(
                "Anchored residual-air reentry requires airConcentrationAtReentryStartMgPerM3."
            )
        return self


class InhalationTier1ScenarioRequest(ExposureScenarioRequest):
    schema_version: Literal["inhalationTier1ScenarioRequest.v1"] = (
        "inhalationTier1ScenarioRequest.v1"
    )
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.INHALATION,
        description="Requested scenario class for the future Tier 1 inhalation family.",
    )
    requested_tier: Literal[TierLevel.TIER_1] = Field(
        default=TierLevel.TIER_1,
        alias="requestedTier",
        description=(
            "Tier 1 inhalation request surface for a future near-field/far-field screening "
            "model family."
        ),
    )
    source_distance_m: float = Field(
        ...,
        gt=0.0,
        description="Distance from the breathing zone to the active spray source.",
    )
    spray_duration_seconds: float = Field(
        ...,
        gt=0.0,
        description="Active spray emission duration for each use event.",
    )
    near_field_volume_m3: float = Field(
        ...,
        gt=0.0,
        description="Local near-field control volume around the user.",
    )
    airflow_directionality: AirflowDirectionality = Field(
        ...,
        description="Directional airflow context near the source and breathing zone.",
    )
    particle_size_regime: ParticleSizeRegime = Field(
        ...,
        description="Spray droplet or aerosol size regime used for screening semantics.",
    )

    @model_validator(mode="after")
    def validate_tier_1_inhalation_scope(self) -> InhalationTier1ScenarioRequest:
        profile = self.product_use_profile
        if self.route != Route.INHALATION:
            raise ValueError("InhalationTier1ScenarioRequest requires route='inhalation'.")
        if profile.application_method not in {"trigger_spray", "pump_spray", "aerosol_spray"}:
            raise ValueError(
                "InhalationTier1ScenarioRequest currently supports spray application methods only."
            )
        if profile.physical_form != "spray":
            raise ValueError(
                "InhalationTier1ScenarioRequest currently supports physical_form='spray' only."
            )
        return self


class WorkerTaskRoutingInput(StrictModel):
    schema_version: Literal["workerTaskRoutingInput.v1"] = "workerTaskRoutingInput.v1"
    chemical_id: str | None = Field(
        default=None,
        description="Optional chemical identifier carried for auditability of the routing request.",
    )
    route: Route = Field(..., description="Exposure route to route inside worker mode.")
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.SCREENING,
        description="Scenario class that the caller is trying to instantiate.",
    )
    product_use_profile: ProductUseProfile = Field(..., description="Product and task-use profile.")
    population_profile: PopulationProfile = Field(
        ..., description="Population profile for the worker task."
    )
    requested_tier: TierLevel | None = Field(
        default=None,
        description=(
            "Optional worker-tier request used to force a higher-tier route recommendation."
        ),
    )
    prefer_current_mcp: bool = Field(
        default=True,
        description=(
            "Whether routing should favor a scientifically bounded path already implemented in "
            "this MCP when one exists."
        ),
    )

    @field_validator("chemical_id")
    @classmethod
    def validate_worker_routing_text_fields(cls, value: str | None) -> str | None:
        return _validate_optional_auditable_text(value)


class WorkerTaskRoutingDecision(StrictModel):
    schema_version: Literal["workerTaskRoutingDecision.v1"] = "workerTaskRoutingDecision.v1"
    route: Route = Field(..., description="Exposure route evaluated by the router.")
    scenario_class: ScenarioClass = Field(
        ..., description="Scenario class evaluated by the router."
    )
    worker_detected: bool = Field(
        ..., description="Whether worker context was explicitly detected."
    )
    detection_basis: list[str] = Field(
        default_factory=list,
        description="Fields or tags that triggered worker-context detection.",
    )
    support_status: WorkerSupportStatus = Field(
        ..., description="Current implementation status for the task path."
    )
    recommended_model_family: str = Field(
        ...,
        description="Best-fit model family for the task given the current MCP boundary.",
    )
    recommended_tool: str | None = Field(
        default=None,
        description="Current MCP tool to call next when one is available.",
    )
    target_mcp: str = Field(
        ...,
        description="MCP or adapter boundary that should own the next step.",
    )
    guidance_resource: str = Field(
        ...,
        description="Documentation resource that explains the routed worker path.",
    )
    required_inputs: list[str] = Field(
        default_factory=list,
        description="Inputs that should be provided before taking the routed path seriously.",
    )
    warnings: list[str] = Field(
        default_factory=list, description="Worker-routing warnings that should remain visible."
    )
    limitations: list[str] = Field(
        default_factory=list, description="Known limits of the routed worker path."
    )
    rationale: str = Field(..., description="Why the router chose this path.")
    next_step: str = Field(..., description="Recommended immediate action for the caller.")


class Tier1AirflowClassProfile(StrictModel):
    directionality: AirflowDirectionality = Field(
        ..., description="Governed airflow-directionality class for Tier 1 NF/FF screening."
    )
    exchange_turnover_per_hour: float = Field(
        ...,
        alias="exchangeTurnoverPerHour",
        gt=0.0,
        description="Screening exchange-turnover mapping used for the near-field zone.",
    )
    source_id: str = Field(..., alias="sourceId", description="Source backing this class.")
    note: str = Field(..., description="Interpretation note for the directionality class.")


class Tier1ParticleRegimeProfile(StrictModel):
    particle_size_regime: ParticleSizeRegime = Field(
        ...,
        alias="particleSizeRegime",
        description="Governed particle-size regime for Tier 1 NF/FF screening.",
    )
    persistence_factor: float = Field(
        ...,
        alias="persistenceFactor",
        gt=0.0,
        description="Screening persistence multiplier applied to the near-field increment.",
    )
    source_id: str = Field(..., alias="sourceId", description="Source backing this regime.")
    note: str = Field(..., description="Interpretation note for the particle-size regime.")


class Tier1InhalationProductProfile(StrictModel):
    profile_id: str = Field(..., alias="profileId")
    label: str = Field(..., description="Human-readable product-family profile label.")
    product_family: str = Field(
        ..., alias="productFamily", description="Named product-family/use-family context."
    )
    product_subtype: str | None = Field(
        default=None,
        alias="productSubtype",
        description="Optional narrower product-use subtype that this profile is tuned for.",
    )
    application_method: str = Field(
        ..., alias="applicationMethod", description="Application method supported by the profile."
    )
    recommended_airflow_directionality: AirflowDirectionality = Field(
        ...,
        alias="recommendedAirflowDirectionality",
        description="Recommended Tier 1 airflow class for this product-family profile.",
    )
    recommended_particle_size_regime: ParticleSizeRegime = Field(
        ...,
        alias="recommendedParticleSizeRegime",
        description="Recommended particle-size regime for this product-family profile.",
    )
    recommended_near_field_volume_m3: float = Field(
        ...,
        alias="recommendedNearFieldVolumeM3",
        gt=0.0,
        description="Recommended near-field volume for the product-family profile.",
    )
    default_source_distance_m: float = Field(
        ...,
        alias="defaultSourceDistanceM",
        gt=0.0,
        description="Typical source-distance anchor for the product-family profile.",
    )
    default_spray_duration_seconds: float = Field(
        ...,
        alias="defaultSprayDurationSeconds",
        gt=0.0,
        description="Typical active spray duration anchor for the product-family profile.",
    )
    source_id: str = Field(..., alias="sourceId", description="Source backing this profile.")
    note: str = Field(..., description="Interpretation note for the profile.")


class Tier1InhalationParameterManifest(StrictModel):
    schema_version: Literal["tier1InhalationParameterManifest.v1"] = (
        "tier1InhalationParameterManifest.v1"
    )
    profile_version: str = Field(..., alias="profileVersion")
    profile_hash_sha256: str = Field(..., alias="profileHashSha256")
    path: str = Field(..., description="Package or repository path for the parameter manifest.")
    source_count: int = Field(..., alias="sourceCount", ge=0)
    directionality_profile_count: int = Field(..., alias="directionalityProfileCount", ge=0)
    particle_profile_count: int = Field(..., alias="particleProfileCount", ge=0)
    profile_count: int = Field(..., alias="profileCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    sources: list[AssumptionSourceReference] = Field(default_factory=list)
    directionality_profiles: list[Tier1AirflowClassProfile] = Field(
        default_factory=list,
        alias="directionalityProfiles",
    )
    particle_profiles: list[Tier1ParticleRegimeProfile] = Field(
        default_factory=list,
        alias="particleProfiles",
    )
    profiles: list[Tier1InhalationProductProfile] = Field(default_factory=list)


class ScenarioDose(StrictModel):
    metric: str = Field(..., description="Dose metric label.")
    value: float = Field(..., description="Numeric value for the dose metric.")
    unit: DoseUnit = Field(..., description="Canonical dose unit.")


class ExposureScenario(StrictModel):
    schema_version: Literal["exposureScenario.v1"] = "exposureScenario.v1"
    scenario_id: str = Field(..., description="Stable scenario identifier.")
    chemical_id: str = Field(..., description="Stable chemical identifier.")
    chemical_name: str | None = Field(default=None, description="Optional chemical name.")
    route: Route = Field(..., description="Exposure route.")
    scenario_class: ScenarioClass = Field(..., description="Scenario class tag.")
    external_dose: ScenarioDose = Field(
        ..., description="Primary normalized external dose estimate."
    )
    product_use_profile: ProductUseProfile = Field(..., description="Resolved product-use profile.")
    population_profile: PopulationProfile = Field(..., description="Resolved population profile.")
    route_metrics: dict[str, ScalarValue] = Field(
        default_factory=dict, description="Route-specific metrics."
    )
    assumptions: list[ExposureAssumptionRecord] = Field(
        default_factory=list, description="Explicit parameter ledger."
    )
    provenance: ProvenanceBundle = Field(..., description="Calculation provenance.")
    limitations: list[LimitationNote] = Field(
        default_factory=list, description="Explicit limitations."
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list, description="Quality flags and warnings."
    )
    fit_for_purpose: FitForPurpose = Field(..., description="Fit-for-purpose metadata.")
    tier_semantics: TierSemantics = Field(
        ..., description="Tier and interpretation-boundary semantics for the active model."
    )
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_A,
        alias="uncertaintyTier",
        description="Current uncertainty-governance tier for this output.",
    )
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list,
        alias="uncertaintyRegister",
        description="Qualitative or bounded uncertainty entries attached to the scenario.",
    )
    sensitivity_ranking: list[SensitivityRankingEntry] = Field(
        default_factory=list,
        alias="sensitivityRanking",
        description="Deterministic one-at-a-time sensitivity ranking for the primary dose metric.",
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list,
        alias="dependencyMetadata",
        description="Known dependence structures that matter for later uncertainty work.",
    )
    validation_summary: ValidationSummary | None = Field(
        default=None,
        alias="validationSummary",
        description="Current validation posture for the route and mechanism represented.",
    )
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable scenario notes."
    )
    tier_upgrade_advisories: list[TierUpgradeAdvisory] = Field(
        default_factory=list,
        alias="tierUpgradeAdvisories",
        description="Machine-readable upgrade hooks for later tier implementations.",
    )


class AggregateComponentReference(StrictModel):
    scenario_id: str = Field(..., description="Component scenario identifier.")
    route: Route = Field(..., description="Component route.")
    dose: ScenarioDose = Field(..., description="Primary component dose.")


class RouteDoseTotal(StrictModel):
    route: Route = Field(..., description="Route represented by the total.")
    total_dose: ScenarioDose = Field(..., description="Aggregated dose for this route.")


class AggregateContributor(StrictModel):
    scenario_id: str = Field(..., description="Component scenario identifier.")
    contribution_fraction: float = Field(
        ..., description="Fractional contribution to the normalized total.", ge=0.0
    )
    dose_value: float = Field(..., description="Absolute contribution value.")


class RouteBioavailabilityAdjustment(StrictModel):
    route: Route = Field(..., description="Route represented by the bioavailability fraction.")
    bioavailability_fraction: float = Field(
        ...,
        alias="bioavailabilityFraction",
        ge=0.0,
        le=1.0,
        description="Fraction of external dose treated as internal-equivalent for aggregation.",
    )


class AggregateExposureSummary(StrictModel):
    schema_version: Literal["aggregateExposureSummary.v1"] = "aggregateExposureSummary.v1"
    scenario_id: str = Field(..., description="Aggregate scenario identifier.")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    scenario_class: Literal["aggregate"] = "aggregate"
    component_scenarios: list[AggregateComponentReference] = Field(
        ..., description="Component scenario references."
    )
    aggregation_mode: AggregationMode = Field(
        default=AggregationMode.EXTERNAL_SUMMARY,
        alias="aggregationMode",
        description="Requested aggregation mode for the returned summary.",
    )
    aggregation_method: str = Field(..., description="Aggregation method description.")
    normalized_total_external_dose: ScenarioDose | None = Field(
        default=None, description="Summed normalized total when units are compatible."
    )
    internal_equivalent_total_dose: ScenarioDose | None = Field(
        default=None,
        alias="internalEquivalentTotalDose",
        description="Optional route-adjusted internal-equivalent total when requested.",
    )
    per_route_totals: list[RouteDoseTotal] = Field(
        default_factory=list, description="Route-wise totals."
    )
    per_route_internal_equivalent_totals: list[RouteDoseTotal] = Field(
        default_factory=list,
        alias="perRouteInternalEquivalentTotals",
        description="Route-wise internal-equivalent totals when requested.",
    )
    route_bioavailability_adjustments: list[RouteBioavailabilityAdjustment] = Field(
        default_factory=list,
        alias="routeBioavailabilityAdjustments",
        description="Route-specific bioavailability fractions used for internal-equivalent mode.",
    )
    dominant_contributors: list[AggregateContributor] = Field(
        default_factory=list, description="Dominant contributors to the total."
    )
    limitations: list[LimitationNote] = Field(
        default_factory=list, description="Aggregate limitations."
    )
    quality_flags: list[QualityFlag] = Field(
        default_factory=list, description="Aggregate quality flags."
    )
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_A, alias="uncertaintyTier"
    )
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list, alias="uncertaintyRegister"
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list, alias="dependencyMetadata"
    )
    validation_summary: ValidationSummary | None = Field(
        default=None, alias="validationSummary"
    )
    provenance: ProvenanceBundle = Field(..., description="Aggregate provenance.")


class PbpkPopulationContext(StrictModel):
    population_group: str = Field(..., description="Population group label.")
    body_weight_kg: float = Field(..., description="Resolved body weight.")
    inhalation_rate_m3_per_hour: float | None = Field(
        default=None, description="Resolved inhalation rate if relevant."
    )
    region: str = Field(..., description="Population region.")


class PbpkConcentrationProfilePoint(StrictModel):
    time_hours: float = Field(
        ...,
        alias="timeHours",
        ge=0.0,
        description="Elapsed hours from the start of the exposure event.",
    )
    concentration_mg_per_m3: float = Field(
        ...,
        alias="concentrationMgPerM3",
        ge=0.0,
        description="Air concentration at the stated elapsed time.",
    )


class PbpkScenarioInput(StrictModel):
    schema_version: Literal["pbpkScenarioInput.v1"] = "pbpkScenarioInput.v1"
    source_scenario_id: str = Field(..., description="Source scenario identifier.")
    chemical_id: str = Field(..., description="Stable chemical identifier.")
    chemical_name: str | None = Field(default=None, description="Optional chemical name.")
    route: Route = Field(..., description="Route for the PBPK handoff.")
    dose_magnitude: float = Field(..., description="Primary dose magnitude for PBPK.")
    dose_unit: DoseUnit = Field(..., description="Canonical dose unit.")
    dose_metric: str = Field(..., description="Dose metric label.")
    events_per_day: float = Field(
        ..., description="Daily frequency implied by the source scenario.", gt=0.0
    )
    event_duration_hours: float | None = Field(
        default=None, description="Per-event duration if available."
    )
    timing_pattern: str = Field(..., description="Human-readable timing semantics.")
    population_context: PbpkPopulationContext = Field(
        ..., description="Resolved population context."
    )
    transient_concentration_profile: list[PbpkConcentrationProfilePoint] = Field(
        default_factory=list,
        alias="transientConcentrationProfile",
        description=(
            "Optional time-resolved inhalation forcing profile when requested and supported."
        ),
    )
    supporting_assumption_names: list[str] = Field(
        default_factory=list, description="Names of assumptions backing the handoff."
    )
    provenance: ProvenanceBundle = Field(..., description="Export provenance.")
    limitations: list[LimitationNote] = Field(
        default_factory=list, description="PBPK export limitations."
    )


class AssumptionDelta(StrictModel):
    name: str = Field(..., description="Assumption name.")
    baseline_value: ScalarValue = Field(..., description="Baseline value.")
    comparison_value: ScalarValue = Field(..., description="Comparison value.")
    unit: str | None = Field(default=None, description="Assumption unit if applicable.")


class ScenarioComparisonRecord(StrictModel):
    schema_version: Literal["scenarioComparisonRecord.v1"] = "scenarioComparisonRecord.v1"
    baseline_scenario_id: str = Field(..., description="Baseline scenario ID.")
    comparison_scenario_id: str = Field(..., description="Comparison scenario ID.")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    baseline_dose: ScenarioDose = Field(..., description="Baseline primary dose.")
    comparison_dose: ScenarioDose = Field(..., description="Comparison primary dose.")
    absolute_delta: float = Field(..., description="Comparison minus baseline.")
    percent_delta: float | None = Field(
        default=None, description="Percentage delta relative to the baseline."
    )
    changed_assumptions: list[AssumptionDelta] = Field(
        default_factory=list, description="Changed assumptions."
    )
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable interpretation notes."
    )
    provenance: ProvenanceBundle = Field(..., description="Comparison provenance.")


class BuildAggregateExposureScenarioInput(StrictModel):
    chemical_id: str = Field(..., description="Chemical ID shared across component scenarios.")
    label: str = Field(..., description="Human-readable aggregate label.")
    aggregation_mode: AggregationMode = Field(
        default=AggregationMode.EXTERNAL_SUMMARY,
        alias="aggregationMode",
        description="Aggregation mode. Defaults to the existing external-dose summary behavior.",
    )
    route_bioavailability_adjustments: list[RouteBioavailabilityAdjustment] = Field(
        default_factory=list,
        alias="routeBioavailabilityAdjustments",
        description=(
            "Optional route-level bioavailability fractions required for "
            "internal-equivalent mode."
        ),
    )
    component_scenarios: list[ExposureScenario] = Field(
        ..., min_length=1, description="Component scenarios to aggregate."
    )


class Tier1InhalationTemplateParameters(StrictModel):
    schema_version: Literal["tier1InhalationTemplateParameters.v1"] = (
        "tier1InhalationTemplateParameters.v1"
    )
    source_distance_m: float = Field(
        ...,
        alias="sourceDistanceM",
        gt=0.0,
        description="Distance from the breathing zone to the active spray source.",
    )
    spray_duration_seconds: float = Field(
        ...,
        alias="sprayDurationSeconds",
        gt=0.0,
        description="Active spray emission duration for each use event.",
    )
    near_field_volume_m3: float = Field(
        ...,
        alias="nearFieldVolumeM3",
        gt=0.0,
        description="Local near-field control volume around the user.",
    )
    airflow_directionality: AirflowDirectionality = Field(
        ...,
        alias="airflowDirectionality",
        description="Directional airflow context near the source and breathing zone.",
    )
    particle_size_regime: ParticleSizeRegime = Field(
        ...,
        alias="particleSizeRegime",
        description="Spray droplet or aerosol size regime used for screening semantics.",
    )


class EnvelopeArchetypeInput(StrictModel):
    template_id: str | None = Field(
        default=None,
        alias="templateId",
        description="Optional stable template ID when the archetype comes from a packaged library.",
    )
    label: str = Field(..., description="Human-readable archetype label.")
    description: str = Field(..., description="Why this archetype belongs in the envelope.")
    request: ExposureScenarioRequest | InhalationTier1ScenarioRequest = Field(
        ..., description="Full scenario request representing one deterministic archetype."
    )


class ArchetypeLibraryTemplate(StrictModel):
    template_id: str = Field(..., alias="templateId")
    label: str = Field(..., description="Human-readable archetype label.")
    description: str = Field(..., description="Why this archetype belongs in the library set.")
    product_use_profile: ProductUseProfile = Field(
        ..., alias="productUseProfile", description="Product-use template for this archetype."
    )
    population_profile: PopulationProfile = Field(
        ..., alias="populationProfile", description="Population template for this archetype."
    )
    tier1_inhalation_parameters: Tier1InhalationTemplateParameters | None = Field(
        default=None,
        alias="tier1InhalationParameters",
        description=(
            "Optional Tier 1 inhalation request fields for packaged near-field/far-field "
            "archetype templates."
        ),
    )


class ArchetypeLibrarySet(StrictModel):
    set_id: str = Field(..., alias="setId")
    label: str = Field(..., description="Human-readable library-set label.")
    description: str = Field(..., description="What this set is intended to represent.")
    route: Route = Field(..., description="Common route across the archetypes in this set.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    chemical_scope: Literal["caller_supplied"] = Field(
        default="caller_supplied",
        alias="chemicalScope",
        description="Whether the caller must inject the target chemical identity.",
    )
    intended_use: str = Field(
        ..., alias="intendedUse", description="Short fit-for-purpose statement for this set."
    )
    driver_parameters: list[str] = Field(default_factory=list, alias="driverParameters")
    interpretation_notes: list[str] = Field(default_factory=list, alias="interpretationNotes")
    limitations: list[str] = Field(default_factory=list)
    archetypes: list[ArchetypeLibraryTemplate] = Field(
        ..., min_length=2, description="Packaged archetype templates for this set."
    )

    @model_validator(mode="after")
    def validate_archetype_tier_scope(self) -> ArchetypeLibrarySet:
        has_tier1 = any(
            item.tier1_inhalation_parameters is not None for item in self.archetypes
        )
        if has_tier1:
            if self.route != Route.INHALATION:
                raise ValueError(
                    "Archetype library sets with tier1InhalationParameters require "
                    "route='inhalation'."
                )
            if self.scenario_class != ScenarioClass.INHALATION:
                raise ValueError(
                    "Archetype library sets with tier1InhalationParameters require "
                    "scenarioClass='inhalation'."
                )
        return self


class ArchetypeLibraryManifest(StrictModel):
    schema_version: Literal["archetypeLibraryManifest.v1"] = "archetypeLibraryManifest.v1"
    library_version: str = Field(..., alias="libraryVersion")
    library_hash_sha256: str = Field(..., alias="libraryHashSha256")
    path: str = Field(..., description="Package or repository path for the archetype library.")
    set_count: int = Field(..., alias="setCount", ge=0)
    notes: list[str] = Field(default_factory=list)
    sets: list[ArchetypeLibrarySet] = Field(default_factory=list)


class BuildExposureEnvelopeInput(StrictModel):
    schema_version: Literal["buildExposureEnvelopeInput.v1"] = "buildExposureEnvelopeInput.v1"
    chemical_id: str = Field(..., description="Chemical ID shared across archetypes.")
    label: str = Field(..., description="Human-readable envelope label.")
    archetypes: list[EnvelopeArchetypeInput] = Field(
        ..., min_length=2, description="Named deterministic archetypes to evaluate."
    )


class BuildExposureEnvelopeFromLibraryInput(StrictModel):
    schema_version: Literal["buildExposureEnvelopeFromLibraryInput.v1"] = (
        "buildExposureEnvelopeFromLibraryInput.v1"
    )
    library_set_id: str = Field(
        ..., alias="librarySetId", description="Packaged archetype-library set identifier."
    )
    chemical_id: str = Field(..., alias="chemicalId", description="Target chemical identifier.")
    chemical_name: str | None = Field(
        default=None,
        alias="chemicalName",
        description="Optional human-readable chemical name injected into every archetype request.",
    )
    label: str | None = Field(
        default=None,
        description="Optional override for the resulting envelope label.",
    )


class BuildParameterBoundsInput(StrictModel):
    schema_version: Literal["buildParameterBoundsInput.v1"] = "buildParameterBoundsInput.v1"
    label: str = Field(..., description="Human-readable bounds summary label.")
    base_request: ExposureScenarioRequest = Field(
        ..., alias="baseRequest", description="Baseline deterministic scenario request."
    )
    bounded_parameters: list[ParameterBoundInput] = Field(
        ..., alias="boundedParameters", min_length=1
    )


class BuildProbabilityBoundsFromProfileInput(StrictModel):
    schema_version: Literal["buildProbabilityBoundsFromProfileInput.v1"] = (
        "buildProbabilityBoundsFromProfileInput.v1"
    )
    label: str = Field(..., description="Human-readable probability-bounds summary label.")
    base_request: ExposureScenarioRequest = Field(
        ..., alias="baseRequest", description="Baseline deterministic scenario request."
    )
    driver_profile_id: str = Field(
        ..., alias="driverProfileId", description="Packaged single-driver probability profile ID."
    )


class BuildProbabilityBoundsFromScenarioPackageInput(StrictModel):
    schema_version: Literal["buildProbabilityBoundsFromScenarioPackageInput.v1"] = (
        "buildProbabilityBoundsFromScenarioPackageInput.v1"
    )
    package_profile_id: str = Field(
        ..., alias="packageProfileId", description="Packaged coupled-driver scenario package ID."
    )
    chemical_id: str = Field(..., alias="chemicalId", description="Target chemical identifier.")
    chemical_name: str | None = Field(
        default=None,
        alias="chemicalName",
        description="Optional human-readable chemical name injected into every package scenario.",
    )
    label: str | None = Field(
        default=None,
        description="Optional override for the resulting scenario-package summary label.",
    )


class EnvelopeArchetypeResult(StrictModel):
    template_id: str | None = Field(default=None, alias="templateId")
    label: str = Field(..., description="Archetype label.")
    description: str = Field(..., description="Archetype description.")
    scenario: ExposureScenario = Field(..., description="Resolved scenario for this archetype.")


class EnvelopeDriverAttribution(StrictModel):
    parameter_name: str = Field(..., alias="parameterName")
    unit: str | None = None
    min_value: ScalarValue = Field(..., alias="minValue")
    max_value: ScalarValue = Field(..., alias="maxValue")
    scenario_labels: list[str] = Field(default_factory=list, alias="scenarioLabels")
    attribution_note: str = Field(..., alias="attributionNote")


class ExposureEnvelopeSummary(StrictModel):
    schema_version: Literal["exposureEnvelopeSummary.v1"] = "exposureEnvelopeSummary.v1"
    envelope_id: str = Field(..., alias="envelopeId")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    route: Route = Field(..., description="Common route across the archetypes.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    label: str = Field(..., description="Human-readable envelope label.")
    archetype_library_set_id: str | None = Field(default=None, alias="archetypeLibrarySetId")
    archetype_library_version: str | None = Field(default=None, alias="archetypeLibraryVersion")
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_B, alias="uncertaintyTier"
    )
    archetypes: list[EnvelopeArchetypeResult] = Field(
        default_factory=list, description="Resolved archetype scenarios."
    )
    min_dose: ScenarioDose = Field(..., alias="minDose")
    median_dose: ScenarioDose = Field(..., alias="medianDose")
    max_dose: ScenarioDose = Field(..., alias="maxDose")
    span_ratio: float | None = Field(default=None, alias="spanRatio")
    driver_attribution: list[EnvelopeDriverAttribution] = Field(
        default_factory=list, alias="driverAttribution"
    )
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list, alias="uncertaintyRegister"
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list, alias="dependencyMetadata"
    )
    validation_summary: ValidationSummary | None = Field(
        default=None, alias="validationSummary"
    )
    provenance: ProvenanceBundle = Field(..., description="Envelope provenance.")
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable interpretation notes."
    )


class ParameterBoundsSummary(StrictModel):
    schema_version: Literal["parameterBoundsSummary.v1"] = "parameterBoundsSummary.v1"
    summary_id: str = Field(..., alias="summaryId")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    route: Route = Field(..., description="Common route across the bounded scenarios.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    label: str = Field(..., description="Human-readable bounds summary label.")
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_B, alias="uncertaintyTier"
    )
    base_scenario: ExposureScenario = Field(..., alias="baseScenario")
    min_scenario: ExposureScenario = Field(..., alias="minScenario")
    max_scenario: ExposureScenario = Field(..., alias="maxScenario")
    bounded_parameters: list[ParameterBoundInput] = Field(
        default_factory=list, alias="boundedParameters"
    )
    monotonicity_checks: list[MonotonicityCheck] = Field(
        default_factory=list, alias="monotonicityChecks"
    )
    min_dose: ScenarioDose = Field(..., alias="minDose")
    max_dose: ScenarioDose = Field(..., alias="maxDose")
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list, alias="uncertaintyRegister"
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list, alias="dependencyMetadata"
    )
    validation_summary: ValidationSummary | None = Field(
        default=None, alias="validationSummary"
    )
    provenance: ProvenanceBundle = Field(..., description="Bounds-summary provenance.")
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable interpretation notes."
    )


class ProbabilityBoundDosePoint(StrictModel):
    point_id: str = Field(..., alias="pointId")
    parameter_value: float = Field(..., alias="parameterValue")
    dose: ScenarioDose = Field(
        ...,
        description="Resolved deterministic dose at this support point.",
    )
    cumulative_probability_lower: float = Field(
        ..., alias="cumulativeProbabilityLower", ge=0.0, le=1.0
    )
    cumulative_probability_upper: float = Field(
        ..., alias="cumulativeProbabilityUpper", ge=0.0, le=1.0
    )
    note: str


class ProbabilityBoundsProfileSummary(StrictModel):
    schema_version: Literal["probabilityBoundsProfileSummary.v1"] = (
        "probabilityBoundsProfileSummary.v1"
    )
    summary_id: str = Field(..., alias="summaryId")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    route: Route = Field(..., description="Route for which the profile was evaluated.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    label: str = Field(..., description="Human-readable probability-bounds summary label.")
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_C, alias="uncertaintyTier"
    )
    driver_profile_id: str = Field(..., alias="driverProfileId")
    driver_parameter_name: str = Field(..., alias="driverParameterName")
    product_family: str = Field(
        ..., alias="productFamily", description="Named product-family or use-family."
    )
    driver_family: DriverProfileFamily = Field(
        ..., alias="driverFamily", description="Curated taxonomy family for the varied driver."
    )
    dependency_cluster: str = Field(..., alias="dependencyCluster")
    fixed_axes: list[str] = Field(
        default_factory=list,
        alias="fixedAxes",
        description="Related axes intentionally held fixed while the driver varies.",
    )
    relationship_type: DependencyRelationship = Field(
        ..., alias="relationshipType", description="Dependency relationship classification."
    )
    handling_strategy: DependencyHandlingStrategy = Field(
        ..., alias="handlingStrategy", description="How unmodeled dependencies are handled."
    )
    profile_version: str = Field(..., alias="profileVersion")
    archetype_library_set_id: str | None = Field(default=None, alias="archetypeLibrarySetId")
    base_scenario: ExposureScenario = Field(..., alias="baseScenario")
    support_points: list[ProbabilityBoundDosePoint] = Field(
        default_factory=list, alias="supportPoints"
    )
    minimum_dose: ScenarioDose = Field(..., alias="minimumDose")
    maximum_dose: ScenarioDose = Field(..., alias="maximumDose")
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list, alias="uncertaintyRegister"
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list, alias="dependencyMetadata"
    )
    validation_summary: ValidationSummary | None = Field(
        default=None, alias="validationSummary"
    )
    provenance: ProvenanceBundle = Field(..., description="Probability-bounds provenance.")
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable interpretation notes."
    )


class ScenarioPackageProbabilityPointResult(StrictModel):
    point_id: str = Field(..., alias="pointId")
    template_id: str = Field(..., alias="templateId")
    cumulative_probability_lower: float = Field(
        ..., alias="cumulativeProbabilityLower", ge=0.0, le=1.0
    )
    cumulative_probability_upper: float = Field(
        ..., alias="cumulativeProbabilityUpper", ge=0.0, le=1.0
    )
    note: str
    scenario: ExposureScenario = Field(
        ...,
        description="Resolved deterministic scenario for this package point.",
    )


class ScenarioPackageProbabilitySummary(StrictModel):
    schema_version: Literal["scenarioPackageProbabilitySummary.v1"] = (
        "scenarioPackageProbabilitySummary.v1"
    )
    summary_id: str = Field(..., alias="summaryId")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    route: Route = Field(..., description="Route for which the package profile was evaluated.")
    scenario_class: ScenarioClass = Field(..., alias="scenarioClass")
    label: str = Field(..., description="Human-readable scenario-package probability label.")
    uncertainty_tier: UncertaintyTier = Field(
        default=UncertaintyTier.TIER_C, alias="uncertaintyTier"
    )
    package_profile_id: str = Field(..., alias="packageProfileId")
    product_family: str = Field(
        ..., alias="productFamily", description="Named product-family or use-family."
    )
    package_family: ScenarioPackageFamily = Field(
        ..., alias="packageFamily", description="Curated dependency taxonomy family."
    )
    dependency_cluster: str = Field(..., alias="dependencyCluster")
    dependency_axes: list[str] = Field(
        default_factory=list,
        alias="dependencyAxes",
        description="Curated driver axes preserved together in the package.",
    )
    relationship_type: DependencyRelationship = Field(
        ..., alias="relationshipType", description="Dependency relationship classification."
    )
    handling_strategy: DependencyHandlingStrategy = Field(
        ..., alias="handlingStrategy", description="How the packaged summary handles dependence."
    )
    profile_version: str = Field(..., alias="profileVersion")
    archetype_library_set_id: str = Field(..., alias="archetypeLibrarySetId")
    archetype_library_version: str = Field(..., alias="archetypeLibraryVersion")
    support_points: list[ScenarioPackageProbabilityPointResult] = Field(
        default_factory=list, alias="supportPoints"
    )
    minimum_dose: ScenarioDose = Field(..., alias="minimumDose")
    maximum_dose: ScenarioDose = Field(..., alias="maximumDose")
    uncertainty_register: list[UncertaintyRegisterEntry] = Field(
        default_factory=list, alias="uncertaintyRegister"
    )
    dependency_metadata: list[DependencyDescriptor] = Field(
        default_factory=list, alias="dependencyMetadata"
    )
    validation_summary: ValidationSummary | None = Field(
        default=None, alias="validationSummary"
    )
    provenance: ProvenanceBundle = Field(
        ...,
        description="Scenario-package probability-bounds provenance.",
    )
    interpretation_notes: list[str] = Field(
        default_factory=list, description="Human-readable interpretation notes."
    )


class ExportPbpkScenarioInputRequest(StrictModel):
    scenario: ExposureScenario = Field(..., description="Scenario to export for PBPK consumption.")
    regimen_name: str | None = Field(
        default=None, description="Optional human-readable regimen name."
    )
    include_transient_concentration_profile: bool = Field(
        default=False,
        alias="includeTransientConcentrationProfile",
        description=(
            "When true, inhalation scenarios export a simple transient concentration "
            "profile if supported."
        ),
    )


class ExportPbpkExternalImportBundleRequest(StrictModel):
    scenario: ExposureScenario = Field(
        ..., description="Source external exposure scenario to map into PBPK MCP import fields."
    )
    context_of_use: str = Field(
        default="screening-brief",
        description="Downstream orchestration context such as screening-brief.",
    )
    scientific_purpose: str = Field(
        default="external exposure scenario translation for PBPK",
        description="Human-readable scientific purpose for the PBPK-side context object.",
    )
    decision_context: str = Field(
        default="upstream external exposure context only",
        description="Decision-context text to preserve PBPK boundary semantics.",
    )
    requested_output: str | None = Field(
        default=None,
        description="Optional target output label to prefill PBPK assessment-context metadata.",
    )
    comparison_metric: Literal["cmax", "tmax", "auc"] = Field(
        default="cmax",
        description="PBPK comparison metric for the downstream BER-input placeholder.",
    )
    source_platform: str = Field(
        default="exposure-scenario-mcp",
        description="Source platform name written into the PBPK import request.",
    )
    source_version: str = Field(
        default="0.1.0",
        description="Source platform version written into the PBPK import request.",
    )
    model_name: str | None = Field(
        default=None,
        description="Optional model name for the PBPK-side import record.",
    )
    operator: str | None = Field(
        default=None, description="Optional operator name for downstream auditability."
    )
    sponsor: str | None = Field(
        default=None, description="Optional sponsor name for downstream auditability."
    )


class ExportToxClawEvidenceBundleRequest(StrictModel):
    scenario: ExposureScenario = Field(
        ..., description="Scenario to convert into ToxClaw evidence/report primitives."
    )
    case_id: str = Field(..., description="Target ToxClaw case identifier.")
    report_id: str = Field(..., description="Target ToxClaw report identifier.")
    context_of_use: str = Field(
        default="screening-brief",
        description="Workflow context in which ToxClaw will consume the evidence.",
    )
    section_key: str = Field(
        default="exposure-scenario",
        description="Deterministic report-section key for the exported section.",
    )
    section_title: str = Field(
        default="Exposure Scenario",
        description="Human-readable title for the report section.",
    )
    data_classification: Literal["public", "internal", "restricted", "regulated"] = Field(
        default="internal",
        description="ToxClaw data-classification tag for the evidence record.",
    )
    trust_label: Literal[
        "module-output", "untrusted-document", "untrusted-external-data"
    ] = Field(
        default="module-output",
        description="ToxClaw evidence trust label.",
    )
    run_id: str | None = Field(
        default=None, description="Optional ToxClaw run identifier if already known."
    )


class ExportToxClawRefinementBundleRequest(StrictModel):
    baseline: ExposureScenario = Field(
        ..., description="Baseline scenario retained as the screening reference point."
    )
    comparison: ExposureScenario = Field(
        ..., description="Refined or alternate scenario to compare against the baseline."
    )
    case_id: str = Field(..., description="Target ToxClaw case identifier.")
    report_id: str = Field(..., description="Target ToxClaw report identifier.")
    workflow_action: Literal[
        "scenario_comparison", "route_recalculation", "aggregate_variant"
    ] = Field(
        default="scenario_comparison",
        description=(
            "Why the comparison is being emitted: a simple comparison, a route-specific "
            "recalculation, or an aggregate-variant refinement."
        ),
    )
    context_of_use: str = Field(
        default="screening-refinement",
        description="Workflow context in which ToxClaw will consume the refinement bundle.",
    )
    section_key: str = Field(
        default="exposure-refinement",
        description="Deterministic report-section key for the exported refinement section.",
    )
    section_title: str = Field(
        default="Exposure Refinement Delta",
        description="Human-readable title for the refinement report section.",
    )
    data_classification: Literal["public", "internal", "restricted", "regulated"] = Field(
        default="internal",
        description="ToxClaw data-classification tag for the refinement evidence record.",
    )
    trust_label: Literal[
        "module-output", "untrusted-document", "untrusted-external-data"
    ] = Field(
        default="module-output",
        description="ToxClaw evidence trust label.",
    )
    run_id: str | None = Field(
        default=None, description="Optional ToxClaw run identifier if already known."
    )


class CompareExposureScenariosInput(StrictModel):
    baseline: ExposureScenario = Field(..., description="Baseline scenario.")
    comparison: ExposureScenario = Field(..., description="Comparison scenario.")


class ToolResultMeta(StrictModel):
    schema_version: Literal["toolResultMeta.v1"] = Field(
        default="toolResultMeta.v1", alias="schemaVersion"
    )
    execution_mode: Literal["sync", "async"] = Field(..., alias="executionMode")
    result_status: Literal["accepted", "running", "completed", "failed"] = Field(
        ..., alias="resultStatus"
    )
    terminal: bool
    future_async_compatible: bool = Field(default=True, alias="futureAsyncCompatible")
    queue_required: bool = Field(default=False, alias="queueRequired")
    response_schema: str | None = Field(default=None, alias="responseSchema")
    job_id: str | None = Field(default=None, alias="jobId")
    status_check_uri: str | None = Field(default=None, alias="statusCheckUri")
    retryable: bool = False
    error_code: str | None = Field(default=None, alias="errorCode")
    notes: list[str] = Field(default_factory=list)


class PublicSurfaceSummary(StrictModel):
    tool_count: int = Field(..., alias="toolCount", ge=0)
    resource_count: int = Field(..., alias="resourceCount", ge=0)
    prompt_count: int = Field(..., alias="promptCount", ge=0)
    transports: list[Literal["stdio", "streamable-http"]] = Field(default_factory=list)


class ReleaseReadinessCheck(StrictModel):
    check_id: str = Field(..., alias="checkId")
    title: str
    status: Literal["pass", "warning", "blocked"]
    blocking: bool = False
    evidence: str
    recommendation: str | None = None


class ReleaseReadinessReport(StrictModel):
    schema_version: Literal["releaseReadinessReport.v1"] = Field(
        default="releaseReadinessReport.v1", alias="schemaVersion"
    )
    release_candidate: str = Field(..., alias="releaseCandidate")
    server_name: str = Field(..., alias="serverName")
    server_version: str = Field(..., alias="serverVersion")
    defaults_version: str = Field(..., alias="defaultsVersion")
    status: Literal["ready", "ready_with_known_limitations", "blocked"]
    summary: str
    public_surface: PublicSurfaceSummary = Field(..., alias="publicSurface")
    validation_commands: list[str] = Field(default_factory=list, alias="validationCommands")
    checks: list[ReleaseReadinessCheck] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list, alias="knownLimitations")


class ReviewedSurfaceIndex(StrictModel):
    tool_names: list[str] = Field(default_factory=list, alias="toolNames")
    resource_uris: list[str] = Field(default_factory=list, alias="resourceUris")
    prompt_names: list[str] = Field(default_factory=list, alias="promptNames")


class SecurityProvenanceReviewFinding(StrictModel):
    finding_id: str = Field(..., alias="findingId")
    category: Literal[
        "contract_integrity",
        "defaults_integrity",
        "provenance_auditability",
        "deterministic_evidence_hashing",
        "transport_security",
        "scientific_boundary",
    ]
    title: str
    status: Literal["pass", "warning", "blocked"]
    applies_to: list[str] = Field(default_factory=list, alias="appliesTo")
    evidence: str
    recommendation: str | None = None
    references: list[str] = Field(default_factory=list)


class SecurityProvenanceReviewReport(StrictModel):
    schema_version: Literal["securityProvenanceReviewReport.v1"] = Field(
        default="securityProvenanceReviewReport.v1", alias="schemaVersion"
    )
    review_id: str = Field(..., alias="reviewId")
    server_name: str = Field(..., alias="serverName")
    server_version: str = Field(..., alias="serverVersion")
    defaults_version: str = Field(..., alias="defaultsVersion")
    reviewed_at: str = Field(..., alias="reviewedAt")
    status: Literal["acceptable", "acceptable_with_warnings", "blocked"]
    summary: str
    reviewed_surface: ReviewedSurfaceIndex = Field(..., alias="reviewedSurface")
    findings: list[SecurityProvenanceReviewFinding] = Field(default_factory=list)
    external_requirements: list[str] = Field(default_factory=list, alias="externalRequirements")


class ReleaseDistributionArtifact(StrictModel):
    kind: Literal["wheel", "sdist"]
    filename: str
    relative_path: str = Field(..., alias="relativePath")
    present: bool
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, alias="sizeBytes", ge=0)


class ReleaseMetadataReport(StrictModel):
    schema_version: Literal["releaseMetadataReport.v1"] = Field(
        default="releaseMetadataReport.v1", alias="schemaVersion"
    )
    release_version: str = Field(..., alias="releaseVersion")
    package_name: str = Field(..., alias="packageName")
    package_version: str = Field(..., alias="packageVersion")
    server_name: str = Field(..., alias="serverName")
    server_version: str = Field(..., alias="serverVersion")
    defaults_version: str = Field(..., alias="defaultsVersion")
    readiness_status: Literal["ready", "ready_with_known_limitations", "blocked"] = Field(
        ..., alias="readinessStatus"
    )
    security_review_status: Literal["acceptable", "acceptable_with_warnings", "blocked"] = Field(
        ..., alias="securityReviewStatus"
    )
    benchmark_case_count: int = Field(..., alias="benchmarkCaseCount", ge=0)
    benchmark_case_ids: list[str] = Field(default_factory=list, alias="benchmarkCaseIds")
    contract_schema_count: int = Field(..., alias="contractSchemaCount", ge=0)
    contract_example_count: int = Field(..., alias="contractExampleCount", ge=0)
    distribution_artifacts: list[ReleaseDistributionArtifact] = Field(
        default_factory=list, alias="distributionArtifacts"
    )
    published_docs: list[str] = Field(default_factory=list, alias="publishedDocs")
    validation_commands: list[str] = Field(default_factory=list, alias="validationCommands")
    migration_notes: list[str] = Field(default_factory=list, alias="migrationNotes")
    known_limitations: list[str] = Field(default_factory=list, alias="knownLimitations")


class VerificationCheck(StrictModel):
    check_id: str = Field(..., alias="checkId")
    title: str
    status: Literal["pass", "warning", "blocked"]
    blocking: bool = False
    evidence: str
    related_resources: list[str] = Field(default_factory=list, alias="relatedResources")
    recommendation: str | None = None


class VerificationSummaryReport(StrictModel):
    schema_version: Literal["verificationSummaryReport.v1"] = Field(
        default="verificationSummaryReport.v1", alias="schemaVersion"
    )
    server_name: str = Field(..., alias="serverName")
    server_version: str = Field(..., alias="serverVersion")
    release_version: str = Field(..., alias="releaseVersion")
    defaults_version: str = Field(..., alias="defaultsVersion")
    status: Literal["pass", "warning", "blocked"]
    summary: str
    public_surface: PublicSurfaceSummary = Field(..., alias="publicSurface")
    release_readiness_status: Literal["ready", "ready_with_known_limitations", "blocked"] = Field(
        ..., alias="releaseReadinessStatus"
    )
    security_review_status: Literal["acceptable", "acceptable_with_warnings", "blocked"] = Field(
        ..., alias="securityReviewStatus"
    )
    validation_domain_count: int = Field(..., alias="validationDomainCount", ge=0)
    benchmark_case_count: int = Field(..., alias="benchmarkCaseCount", ge=0)
    external_dataset_count: int = Field(..., alias="externalDatasetCount", ge=0)
    reference_band_count: int = Field(..., alias="referenceBandCount", ge=0)
    time_series_pack_count: int = Field(..., alias="timeSeriesPackCount", ge=0)
    goldset_case_count: int = Field(..., alias="goldsetCaseCount", ge=0)
    unmapped_goldset_case_ids: list[str] = Field(
        default_factory=list, alias="unmappedGoldsetCaseIds"
    )
    published_resources: list[str] = Field(default_factory=list, alias="publishedResources")
    validation_commands: list[str] = Field(default_factory=list, alias="validationCommands")
    checks: list[VerificationCheck] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ContractToolEntry(StrictModel):
    name: str
    request_schema: str | None = None
    response_schema: str | None = None
    description: str


class ContractResourceEntry(StrictModel):
    uri: str
    description: str


class ContractPromptEntry(StrictModel):
    name: str
    description: str


class ContractManifest(StrictModel):
    schema_version: Literal["contractManifest.v1"] = "contractManifest.v1"
    server_name: str
    server_version: str
    defaults_version: str
    tools: list[ContractToolEntry]
    resources: list[ContractResourceEntry]
    prompts: list[ContractPromptEntry]
    schemas: dict[str, str]
    examples: dict[str, str]

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, value: str) -> str:
        if not value.endswith("_mcp"):
            raise ValueError("MCP server names should end with '_mcp'.")
        return value
