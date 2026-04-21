from __future__ import annotations

import json
from pathlib import Path

import anyio
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from exposure_scenario_mcp.http_audit import (
    build_http_audit_replay_report,
    build_http_audit_runtime_context,
    load_http_audit_events,
    summarize_http_audit_events,
)
from exposure_scenario_mcp.http_security import (
    ConcurrencyLimitMiddleware,
    RequestTimeoutMiddleware,
    apply_http_boundary_security,
    build_http_boundary_security_config,
)


async def _complete_lifespan(receive, send) -> None:
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
            continue
        if message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _tool_response_app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await _complete_lifespan(receive, send)
        return
    body = b""
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    request = json.loads(body or b"{}")
    response = JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "_meta": {"resultStatus": "completed"},
                "structuredContent": {
                    "qualityFlags": [{"code": "review-warning"}],
                    "limitations": [{"code": "screening-only"}],
                    "manualReviewRequired": True,
                },
            },
        }
    )
    await response(scope, receive, send)


async def _json_rpc_error_app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await _complete_lifespan(receive, send)
        return
    response = JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "boom"},
        },
        status_code=500,
    )
    await response(scope, receive, send)


async def _slow_app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await _complete_lifespan(receive, send)
        return
    await anyio.sleep(0.05)
    response = JSONResponse({"ok": True})
    await response(scope, receive, send)


async def _plain_json_app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await _complete_lifespan(receive, send)
        return
    response = JSONResponse({"ok": True})
    await response(scope, receive, send)


def test_http_audit_sink_records_redacted_stable_digests(tmp_path: Path) -> None:
    audit_path = tmp_path / "http-audit.jsonl"
    app = apply_http_boundary_security(
        _tool_response_app,
        build_http_boundary_security_config(
            max_request_bytes=0,
            request_timeout_seconds=0,
            max_concurrency=0,
            audit_log_path=audit_path,
        ),
    )

    request_a = (
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"'
        'exposure_run_verification_checks","arguments":{"sessionToken":"secret-a"}}}'
    )
    request_b = (
        '{"id":1,"params":{"arguments":{"sessionToken":"secret-b"},"name":"'
        'exposure_run_verification_checks"},"method":"tools/call","jsonrpc":"2.0"}'
    )

    with TestClient(app) as client:
        first = client.post("/", content=request_a, headers={"Content-Type": "application/json"})
        second = client.post("/", content=request_b, headers={"Content-Type": "application/json"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["x-exposure-audit-request-id"]

    events = load_http_audit_events(audit_path)
    assert len(events) == 2
    assert events[0]["normalizedInputDigestSha256"] == events[1]["normalizedInputDigestSha256"]
    assert events[0]["operationKind"] == "tool"
    assert events[0]["operationName"] == "exposure_run_verification_checks"
    assert events[0]["qualityFlagCodes"] == ["review-warning"]
    assert events[0]["limitationCodes"] == ["screening-only"]
    assert events[0]["manualReviewRequired"] is True
    reproducibility = events[0]["reproducibility"]
    assert reproducibility["releaseVersion"]
    assert reproducibility["defaultsVersion"]
    assert len(reproducibility["defaultsHashSha256"]) == 64
    assert reproducibility["defaultsManifestResource"] == "defaults://manifest"
    assert reproducibility["releaseMetadataResource"] == "release://metadata-report"

    summary = summarize_http_audit_events(events)
    assert summary["totalEvents"] == 2
    assert summary["manualReviewEventCount"] == 2
    assert summary["operationCounts"]["exposure_run_verification_checks"] == 2
    assert summary["defaultsVersionCounts"][reproducibility["defaultsVersion"]] == 2
    assert summary["releaseVersionCounts"][reproducibility["releaseVersion"]] == 2


def test_http_audit_sink_records_rpc_failures(tmp_path: Path) -> None:
    audit_path = tmp_path / "http-audit-errors.jsonl"
    app = apply_http_boundary_security(
        _json_rpc_error_app,
        build_http_boundary_security_config(
            max_request_bytes=0,
            request_timeout_seconds=0,
            max_concurrency=0,
            audit_log_path=audit_path,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "boom"}},
        )

    assert response.status_code == 500
    events = load_http_audit_events(audit_path)
    assert len(events) == 1
    assert events[0]["resultStatus"] == "failed"
    assert events[0]["exceptionSummary"] == "boom"


def test_request_timeout_middleware_returns_gateway_timeout() -> None:
    app = RequestTimeoutMiddleware(_slow_app, timeout_seconds=0.01)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 504
    assert response.json()["error"] == "request_timed_out"


def test_concurrency_limit_middleware_rejects_when_capacity_is_exhausted() -> None:
    app = ConcurrencyLimitMiddleware(_plain_json_app, max_concurrency=1)
    assert app._semaphore.acquire(blocking=False)

    try:
        with TestClient(app) as client:
            response = client.get("/")
    finally:
        app._semaphore.release()

    assert response.status_code == 503
    assert response.json()["error"] == "server_busy"


def test_http_audit_replay_report_filters_by_request_id_and_digest(tmp_path: Path) -> None:
    audit_path = tmp_path / "http-audit-replay.jsonl"
    app = apply_http_boundary_security(
        _tool_response_app,
        build_http_boundary_security_config(
            max_request_bytes=0,
            request_timeout_seconds=0,
            max_concurrency=0,
            audit_log_path=audit_path,
        ),
    )

    with TestClient(app) as client:
        first = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "exposure_run_verification_checks"},
            },
        )
        client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "exposure_run_verification_checks"},
            },
        )

    events = load_http_audit_events(audit_path)
    replay = build_http_audit_replay_report(
        events,
        request_id=first.headers["x-exposure-audit-request-id"],
    )

    assert replay["matchedEventCount"] == 1
    assert replay["requestIds"] == [first.headers["x-exposure-audit-request-id"]]
    assert replay["reproducibility"]["defaultsManifestResource"] == "defaults://manifest"
    assert replay["reproducibility"]["releaseMetadataResource"] == "release://metadata-report"

    digest_replay = build_http_audit_replay_report(
        events,
        normalized_input_digest=events[0]["normalizedInputDigestSha256"],
    )
    assert digest_replay["matchedEventCount"] == 2
    assert digest_replay["reproducibility"]["defaultsVersions"]


def test_http_audit_runtime_context_tracks_release_metadata(tmp_path: Path) -> None:
    release_metadata_path = tmp_path / "release.json"
    release_metadata_path.write_text('{"releaseVersion":"test"}', encoding="utf-8")

    runtime_context = build_http_audit_runtime_context(release_metadata_path=release_metadata_path)

    assert runtime_context["serverVersion"]
    assert runtime_context["releaseVersion"]
    assert runtime_context["releaseMetadataPath"] == str(release_metadata_path)
    assert len(runtime_context["releaseMetadataSha256"]) == 64
