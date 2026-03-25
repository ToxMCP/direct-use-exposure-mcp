from __future__ import annotations

import json
from pathlib import Path

import pytest

from exposure_scenario_mcp.archetypes import ArchetypeLibraryRegistry
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.integrations import build_pbpk_external_import_package
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    BuildProbabilityBoundsFromScenarioPackageInput,
    CompareExposureScenariosInput,
    ExportPbpkExternalImportBundleRequest,
    ExportPbpkScenarioInputRequest,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_screening_scenario
from exposure_scenario_mcp.probability_bounds import build_probability_bounds_from_scenario_package
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)
from exposure_scenario_mcp.scenario_probability_packages import ScenarioProbabilityPackageRegistry
from exposure_scenario_mcp.uncertainty import enrich_scenario_uncertainty

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "benchmark_cases.json"


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def build_request(
    payload: dict,
) -> ExposureScenarioRequest | InhalationScenarioRequest | InhalationTier1ScenarioRequest:
    if payload.get("schema_version") == "inhalationTier1ScenarioRequest.v1":
        return InhalationTier1ScenarioRequest(**payload)
    if payload["route"] == "inhalation":
        return InhalationScenarioRequest(**payload)
    return ExposureScenarioRequest(**payload)


def build_scenario(engine: ScenarioEngine, payload: dict):
    request = build_request(payload)
    if isinstance(request, InhalationTier1ScenarioRequest):
        return enrich_scenario_uncertainty(
            engine,
            build_inhalation_tier_1_screening_scenario(request, DefaultsRegistry.load()),
        )
    return engine.build(request)


def assumption_values(scenario) -> dict[str, object]:
    return {item.name: item.value for item in scenario.assumptions}


def test_benchmark_corpus_matches_engine_outputs() -> None:
    engine = build_engine()
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["defaults_version"] == DefaultsRegistry.load().version

    for case in fixture["cases"]:
        expected = case["expected"]

        if case["kind"] == "scenario":
            scenario = build_scenario(engine, case["request"])
            assert scenario.external_dose.value == pytest.approx(
                expected["external_dose_value"], rel=1e-6
            ), case["id"]
            assert scenario.external_dose.unit.value == expected["external_dose_unit"], case["id"]
            for metric_name, expected_value in expected["route_metrics"].items():
                assert scenario.route_metrics[metric_name] == pytest.approx(
                    expected_value, rel=1e-6
                ), case["id"]
            for assumption_name, expected_value in expected.get("assumptions", {}).items():
                assert assumption_values(scenario)[assumption_name] == pytest.approx(
                    expected_value, rel=1e-6
                ), case["id"]
            assert scenario.provenance.defaults_version == fixture["defaults_version"], case["id"]
            continue

        if case["kind"] == "aggregate":
            component_scenarios = [
                build_scenario(engine, payload) for payload in case["component_requests"]
            ]
            summary = aggregate_scenarios(
                BuildAggregateExposureScenarioInput(
                    chemical_id=component_scenarios[0].chemical_id,
                    label=case["id"],
                    component_scenarios=component_scenarios,
                ),
                DefaultsRegistry.load(),
            )
            assert summary.normalized_total_external_dose is not None, case["id"]
            assert summary.normalized_total_external_dose.value == pytest.approx(
                expected["normalized_total_external_dose_value"], rel=1e-6
            ), case["id"]
            actual_route_totals = {
                item.route.value: item.total_dose.value for item in summary.per_route_totals
            }
            for route_name, expected_value in expected["route_totals"].items():
                assert actual_route_totals[route_name] == pytest.approx(
                    expected_value, rel=1e-6
                ), case["id"]
            route_by_scenario_id = {
                item.scenario_id: item.route.value for item in summary.component_scenarios
            }
            actual_contributors = {
                route_by_scenario_id[item.scenario_id]: item.contribution_fraction
                for item in summary.dominant_contributors
            }
            for route_name, expected_value in expected["dominant_contributor_fractions"].items():
                assert actual_contributors[route_name] == pytest.approx(
                    expected_value, rel=1e-6
                ), case["id"]
            assert [item.code for item in summary.limitations] == expected["limitation_codes"], (
                case["id"]
            )
            assert summary.provenance.defaults_version == fixture["defaults_version"], case["id"]
            continue

        if case["kind"] == "comparison":
            record = compare_scenarios(
                CompareExposureScenariosInput(
                    baseline=build_scenario(engine, case["baseline_request"]),
                    comparison=build_scenario(engine, case["comparison_request"]),
                ),
                DefaultsRegistry.load(),
            )
            assert record.absolute_delta == pytest.approx(expected["absolute_delta"], rel=1e-6), (
                case["id"]
            )
            assert record.percent_delta == expected["percent_delta"], case["id"]
            assert [item.name for item in record.changed_assumptions] == expected[
                "changed_assumptions"
            ], case["id"]
            assert record.interpretation_notes == expected["interpretation_notes"], case["id"]
            assert record.provenance.defaults_version == fixture["defaults_version"], case["id"]
            continue

        if case["kind"] == "pbpk_export":
            exported = export_pbpk_input(
                ExportPbpkScenarioInputRequest(
                    scenario=build_scenario(engine, case["request"]),
                    regimen_name=case["regimen_name"],
                ),
                DefaultsRegistry.load(),
            )
            assert exported.dose_magnitude == pytest.approx(
                expected["dose_magnitude"], rel=1e-6
            ), case["id"]
            assert exported.dose_unit.value == expected["dose_unit"], case["id"]
            assert exported.timing_pattern == expected["timing_pattern"], case["id"]
            assert exported.population_context.population_group == expected["population_context"][
                "population_group"
            ], case["id"]
            assert exported.population_context.body_weight_kg == pytest.approx(
                expected["population_context"]["body_weight_kg"], rel=1e-6
            ), case["id"]
            assert exported.population_context.region == expected["population_context"]["region"], (
                case["id"]
            )
            assert len(exported.supporting_assumption_names) == expected[
                "supporting_assumption_count"
            ], case["id"]
            assert exported.provenance.defaults_version == fixture["defaults_version"], case["id"]
            continue

        if case["kind"] == "pbpk_external_import_package":
            source_scenario = build_scenario(engine, case["request"])
            exported = build_pbpk_external_import_package(
                ExportPbpkExternalImportBundleRequest(scenario=source_scenario)
            )
            payload = exported.model_dump(mode="json", by_alias=True)

            assert payload["ingestToolName"] == expected["ingest_tool_name"], case["id"]
            assert payload["bundle"]["sourcePlatform"] == expected["source_platform"], case["id"]
            assert payload["bundle"]["sourceVersion"] == expected["source_version"], case["id"]
            assert payload["bundle"]["modelType"] == expected["model_type"], case["id"]
            expected_run_id = f"{source_scenario.scenario_id}-external-context"
            assert payload["bundle"]["runId"] == expected_run_id, case["id"]
            assert payload["bundle"]["assessmentContext"]["contextOfUse"] == expected[
                "context_of_use"
            ], case["id"]
            assert payload["bundle"]["assessmentContext"]["doseScenario"]["scenarioId"] == (
                source_scenario.scenario_id
            ), case["id"]
            assert payload["bundle"]["assessmentContext"]["doseScenario"][
                "bodyWeightKg"
            ] == pytest.approx(expected["body_weight_kg"], rel=1e-6), case["id"]
            assert payload["bundle"]["chemicalIdentity"]["preferredName"] == expected[
                "preferred_name"
            ], case["id"]
            assert sorted(payload["bundle"]["supportingHandoffs"]) == expected[
                "supporting_handoff_keys"
            ], case["id"]
            assert payload["bundle"]["supportingHandoffs"]["pbpkScenarioInput"][
                "schema_version"
            ] == expected["pbpk_scenario_schema_version"], case["id"]
            assert payload["requestPayload"]["sourcePlatform"] == expected["source_platform"], (
                case["id"]
            )
            assert payload["requestPayload"]["comparisonMetric"] == expected[
                "comparison_metric"
            ], case["id"]
            assert payload["toolCall"]["toolName"] == expected["ingest_tool_name"], case["id"]
            assert payload["toolCall"]["arguments"]["sourcePlatform"] == expected[
                "source_platform"
            ], case["id"]
            assert payload["toxclawModuleParams"]["ingestToolName"] == expected[
                "ingest_tool_name"
            ], case["id"]
            assert payload["compatibilityReport"]["target_tool"] == expected[
                "compatibility_target"
            ], case["id"]
            assert payload["compatibilityReport"]["ready_for_external_pbpk_import"] is expected[
                "compatibility_ready"
            ], case["id"]
            assert payload["compatibilityReport"]["missing_external_bundle_fields"] == expected[
                "missing_external_bundle_fields"
            ], case["id"]
            continue

        if case["kind"] == "scenario_package_probability":
            summary = build_probability_bounds_from_scenario_package(
                BuildProbabilityBoundsFromScenarioPackageInput(**case["request"]),
                engine,
                DefaultsRegistry.load(),
                ArchetypeLibraryRegistry.load(),
                ScenarioProbabilityPackageRegistry.load(),
            )
            assert summary.route.value == expected["route"], case["id"]
            assert summary.scenario_class.value == expected["scenario_class"], case["id"]
            assert summary.package_profile_id == expected["package_profile_id"], case["id"]
            assert summary.archetype_library_set_id == expected["archetype_library_set_id"], (
                case["id"]
            )
            assert summary.minimum_dose.value == pytest.approx(
                expected["minimum_dose_value"], rel=1e-6
            ), case["id"]
            assert summary.maximum_dose.value == pytest.approx(
                expected["maximum_dose_value"], rel=1e-6
            ), case["id"]
            assert [item.template_id for item in summary.support_points] == expected[
                "support_point_template_ids"
            ], case["id"]
            assert all(
                item.scenario.tier_semantics.tier_claimed.value
                == expected["support_point_tier_claimed"]
                for item in summary.support_points
            ), case["id"]
            assert all(
                item.scenario.route_metrics["tier1_product_profile_id"]
                == expected["support_point_profile_id"]
                for item in summary.support_points
            ), case["id"]
            assert summary.provenance.defaults_version == fixture["defaults_version"], case["id"]
            continue

        raise AssertionError(f"Unsupported benchmark kind: {case['kind']}")
