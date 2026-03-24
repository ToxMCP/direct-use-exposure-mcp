from __future__ import annotations

import json
from pathlib import Path

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    CompareExposureScenariosInput,
    ExportPbpkScenarioInputRequest,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_scenarios,
    export_pbpk_input,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "benchmark_cases.json"


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def build_request(payload: dict) -> ExposureScenarioRequest | InhalationScenarioRequest:
    if payload["route"] == "inhalation":
        return InhalationScenarioRequest(**payload)
    return ExposureScenarioRequest(**payload)


def build_scenario(engine: ScenarioEngine, payload: dict):
    return engine.build(build_request(payload))


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

        raise AssertionError(f"Unsupported benchmark kind: {case['kind']}")
