"""Exercise patched SDK HTTP limits and session cleanup on the real server app."""

from __future__ import annotations

import asyncio
import time

import pytest
from starlette.testclient import TestClient

from exposure_scenario_mcp.server import create_mcp_server


@pytest.fixture
def app():
    return create_mcp_server().streamable_http_app(
        max_request_body_size=512,
        max_sessions=1,
        session_idle_timeout=0.5,
        json_response=True,
    )


def test_http_rejects_declared_and_streamed_oversized_bodies(app) -> None:
    path = "/mcp"
    query = b""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "root_path": "",
        "query_string": query,
        "headers": [
            (b"host", b"localhost:8000"),
            (b"content-type", b"application/json"),
            (b"accept", b"application/json, text/event-stream"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8000),
    }

    async def exercise_app() -> None:
        async with app.router.lifespan_context(app):
            declared_reads = 0
            declared_responses = []

            async def declared_receive():
                nonlocal declared_reads
                declared_reads += 1
                return {"type": "http.request", "body": b"x" * 513, "more_body": False}

            async def declared_send(message):
                declared_responses.append(message)

            declared_scope = {**scope, "headers": [*scope["headers"], (b"content-length", b"513")]}
            await app(declared_scope, declared_receive, declared_send)
            assert declared_responses[0]["status"] == 413
            assert declared_reads == 0

            frames = [
                {"type": "http.request", "body": b"x" * 300, "more_body": True},
                {"type": "http.request", "body": b"x" * 300, "more_body": True},
                {"type": "http.request", "body": b"unread", "more_body": False},
            ]
            streamed_reads = 0
            streamed_responses = []

            async def streamed_receive():
                nonlocal streamed_reads
                streamed_reads += 1
                return frames.pop(0)

            async def streamed_send(message):
                streamed_responses.append(message)

            await app(scope, streamed_receive, streamed_send)
            assert streamed_responses[0]["status"] == 413
            assert streamed_reads == 2
            assert frames == [{"type": "http.request", "body": b"unread", "more_body": False}]

    asyncio.run(exercise_app())


def test_stateful_http_reclaims_deleted_and_idle_sessions(app) -> None:
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "security-regression", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}

    with TestClient(app, base_url="http://localhost:8000") as client:
        first = client.post("/mcp", json=initialize, headers=headers)
        assert first.status_code == 200
        first_id = first.headers["mcp-session-id"]
        assert client.post("/mcp", json=initialize, headers=headers).status_code == 503

        deleted = client.delete("/mcp", headers={**headers, "mcp-session-id": first_id})
        assert deleted.status_code == 200
        replacement = client.post("/mcp", json=initialize, headers=headers)
        assert replacement.status_code == 200
        replacement_id = replacement.headers["mcp-session-id"]
        assert replacement_id != first_id

        # Bounded retry only creates new sessions, leaving the old session idle.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            resumed = client.post("/mcp", json=initialize, headers=headers)
            if resumed.status_code != 503:
                break
            time.sleep(0.02)
        assert resumed.status_code == 200
        assert resumed.headers["mcp-session-id"] != replacement_id
        stale = client.get("/mcp", headers={**headers, "mcp-session-id": replacement_id})
        assert stale.status_code == 404
