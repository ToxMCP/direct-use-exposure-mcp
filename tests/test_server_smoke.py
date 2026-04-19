"""End-to-end smoke tests through the FastMCP server object."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS

from exposure_scenario_mcp.examples import build_examples
from exposure_scenario_mcp.models import (
    CompareJurisdictionalScenariosInput,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.server import create_mcp_server


@pytest.fixture
def server():
    return create_mcp_server()


def _run(coro):
    return asyncio.run(coro)


def test_call_core_tool_verification_checks(server):
    result = _run(server.call_tool("exposure_run_verification_checks", {}))
    assert not result.isError
    assert result.content[0].text.startswith("Built verification summary")
    payload = result.structuredContent
    assert payload["status"] in {"ok", "warning"}


def test_call_core_tool_compare_jurisdictional_scenarios(server):
    request = CompareJurisdictionalScenariosInput(
        request=ExposureScenarioRequest(
            chemical_id="TCM-COMPARE-TOOL-001",
            route=Route.ORAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="herbal_medicinal_product",
                physical_form="solid",
                application_method="direct_oral",
                retention_type="leave_on",
                concentration_fraction=0.05,
                use_amount_per_event=0.5,
                use_amount_unit="g",
                use_events_per_day=2,
            ),
            population_profile=PopulationProfile(population_group="adult", region="global"),
        ),
        jurisdictions=["global", "china"],
    )

    result = _run(
        server.call_tool(
            "exposure_compare_jurisdictional_scenarios",
            {"params": request.model_dump(mode="json", by_alias=True)},
        )
    )

    assert not result.isError
    assert result.content[0].text.startswith("Compared 2 jurisdictions.")
    payload = result.structuredContent
    assert payload["comparedJurisdictions"] == ["global", "china"]
    assert payload["fitForPurpose"]["label"] == "jurisdictional_comparison_screening"
    assert payload["provenance"]["algorithm_id"] == "scenario.compare_jurisdictional.v1"


def test_read_resource_contracts_manifest(server):
    contents = _run(server.read_resource("contracts://manifest"))
    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    assert payload["server_name"] == "exposure_scenario_mcp"
    assert len(payload["tools"]) >= 35


def test_read_resource_invalid_schema_returns_error_json(server):
    with pytest.raises(McpError) as exc_info:
        _run(server.read_resource("schemas://nonexistent_schema"))

    assert exc_info.value.error.code == INVALID_PARAMS
    assert exc_info.value.error.message == "Schema 'nonexistent_schema' not found."
    assert exc_info.value.error.data["resourceType"] == "schema"
    assert exc_info.value.error.data["resourceName"] == "nonexistent_schema"


def test_read_resource_invalid_example_returns_error_json(server):
    with pytest.raises(McpError) as exc_info:
        _run(server.read_resource("examples://nonexistent_example"))

    assert exc_info.value.error.code == INVALID_PARAMS
    assert exc_info.value.error.message == "Example 'nonexistent_example' not found."
    assert exc_info.value.error.data["resourceType"] == "example"
    assert exc_info.value.error.data["resourceName"] == "nonexistent_example"


def test_get_prompt_refinement_playbook(server):
    prompt = _run(
        server.get_prompt(
            "exposure_refinement_playbook",
            arguments={"route": "dermal"},
        )
    )
    text = prompt.messages[0].content.text
    assert "dermal" in text


def test_call_worker_route_alias(server):
    request = WorkerTaskRoutingInput(
        chemical_id="WORKER-ROUTE-001",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="industrial_maintenance",
            physical_form="liquid",
            application_method="pour_transfer",
            retention_type="surface_contact",
            concentration_fraction=0.15,
            use_amount_per_event=12.0,
            use_amount_unit="mL",
            use_events_per_day=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="worker",
            demographic_tags=["worker"],
            region="EU",
        ),
        prefer_current_mcp=False,
    )

    result = _run(
        server.call_tool(
            "worker_route_task",
            {"params": request.model_dump(mode="json", by_alias=True)},
        )
    )

    assert not result.isError
    assert result.content[0].text.startswith("Routed worker task for route dermal.")
    payload = result.structuredContent
    assert payload["recommended_tool"] == "worker_export_dermal_absorbed_dose_bridge"


def test_export_toxclaw_evidence_bundle_unexpected_error_returns_failed_tool_result(
    server, monkeypatch
):
    request = ExposureScenarioRequest(
        chemical_id="TOXCLAW-ERROR-001",
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
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(population_group="adult", region="EU"),
    )
    scenario_result = _run(
        server.call_tool(
            "exposure_build_screening_exposure_scenario",
            {"params": request.model_dump(mode="json", by_alias=True)},
        )
    )
    assert not scenario_result.isError

    def boom(_params):
        raise ValueError("boom")

    monkeypatch.setattr(
        "exposure_scenario_mcp.server_tools_core.build_toxclaw_evidence_bundle",
        boom,
    )

    result = _run(
        server._tool_manager.call_tool(
            "exposure_export_toxclaw_evidence_bundle",
            {
                "params": {
                    "scenario": scenario_result.structuredContent,
                    "case_id": "case-1",
                    "report_id": "report-1",
                }
            },
            convert_result=False,
        )
    )

    assert result.isError
    assert result.meta["errorCode"] == "InternalError"
    assert result.meta["mcpErrorCode"] == INTERNAL_ERROR
    assert "Unexpected failure while executing" in result.content[0].text


def test_build_product_use_evidence_from_nanomaterial_unexpected_error_returns_failed_tool_result(
    server, monkeypatch
):
    payloads = build_examples()

    def boom(_params):
        raise ValueError("boom")

    monkeypatch.setattr(
        "exposure_scenario_mcp.server_tools_integration.build_product_use_evidence_from_nanomaterial",
        boom,
    )

    result = _run(
        server._tool_manager.call_tool(
            "exposure_build_product_use_evidence_from_nanomaterial",
            {"params": {"evidence": payloads["nanomaterial_evidence_record"]}},
            convert_result=False,
        )
    )

    assert result.isError
    assert result.meta["errorCode"] == "InternalError"
    assert result.meta["mcpErrorCode"] == INTERNAL_ERROR
    assert "Unexpected failure while executing" in result.content[0].text


def test_worker_route_task_unexpected_error_returns_failed_tool_result(server, monkeypatch):
    payloads = build_examples()

    def boom(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(
        "exposure_scenario_mcp.server_tools_worker.route_worker_task",
        boom,
    )

    result = _run(
        server._tool_manager.call_tool(
            "worker_route_task",
            {"params": payloads["worker_task_routing_request"]},
            convert_result=False,
        )
    )

    assert result.isError
    assert result.meta["errorCode"] == "InternalError"
    assert result.meta["mcpErrorCode"] == INTERNAL_ERROR
    assert "Unexpected failure while executing" in result.content[0].text
