"""Synthetic boundaries for the deterministic aggregate and evidence-fit contracts."""

from __future__ import annotations

from fractions import Fraction

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    ProductUseEvidenceRecord,
    apply_product_use_evidence,
    assess_product_use_evidence_fit,
    reconcile_product_use_evidence,
)
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    ExposureScenario,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    RouteBioavailabilityAdjustment,
    ScenarioClass,
    Severity,
)
from exposure_scenario_mcp.plugins import ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine, aggregate_scenarios


def request(
    *,
    group: str = "adult",
    weight: float = 70.0,
    product: str = "Synthetic use A",
    amount: float = 1.0,
) -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="synthetic-aggregate-review",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name=product,
            product_category="personal_care",
            physical_form="liquid",
            application_method="direct_oral",
            retention_type="leave_on",
            concentration_fraction=0.01,
            use_amount_per_event=amount,
            use_amount_unit="g",
            use_events_per_day=1,
            ingestion_fraction=1,
        ),
        population_profile=PopulationProfile(
            population_group=group, body_weight_kg=weight, region="global"
        ),
    )


def build(req: ExposureScenarioRequest) -> ExposureScenario:
    plugins = PluginRegistry()
    plugins.register(ScreeningScenarioPlugin())
    return ScenarioEngine(plugins, DefaultsRegistry.load()).build(req)


def aggregate(*scenarios: ExposureScenario, **kwargs):
    return aggregate_scenarios(
        BuildAggregateExposureScenarioInput(
            chemical_id="synthetic-aggregate-review",
            label="Artificial aggregate review control",
            component_scenarios=list(scenarios),
            **kwargs,
        ),
        DefaultsRegistry.load(),
    )


def test_compatible_independent_uses_preserve_arithmetic_and_scope_limit() -> None:
    result = aggregate(build(request()), build(request(product="Synthetic use B", amount=2)))
    assert result.normalized_total_external_dose is not None
    assert result.normalized_total_external_dose.value == pytest.approx(float(Fraction(30, 70)))
    assert not any(flag.severity == Severity.ERROR for flag in result.quality_flags)
    assert "aggregate_component_overlap_unresolved" not in {
        flag.code for flag in result.quality_flags
    }
    assert "aggregate_scope_unverified" in {flag.code for flag in result.quality_flags}
    assert result.validation_summary is not None
    assert "aggregate_scope_and_co_use_unverified" in result.validation_summary.validation_gap_ids


@pytest.mark.parametrize(
    "other",
    [
        request(group="child", weight=15),
        request(weight=60),
        request().model_copy(
            update={
                "population_profile": PopulationProfile(
                    population_group="adult", body_weight_kg=70, region="EU"
                )
            }
        ),
        request().model_copy(
            update={
                "population_profile": PopulationProfile(
                    population_group="adult", body_weight_kg=70, demographic_tags=["female"]
                )
            }
        ),
    ],
    ids=["adult-child", "different-denominator", "different-region", "different-cohort"],
)
def test_mixed_contexts_are_error_flagged_and_arithmetic_is_inspectable(other) -> None:
    result = aggregate(build(request()), build(other))
    assert any(
        flag.code == "aggregate_population_mismatch" and flag.severity == Severity.ERROR
        for flag in result.quality_flags
    )
    assert any(
        note.code == "aggregate_population_mismatch" and note.severity == Severity.ERROR
        for note in result.limitations
    )
    assert result.normalized_total_external_dose is not None
    assert "aggregate-population-mismatch" in {
        entry.entry_id for entry in result.uncertainty_register
    }


def test_calculation_denominator_cannot_be_hidden_by_rewriting_profile_or_flags() -> None:
    original = build(request(weight=60))
    altered = original.model_copy(
        update={
            "population_profile": PopulationProfile(population_group="adult", body_weight_kg=70),
            "quality_flags": [],
            "limitations": [],
        }
    )
    result = aggregate(build(request()), altered)
    codes = {flag.code for flag in result.quality_flags}
    assert "aggregate_component_population_inconsistent" in codes
    assert "aggregate_population_mismatch" in codes


def test_missing_denominator_stays_unresolved() -> None:
    scenario = build(request()).model_copy(
        update={
            "population_profile": PopulationProfile(population_group="adult"),
            "assumptions": [],
        }
    )
    result = aggregate(scenario)
    assert any(
        flag.code == "aggregate_population_context_incomplete" and flag.severity == Severity.ERROR
        for flag in result.quality_flags
    )


def test_multiple_missing_contexts_keep_distinct_uncertainty_references() -> None:
    components = [
        build(request(product=product)).model_copy(
            update={
                "population_profile": PopulationProfile(population_group="adult"),
                "assumptions": [],
            }
        )
        for product in ("Synthetic use A", "Synthetic use B")
    ]
    result = aggregate(*components)
    entries = [
        entry
        for entry in result.uncertainty_register
        if entry.entry_id.startswith("aggregate-population-context-incomplete")
    ]
    assert len(entries) == 2
    assert len({entry.entry_id for entry in entries}) == 2
    for component in components:
        assert any(component.scenario_id in entry.summary for entry in entries)


def test_case_and_tag_order_do_not_create_population_mismatch() -> None:
    left = build(request())
    right = build(request(product="Synthetic use B"))
    left = left.model_copy(
        update={
            "population_profile": PopulationProfile(
                population_group="Adult",
                body_weight_kg=70,
                region="GLOBAL",
                demographic_tags=["female", "adult"],
            )
        }
    )
    right = right.model_copy(
        update={
            "population_profile": PopulationProfile(
                population_group="adult",
                body_weight_kg=70,
                region="global",
                demographic_tags=["ADULT", "Female"],
            )
        }
    )
    result = aggregate(left, right)
    assert "aggregate_population_mismatch" not in {flag.code for flag in result.quality_flags}


def test_rebuilt_same_use_warns_without_inventing_event_identity_or_deduplicating() -> None:
    left, right = build(request()), build(request())
    assert left.scenario_id != right.scenario_id
    result = aggregate(left, right)
    assert any(
        flag.code == "aggregate_component_overlap_unresolved" and flag.severity == Severity.WARNING
        for flag in result.quality_flags
    )
    assert result.normalized_total_external_dose is not None
    assert result.normalized_total_external_dose.value == left.external_dose.value * 2


@pytest.mark.parametrize("fractions", [[0.1, 0.9], [0.9, 0.1], [0.1, 0.1]])
@pytest.mark.parametrize("mode", ["external_summary", "internal_equivalent"])
def test_duplicate_route_adjustments_are_rejected_regardless_of_order(fractions, mode) -> None:
    with pytest.raises(ExposureScenarioError) as error:
        aggregate(
            build(request()),
            aggregationMode=mode,
            routeBioavailabilityAdjustments=[
                RouteBioavailabilityAdjustment(route=Route.ORAL, bioavailabilityFraction=value)
                for value in fractions
            ],
        )
    assert error.value.code == "aggregate_duplicate_bioavailability_route"


def test_unique_route_adjustment_preserves_result() -> None:
    result = aggregate(
        build(request()),
        build(request(product="Synthetic use B", amount=2)),
        aggregationMode="internal_equivalent",
        routeBioavailabilityAdjustments=[
            RouteBioavailabilityAdjustment(route=Route.ORAL, bioavailabilityFraction=0.25)
        ],
    )
    assert result.internal_equivalent_total_dose is not None
    assert result.internal_equivalent_total_dose.value == pytest.approx(float(Fraction(30, 70) / 4))


@pytest.mark.parametrize("status", ["unreviewed", "provisional"])
def test_unreviewed_evidence_is_compatible_but_requires_review_in_strict_paths(status) -> None:
    evidence = ProductUseEvidenceRecord(
        chemical_id="synthetic-aggregate-review",
        source_name="Artificial matching evidence control",
        source_kind="user_upload",
        review_status=status,
        product_use_categories=["personal_care"],
        physical_forms=["liquid"],
        application_methods=["direct_oral"],
        retention_types=["leave_on"],
        region_scopes=["global"],
    )
    report = assess_product_use_evidence_fit(request(), evidence)
    assert report.compatible is True
    assert report.auto_apply_safe is False
    assert report.recommendation == "accept_with_review"
    assert any("review_status" in warning for warning in report.warnings)
    with pytest.raises(ExposureScenarioError) as error:
        apply_product_use_evidence(request(), evidence, require_auto_apply_safe=True)
    assert error.value.code == "product_use_evidence_requires_review"
    reconciliation = reconcile_product_use_evidence(
        request(), [evidence], require_auto_apply_safe=True
    )
    assert reconciliation.manual_review_required is True
    assert reconciliation.recommendation == "manual_review"
    exploratory = apply_product_use_evidence(request(), evidence)
    assert exploratory.assumption_overrides["external_product_use_review_status"] == status


def test_matching_reviewed_record_keeps_technical_application_behavior() -> None:
    evidence = ProductUseEvidenceRecord(
        chemical_id="synthetic-aggregate-review",
        source_name="Artificial reviewed-label control",
        source_kind="user_upload",
        review_status="reviewed",
        product_use_categories=["personal_care"],
        physical_forms=["liquid"],
        application_methods=["direct_oral"],
        retention_types=["leave_on"],
        region_scopes=["global"],
    )
    report = assess_product_use_evidence_fit(request(), evidence)
    assert report.auto_apply_safe is True
    assert report.recommendation == "accept"
    # The caller's label is not a signature or a TTC qualification.
    assert report.schema_version == "productUseEvidenceFitReport.v1"
