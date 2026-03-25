"""Public data contracts for Exposure Scenario MCP."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ScalarValue = str | float | int | bool | None


class StrictModel(BaseModel):
    """Common Pydantic configuration for all public models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)


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


class ValidationStatus(StrEnum):
    VERIFICATION_ONLY = "verification_only"
    BENCHMARK_REGRESSION = "benchmark_regression"
    EXTERNAL_VALIDATION_PARTIAL = "external_validation_partial"
    CALIBRATED = "calibrated"


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


class ValidationSummary(StrictModel):
    validation_status: ValidationStatus = Field(..., alias="validationStatus")
    route_mechanism: str = Field(..., alias="routeMechanism")
    benchmark_case_ids: list[str] = Field(default_factory=list, alias="benchmarkCaseIds")
    external_dataset_ids: list[str] = Field(default_factory=list, alias="externalDatasetIds")
    highest_supported_uncertainty_tier: UncertaintyTier = Field(
        ..., alias="highestSupportedUncertaintyTier"
    )
    probabilistic_enablement: Literal["blocked", "gated", "enabled"] = Field(
        ..., alias="probabilisticEnablement"
    )
    notes: list[str] = Field(default_factory=list)


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


class ProductUseProfile(StrictModel):
    schema_version: Literal["productUseProfile.v1"] = "productUseProfile.v1"
    product_name: str | None = Field(
        default=None, description="Optional human-readable product label."
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
    assumption_overrides: dict[str, ScalarValue] = Field(
        default_factory=dict, description="Additional explicit overrides for auditability."
    )


class InhalationScenarioRequest(ExposureScenarioRequest):
    scenario_class: ScenarioClass = Field(
        default=ScenarioClass.INHALATION, description="Requested scenario class."
    )

    @model_validator(mode="after")
    def validate_inhalation_route(self) -> InhalationScenarioRequest:
        if self.route != Route.INHALATION:
            raise ValueError("InhalationScenarioRequest requires route='inhalation'.")
        return self


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


class AggregateExposureSummary(StrictModel):
    schema_version: Literal["aggregateExposureSummary.v1"] = "aggregateExposureSummary.v1"
    scenario_id: str = Field(..., description="Aggregate scenario identifier.")
    chemical_id: str = Field(..., description="Shared chemical identifier.")
    scenario_class: Literal["aggregate"] = "aggregate"
    component_scenarios: list[AggregateComponentReference] = Field(
        ..., description="Component scenario references."
    )
    aggregation_method: str = Field(..., description="Aggregation method description.")
    normalized_total_external_dose: ScenarioDose | None = Field(
        default=None, description="Summed normalized total when units are compatible."
    )
    per_route_totals: list[RouteDoseTotal] = Field(
        default_factory=list, description="Route-wise totals."
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
    component_scenarios: list[ExposureScenario] = Field(
        ..., min_length=1, description="Component scenarios to aggregate."
    )


class EnvelopeArchetypeInput(StrictModel):
    label: str = Field(..., description="Human-readable archetype label.")
    description: str = Field(..., description="Why this archetype belongs in the envelope.")
    request: ExposureScenarioRequest = Field(
        ..., description="Full scenario request representing one deterministic archetype."
    )


class BuildExposureEnvelopeInput(StrictModel):
    schema_version: Literal["buildExposureEnvelopeInput.v1"] = "buildExposureEnvelopeInput.v1"
    chemical_id: str = Field(..., description="Chemical ID shared across archetypes.")
    label: str = Field(..., description="Human-readable envelope label.")
    archetypes: list[EnvelopeArchetypeInput] = Field(
        ..., min_length=2, description="Named deterministic archetypes to evaluate."
    )


class EnvelopeArchetypeResult(StrictModel):
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


class ExportPbpkScenarioInputRequest(StrictModel):
    scenario: ExposureScenario = Field(..., description="Scenario to export for PBPK consumption.")
    regimen_name: str | None = Field(
        default=None, description="Optional human-readable regimen name."
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
