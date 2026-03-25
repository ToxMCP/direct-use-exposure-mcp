"""Assumption capture and provenance helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ApplicabilityStatus,
    AssumptionGovernance,
    AssumptionSourceReference,
    DefaultVisibility,
    EvidenceBasis,
    EvidenceGrade,
    ExposureAssumptionRecord,
    FitForPurpose,
    LimitationNote,
    ProvenanceBundle,
    QualityFlag,
    ScalarValue,
    Severity,
    SourceKind,
    TierLevel,
    TierSemantics,
    UncertaintyType,
)

SYSTEM_SOURCE = AssumptionSourceReference(
    source_id="exposure_scenario_mcp",
    title="Exposure Scenario MCP runtime",
    locator="docs://algorithm-notes",
    version="0.1.0",
    hash_sha256=None,
)

DEFAULT_SOURCE_GRADE_HINTS = {
    "benchmark_": EvidenceGrade.GRADE_3,
    "epa_": EvidenceGrade.GRADE_4,
    "echa_": EvidenceGrade.GRADE_3,
    "heuristic_": EvidenceGrade.GRADE_1,
}

ASSUMPTION_UNCERTAINTY_TYPES: dict[str, tuple[UncertaintyType, ...]] = {
    "body_weight_kg": (UncertaintyType.VARIABILITY,),
    "inhalation_rate_m3_per_hour": (UncertaintyType.VARIABILITY,),
    "exposed_surface_area_cm2": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.PARAMETER_UNCERTAINTY,
    ),
    "density_g_per_ml": (UncertaintyType.PARAMETER_UNCERTAINTY,),
    "retention_factor": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "transfer_efficiency": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "ingestion_fraction": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.PARAMETER_UNCERTAINTY,
    ),
    "aerosolized_fraction": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "room_volume_m3": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "air_exchange_rate_per_hour": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "exposure_duration_hours": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "source_distance_m": (
        UncertaintyType.SCENARIO_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "spray_duration_seconds": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "near_field_volume_m3": (
        UncertaintyType.SCENARIO_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "airflow_directionality": (
        UncertaintyType.SCENARIO_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "particle_size_regime": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "near_field_exchange_turnover_per_hour": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "particle_persistence_factor": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.MODEL_UNCERTAINTY,
    ),
    "interzonal_mixing_rate_m3_per_hour": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "near_field_active_spray_concentration_mg_per_m3": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "far_field_average_air_concentration_mg_per_m3": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "breathing_zone_time_weighted_average_mg_per_m3": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "use_events_per_day": (UncertaintyType.VARIABILITY,),
    "use_amount_per_event": (
        UncertaintyType.VARIABILITY,
        UncertaintyType.PARAMETER_UNCERTAINTY,
    ),
    "concentration_fraction": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "product_mass_g_per_event": (UncertaintyType.PARAMETER_UNCERTAINTY,),
    "chemical_mass_mg_per_event": (
        UncertaintyType.PARAMETER_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "external_mass_mg_per_day": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "released_mass_mg_per_event": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "average_air_concentration_mg_per_m3": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "inhaled_mass_mg_per_day": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
    "normalized_external_dose_mg_per_kg_day": (
        UncertaintyType.MODEL_UNCERTAINTY,
        UncertaintyType.SCENARIO_UNCERTAINTY,
    ),
}

ASSUMPTION_DOMAIN_FIELDS: dict[str, tuple[str, ...]] = {
    "body_weight_kg": ("population_group", "region"),
    "inhalation_rate_m3_per_hour": ("population_group", "region"),
    "exposed_surface_area_cm2": ("population_group", "region"),
    "density_g_per_ml": ("product_category", "physical_form"),
    "retention_factor": (
        "product_category",
        "physical_form",
        "application_method",
        "retention_type",
    ),
    "transfer_efficiency": ("product_category", "physical_form", "application_method"),
    "ingestion_fraction": ("product_category", "application_method", "population_group"),
    "aerosolized_fraction": ("product_category", "physical_form", "application_method"),
    "room_volume_m3": ("region", "product_category", "application_method"),
    "air_exchange_rate_per_hour": ("region", "product_category", "application_method"),
    "exposure_duration_hours": ("region", "application_method"),
    "source_distance_m": ("application_method", "physical_form"),
    "spray_duration_seconds": ("application_method", "physical_form"),
    "near_field_volume_m3": ("application_method", "physical_form", "region"),
    "airflow_directionality": ("application_method", "physical_form", "region"),
    "particle_size_regime": ("application_method", "physical_form"),
    "near_field_exchange_turnover_per_hour": (
        "application_method",
        "physical_form",
        "region",
    ),
    "particle_persistence_factor": ("application_method", "physical_form"),
    "use_events_per_day": ("population_group", "product_category", "application_method"),
    "use_amount_per_event": ("product_category", "physical_form", "application_method"),
    "concentration_fraction": ("product_category", "physical_form"),
}


@dataclass(slots=True)
class AssumptionTracker:
    """Collects explicit assumptions, limitations, and quality flags."""

    registry: DefaultsRegistry
    assumptions: list[ExposureAssumptionRecord] = field(default_factory=list)
    limitations: list[LimitationNote] = field(default_factory=list)
    quality_flags: list[QualityFlag] = field(default_factory=list)
    scenario_context: dict[str, ScalarValue] = field(default_factory=dict)

    def set_context(self, **context: ScalarValue) -> None:
        self.scenario_context = {key: value for key, value in context.items() if value is not None}

    def _evidence_grade(
        self,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
    ) -> EvidenceGrade | None:
        if source_kind != SourceKind.DEFAULT_REGISTRY:
            return None
        for prefix, grade in DEFAULT_SOURCE_GRADE_HINTS.items():
            if source.source_id.startswith(prefix):
                return grade
        return EvidenceGrade.GRADE_2

    def _evidence_basis(
        self,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
    ) -> EvidenceBasis:
        if source_kind == SourceKind.USER_INPUT:
            return EvidenceBasis.EXPLICIT_INPUT
        if source_kind == SourceKind.DERIVED:
            return EvidenceBasis.DERIVED
        if source.source_id.startswith("heuristic_"):
            return EvidenceBasis.HEURISTIC_DEFAULT
        return EvidenceBasis.CURATED_DEFAULT

    def _default_visibility(
        self,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
    ) -> DefaultVisibility:
        if source_kind == SourceKind.DEFAULT_REGISTRY and source.source_id.startswith("heuristic_"):
            return DefaultVisibility.WARN
        return DefaultVisibility.SILENT_TRACEABLE

    def _applicability_status(
        self,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
    ) -> ApplicabilityStatus:
        if source_kind == SourceKind.USER_INPUT:
            return ApplicabilityStatus.USER_ASSERTED
        if source_kind == SourceKind.DERIVED:
            return ApplicabilityStatus.DERIVED
        if source.source_id.startswith("heuristic_"):
            return ApplicabilityStatus.SCREENING_EXTRAPOLATION
        return ApplicabilityStatus.IN_DOMAIN

    def _uncertainty_types(self, name: str) -> list[UncertaintyType]:
        return list(ASSUMPTION_UNCERTAINTY_TYPES.get(name, ()))

    def _applicability_domain(self, name: str) -> dict[str, ScalarValue]:
        field_names = ASSUMPTION_DOMAIN_FIELDS.get(name)
        if not field_names:
            return dict(self.scenario_context)
        return {
            key: value
            for key, value in self.scenario_context.items()
            if key in field_names and value is not None
        }

    def _governance(
        self,
        name: str,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
    ) -> AssumptionGovernance:
        return AssumptionGovernance(
            evidence_grade=self._evidence_grade(source_kind, source),
            evidence_basis=self._evidence_basis(source_kind, source),
            default_visibility=self._default_visibility(source_kind, source),
            applicability_status=self._applicability_status(source_kind, source),
            uncertainty_types=self._uncertainty_types(name),
            applicability_domain=self._applicability_domain(name),
        )

    def add(
        self,
        name: str,
        value: str | float | int | bool | None,
        unit: str | None,
        source_kind: SourceKind,
        source: AssumptionSourceReference,
        confidence: str,
        default_applied: bool,
        rationale: str,
    ) -> None:
        self.assumptions.append(
            ExposureAssumptionRecord(
                name=name,
                value=value,
                unit=unit,
                source_kind=source_kind,
                source=source,
                confidence=confidence,
                default_applied=default_applied,
                rationale=rationale,
                governance=self._governance(name, source_kind, source),
            )
        )

    def add_user(
        self, name: str, value: str | float | int | bool | None, unit: str | None, rationale: str
    ) -> None:
        self.add(
            name=name,
            value=value,
            unit=unit,
            source_kind=SourceKind.USER_INPUT,
            source=SYSTEM_SOURCE,
            confidence="explicit_user_input",
            default_applied=False,
            rationale=rationale,
        )

    def add_default(
        self,
        name: str,
        value: str | float | int | bool | None,
        unit: str | None,
        source: AssumptionSourceReference,
        rationale: str,
    ) -> None:
        self.add(
            name=name,
            value=value,
            unit=unit,
            source_kind=SourceKind.DEFAULT_REGISTRY,
            source=source,
            confidence="registry_default",
            default_applied=True,
            rationale=rationale,
        )
        self.quality_flags.append(
            QualityFlag(
                code="default_applied",
                severity=Severity.INFO,
                message=f"Default value applied for '{name}'.",
            )
        )
        if source.source_id.startswith("heuristic_"):
            self.quality_flags.append(
                QualityFlag(
                    code="heuristic_default_source",
                    severity=Severity.WARNING,
                    message=(
                        f"Default value for '{name}' comes from a heuristic screening source "
                        "rather than a curated factor pack."
                    ),
                )
            )

    def add_derived(
        self, name: str, value: str | float | int | bool | None, unit: str | None, rationale: str
    ) -> None:
        self.add(
            name=name,
            value=value,
            unit=unit,
            source_kind=SourceKind.DERIVED,
            source=SYSTEM_SOURCE,
            confidence="deterministic_derived",
            default_applied=False,
            rationale=rationale,
        )

    def add_limitation(
        self, code: str, message: str, severity: Severity = Severity.WARNING
    ) -> None:
        self.limitations.append(LimitationNote(code=code, message=message, severity=severity))

    def add_quality_flag(self, code: str, message: str, severity: Severity = Severity.INFO) -> None:
        self.quality_flags.append(QualityFlag(code=code, message=message, severity=severity))

    def fit_for_purpose(self, scenario_label: str) -> FitForPurpose:
        return FitForPurpose(
            label=scenario_label,
            suitable_for=[
                "screening prioritization",
                "PBPK scenario preparation",
                "auditable scenario comparison",
            ],
            not_suitable_for=[
                "internal exposure estimation",
                "final risk characterization",
                "population-scale probabilistic inference",
            ],
        )

    def tier_semantics(
        self,
        *,
        tier_claimed: TierLevel,
        tier_earned: TierLevel | None = None,
        tier_rationale: str,
        required_caveats: list[str] | None = None,
        forbidden_interpretations: list[str] | None = None,
        assumption_checks_passed: bool = True,
    ) -> TierSemantics:
        return TierSemantics(
            tier_claimed=tier_claimed,
            tier_earned=tier_earned or tier_claimed,
            tier_rationale=tier_rationale,
            assumption_checks_passed=assumption_checks_passed,
            required_caveats=required_caveats or [],
            forbidden_interpretations=forbidden_interpretations or [],
        )

    def provenance(
        self,
        plugin_id: str,
        algorithm_id: str,
        plugin_version: str = "0.1.0",
        generated_at: str | None = None,
    ) -> ProvenanceBundle:
        return ProvenanceBundle(
            algorithm_id=algorithm_id,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            defaults_version=self.registry.version,
            defaults_hash_sha256=self.registry.sha256,
            generated_at=generated_at or datetime.now(UTC).isoformat(),
            notes=[
                "Deterministic-first v0.1 engine.",
                "All defaults are surfaced through exposureAssumptionRecord entries.",
            ],
        )
