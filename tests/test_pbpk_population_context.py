"""Denominator preservation across the native and external-import PBPK handoffs."""

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    build_pbpk_external_import_package,
    check_pbpk_compatibility,
)
from exposure_scenario_mcp.models import (
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
)
from exposure_scenario_mcp.runtime import export_pbpk_input
from tests.test_aggregate_review import build, request


def test_mismatch_preserves_original_dose_and_denominator_in_every_export() -> None:
    original = build(request(weight=60))
    changed = original.model_copy(
        update={
            "population_profile": original.population_profile.model_copy(
                update={"body_weight_kg": 70}
            ),
            "quality_flags": [],
            "limitations": [],
        }
    )
    native = export_pbpk_input(
        ExportPbpkScenarioInputRequest(scenario=changed), DefaultsRegistry.load()
    )
    assert native.population_context.body_weight_kg == 60
    assert native.dose_magnitude == original.external_dose.value
    assert "pbpk_population_context_inconsistent" in {x.code for x in native.limitations}
    package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(scenario=changed)
    )
    wire = package.model_dump(mode="json", by_alias=True)
    for context in [
        wire["bundle"]["assessmentContext"],
        wire["requestPayload"]["assessmentContext"],
        wire["toolCall"]["arguments"]["assessmentContext"],
        wire["toxclawModuleParams"]["arguments"]["assessmentContext"],
    ]:
        assert context["doseScenario"]["bodyWeightKg"] == 60
        assert context["doseScenario"]["externalDose"]["value"] == original.external_dose.value
    assert not package.compatibility_report.ready_for_external_pbpk_import
    assert not package.compatibility_report.compatible
    assert "pbpk_population_context_inconsistent" in {
        x.code for x in package.compatibility_report.issues
    }


@pytest.mark.parametrize("retained", [False, True])
def test_coherent_native_or_profile_only_retained_records_remain_compatible(retained) -> None:
    scenario = build(request(weight=60))
    if retained:
        scenario = scenario.model_copy(update={"assumptions": []})
    package = build_pbpk_external_import_package(
        ExportPbpkExternalImportBundleRequest(scenario=scenario)
    )
    assert package.compatibility_report.ready_for_external_pbpk_import
    assert package.bundle.assessment_context["doseScenario"]["bodyWeightKg"] == 60


@pytest.mark.parametrize("value", [None, True, "60", 0, -1, float("nan"), float("inf")])
def test_invalid_recorded_denominator_cannot_fall_back_to_valid_profile(value) -> None:
    scenario = build(request(weight=60))
    changed = scenario.model_copy(
        update={
            "assumptions": [
                x.model_copy(update={"value": value}) if x.name == "body_weight_kg" else x
                for x in scenario.assumptions
            ]
        }
    )
    assert not check_pbpk_compatibility(changed).ready_for_external_pbpk_import
    with pytest.raises(ExposureScenarioError) as caught:
        export_pbpk_input(ExportPbpkScenarioInputRequest(scenario=changed), DefaultsRegistry.load())
    assert caught.value.code in {"pbpk_body_weight_invalid", "pbpk_body_weight_missing"}


@pytest.mark.parametrize(
    ("weight", "unit", "ready"), [(60, "kg", True), (70, "kg", False), (60, "lb", False)]
)
def test_repeated_recorded_values_require_unambiguous_kg_context(weight, unit, ready) -> None:
    scenario = build(request(weight=60))
    assumption = next(x for x in scenario.assumptions if x.name == "body_weight_kg")
    changed = scenario.model_copy(
        update={
            "assumptions": [
                *scenario.assumptions,
                assumption.model_copy(update={"value": weight, "unit": unit}),
            ]
        }
    )
    assert check_pbpk_compatibility(changed).ready_for_external_pbpk_import is ready


def test_absent_context_returns_actionable_error_without_inventing_a_denominator() -> None:
    scenario = build(request(weight=60))
    scenario = scenario.model_copy(
        update={
            "assumptions": [],
            "population_profile": scenario.population_profile.model_copy(
                update={"body_weight_kg": None}
            ),
        }
    )
    assert not check_pbpk_compatibility(scenario).ready_for_external_pbpk_import
    with pytest.raises(ExposureScenarioError) as caught:
        build_pbpk_external_import_package(ExportPbpkExternalImportBundleRequest(scenario=scenario))
    assert caught.value.code == "pbpk_body_weight_missing"
