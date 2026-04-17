"""End-to-end smoke tests through the FastMCP server object."""

from __future__ import annotations

import asyncio
import json

import pytest

from exposure_scenario_mcp.models import (
    CompareJurisdictionalScenariosInput,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
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
    contents = _run(server.read_resource("schemas://nonexistent_schema"))
    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    assert "error" in payload
    assert "nonexistent_schema" in payload["error"]


def test_read_resource_invalid_example_returns_error_json(server):
    contents = _run(server.read_resource("examples://nonexistent_example"))
    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    assert "error" in payload
    assert "nonexistent_example" in payload["error"]


def test_get_prompt_refinement_playbook(server):
    prompt = _run(
        server.get_prompt(
            "exposure_refinement_playbook",
            arguments={"route": "dermal"},
        )
    )
    text = prompt.messages[0].content.text
    assert "dermal" in text
