"""Modern HTTP routing, security, and real calculation isolation checks."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anyio
import pytest
from mcp import Client
from starlette.testclient import TestClient

from exposure_scenario_mcp.server import create_mcp_server
from exposure_scenario_mcp.transport.http import create_http_app
from scripts.protocol_probe import stable

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "2026-07-28"


def request(method, params=None, request_id=1):
    params = {
        **(params or {}),
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL,
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }
    body = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL,
        "Mcp-Method": method,
    }
    if method in {"tools/call", "resources/read"}:
        headers["Mcp-Name"] = params.get("name", params.get("uri", ""))
    return body, headers


def post(client, method, params=None, request_id=1):
    body, headers = request(method, params, request_id)
    return client.post("/mcp", json=body, headers=headers)


@pytest.fixture
def app():
    return create_http_app()


def test_sessionless_discovery_and_private_catalog_hints(app):
    with TestClient(app, base_url="http://localhost:8000") as client:
        for method, key, count in [
            ("tools/list", "tools", 39),
            ("resources/list", "resources", 63),
            ("resources/templates/list", "resourceTemplates", 2),
            ("prompts/list", "prompts", 2),
        ]:
            response = post(client, method)
            assert response.status_code == 200
            assert "mcp-session-id" not in response.headers
            result = response.json()["result"]
            assert len(result[key]) == count
            assert result["ttlMs"] == 60_000
            assert result["cacheScope"] == "private"
        discovery = post(client, "server/discover").json()["result"]
        assert PROTOCOL in discovery["supportedVersions"]


@pytest.mark.parametrize("version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"])
def test_supported_legacy_http_versions(app, version):
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": version}
    with TestClient(app, base_url="http://localhost:8000") as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": version,
                    "capabilities": {},
                    "clientInfo": {"name": "legacy-compatibility", "version": "1"},
                },
            },
        )
        assert initialized.status_code == 200
        assert initialized.json()["result"]["protocolVersion"] == version
        tools = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        assert tools.status_code == 200
        assert len(tools.json()["result"]["tools"]) == 39


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("Mcp-Method", "resources/list"),
        ("Mcp-Name", "other"),
        ("Mcp-Method", None),
        ("Mcp-Name", None),
    ],
)
def test_missing_or_mismatched_routing_headers(app, header, value):
    body, headers = request(
        "tools/call", {"name": "exposure_run_verification_checks", "arguments": {}}
    )
    if value is None:
        headers.pop(header)
    else:
        headers[header] = value
    with TestClient(app, base_url="http://localhost:8000") as client:
        response = client.post("/mcp", json=body, headers=headers)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == -32020


@pytest.mark.parametrize(
    ("header", "value", "status"),
    [("Host", "attacker.example", 421), ("Origin", "https://attacker.example", 403)],
)
def test_untrusted_host_or_origin(app, header, value, status):
    body, headers = request("tools/list")
    headers[header] = value
    with TestClient(app, base_url="http://localhost:8000") as client:
        assert client.post("/mcp", json=body, headers=headers).status_code == status


def test_malformed_unknown_and_oversized_requests_recover(app):
    with TestClient(app, base_url="http://localhost:8000") as client:
        _, headers = request("tools/list")
        malformed = client.post(
            "/mcp", content="{", headers={**headers, "Content-Type": "application/json"}
        )
        assert malformed.status_code == 400
        assert malformed.json()["error"]["code"] == -32700
        unknown = post(client, "unknown/method")
        assert unknown.status_code == 404
        assert unknown.json()["error"]["code"] == -32601
        oversized = client.post("/mcp", content=b"x" * (4_194_304 + 1), headers=headers)
        assert oversized.status_code == 413
        assert post(client, "tools/list").status_code == 200


def test_domain_and_resource_errors_preserve_semantics(app):
    fixtures = json.loads((ROOT / "tests/compatibility/requests.json").read_text())
    call = next(item for item in fixtures["calls"] if item["label"] == "domain-error")
    with TestClient(app, base_url="http://localhost:8000") as client:
        result = post(
            client,
            "tools/call",
            {
                "name": call["name"],
                "arguments": call["arguments"],
            },
        ).json()["result"]
        assert result["isError"] is True
        assert result["_meta"]["errorCode"] == "jurisdiction_not_supported"
        assert result["_meta"]["mcpErrorCode"] == -32602
        missing = post(client, "resources/read", {"uri": "schemas://does-not-exist"})
        error = missing.json()["error"]
        assert error["code"] == -32602
        assert error["data"]["resourceType"] == "schema"
        assert error["data"]["resourceName"] == "does-not-exist"


def test_parallel_real_calls_reuse_ids_without_cross_talk_or_file_writes(app):
    fixture = json.loads((ROOT / "tests/compatibility/requests.json").read_text())
    jobs = [
        item
        for item in fixture["calls"]
        if item["label"] in {"worker-inhalation", "worker-dermal", "pbpk"}
    ]
    tracked = [ROOT / "defaults/manifest.json", ROOT / "docs/contracts/contract_manifest.json"]
    before = [
        (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in tracked
    ]
    with TestClient(app, base_url="http://localhost:8000") as client:

        def run(call):
            response = post(
                client,
                "tools/call",
                {
                    "name": call["name"],
                    "arguments": call["arguments"],
                },
                request_id=7,
            )
            assert response.status_code == 200
            result = response.json()["result"]
            assert result["isError"] is False
            return stable(result["structuredContent"])

        expected = [run(call) for call in jobs]
        with ThreadPoolExecutor(max_workers=6) as pool:
            assert list(pool.map(run, jobs * 4)) == expected * 4
    assert before == [
        (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()) for path in tracked
    ]


def test_cancelling_async_call_keeps_real_server_healthy():
    server = create_mcp_server()

    @server.tool()
    async def slow_test_tool() -> str:
        await anyio.sleep(10)
        return "late"

    async def exercise():
        async with Client(server) as client:
            with anyio.move_on_after(0.05) as cancelled:
                await client.call_tool("slow_test_tool", {})
            assert cancelled.cancel_called
            result = await client.call_tool("exposure_run_verification_checks", {})
            assert result.is_error is False

    anyio.run(exercise)
