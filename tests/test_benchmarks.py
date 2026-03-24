from __future__ import annotations

import json
from pathlib import Path

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import ExposureScenarioRequest, InhalationScenarioRequest
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "benchmark_cases.json"


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_benchmark_corpus_matches_engine_outputs() -> None:
    engine = build_engine()
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["defaults_version"] == DefaultsRegistry.load().version

    for case in fixture["cases"]:
        if case["request"]["route"] == "inhalation":
            request = InhalationScenarioRequest(**case["request"])
        else:
            request = ExposureScenarioRequest(**case["request"])

        scenario = engine.build(request)
        expected = case["expected"]

        assert scenario.external_dose.value == pytest.approx(
            expected["external_dose_value"], rel=1e-6
        ), case["id"]
        assert scenario.external_dose.unit.value == expected["external_dose_unit"], case["id"]
        for metric_name, expected_value in expected["route_metrics"].items():
            assert scenario.route_metrics[metric_name] == pytest.approx(expected_value, rel=1e-6), (
                case["id"]
            )
        assert scenario.provenance.defaults_version == fixture["defaults_version"], case["id"]
