"""Assumption capture and provenance helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    AssumptionSourceReference,
    ExposureAssumptionRecord,
    FitForPurpose,
    LimitationNote,
    ProvenanceBundle,
    QualityFlag,
    Severity,
    SourceKind,
)

SYSTEM_SOURCE = AssumptionSourceReference(
    source_id="exposure_scenario_mcp",
    title="Exposure Scenario MCP runtime",
    locator="docs://algorithm-notes",
    version="0.1.0",
    hash_sha256=None,
)


@dataclass(slots=True)
class AssumptionTracker:
    """Collects explicit assumptions, limitations, and quality flags."""

    registry: DefaultsRegistry
    assumptions: list[ExposureAssumptionRecord] = field(default_factory=list)
    limitations: list[LimitationNote] = field(default_factory=list)
    quality_flags: list[QualityFlag] = field(default_factory=list)

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

    def provenance(
        self, plugin_id: str, algorithm_id: str, plugin_version: str = "0.1.0"
    ) -> ProvenanceBundle:
        return ProvenanceBundle(
            algorithm_id=algorithm_id,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            defaults_version=self.registry.version,
            defaults_hash_sha256=self.registry.sha256,
            generated_at=datetime.now(UTC).isoformat(),
            notes=[
                "Deterministic-first v0.1 engine.",
                "All defaults are surfaced through exposureAssumptionRecord entries.",
            ],
        )
