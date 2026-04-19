from __future__ import annotations

from mcp.types import INTERNAL_ERROR, INVALID_PARAMS

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine
from exposure_scenario_mcp.server import _error_result, _success_result


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_success_result_emits_future_safe_sync_meta() -> None:
    scenario = build_engine().build(
        ExposureScenarioRequest(
            chemical_id="DTXSID7020182",
            chemical_name="Example Solvent A",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="personal_care",
                physical_form="cream",
                application_method="hand_application",
                retention_type="leave_on",
                concentration_fraction=0.02,
                use_amount_per_event=1.5,
                use_amount_unit="g",
                use_events_per_day=3,
            ),
            population_profile=PopulationProfile(population_group="adult"),
        )
    )

    result = _success_result("Built scenario.", scenario)

    assert result.meta is not None
    assert result.meta["schemaVersion"] == "toolResultMeta.v1"
    assert result.meta["executionMode"] == "sync"
    assert result.meta["resultStatus"] == "completed"
    assert result.meta["terminal"] is True
    assert result.meta["queueRequired"] is False
    assert result.meta["responseSchema"] == "exposureScenario.v1"
    assert result.structuredContent is not None


def test_error_result_emits_failed_meta_without_queue_semantics() -> None:
    error = ExposureScenarioError(
        code="example_failure",
        message="Illustrative failure.",
    )

    result = _error_result(error)

    assert result.isError is True
    assert result.meta is not None
    assert result.meta["schemaVersion"] == "toolResultMeta.v1"
    assert result.meta["resultStatus"] == "failed"
    assert result.meta["executionMode"] == "sync"
    assert result.meta["errorCode"] == "example_failure"
    assert result.meta["mcpErrorCode"] == INVALID_PARAMS
    assert result.meta["jobId"] is None
    assert result.meta["statusCheckUri"] is None


def test_internal_error_result_uses_internal_mcp_error_code() -> None:
    error = ExposureScenarioError(
        code="InternalError",
        message="Illustrative internal failure.",
    )

    result = _error_result(error)

    assert result.isError is True
    assert result.meta is not None
    assert result.meta["errorCode"] == "InternalError"
    assert result.meta["mcpErrorCode"] == INTERNAL_ERROR
