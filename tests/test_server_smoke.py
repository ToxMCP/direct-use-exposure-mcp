"""End-to-end smoke tests through the FastMCP server object."""

from __future__ import annotations

import asyncio
import json

import pytest

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
