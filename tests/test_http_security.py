from __future__ import annotations

from starlette.testclient import TestClient

from exposure_scenario_mcp.http_security import (
    DEFAULT_HTTP_MAX_CONCURRENCY,
    DEFAULT_HTTP_MAX_REQUEST_BYTES,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    build_http_boundary_security_config,
)
from exposure_scenario_mcp.server import create_mcp_server, create_streamable_http_app

TEST_BEARER_TOKEN = "test-shared-token"  # noqa: S105


def test_http_security_config_uses_env_fallbacks(monkeypatch, tmp_path) -> None:
    audit_path = tmp_path / "exposure-http-audit.jsonl"
    monkeypatch.setenv("EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN", TEST_BEARER_TOKEN)
    monkeypatch.setenv(
        "EXPOSURE_SCENARIO_MCP_HTTP_ALLOWED_ORIGINS",
        "https://trusted.example, https://backup.example",
    )
    monkeypatch.setenv(
        "EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH",
        str(audit_path),
    )
    monkeypatch.setenv("EXPOSURE_SCENARIO_MCP_HTTP_REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EXPOSURE_SCENARIO_MCP_HTTP_MAX_CONCURRENCY", "8")
    config = build_http_boundary_security_config()

    assert config.bearer_token == TEST_BEARER_TOKEN
    assert config.allowed_origins == (
        "https://trusted.example",
        "https://backup.example",
    )
    assert config.max_request_bytes == DEFAULT_HTTP_MAX_REQUEST_BYTES
    assert config.audit_log_path == audit_path
    assert config.request_timeout_seconds == 45.0
    assert config.max_concurrency == 8


def test_http_security_config_defaults_include_timeout_and_concurrency() -> None:
    config = build_http_boundary_security_config(max_request_bytes=0)

    assert config.request_timeout_seconds == DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS
    assert config.max_concurrency == DEFAULT_HTTP_MAX_CONCURRENCY


def test_streamable_http_app_requires_shared_bearer_token() -> None:
    server = create_mcp_server()
    app = create_streamable_http_app(
        server,
        build_http_boundary_security_config(
            bearer_token=TEST_BEARER_TOKEN,
            allowed_origins=[],
            max_request_bytes=0,
        ),
    )

    with TestClient(app) as client:
        response = client.post(server.settings.streamable_http_path, json={"jsonrpc": "2.0"})
        allowed = client.post(
            server.settings.streamable_http_path,
            headers={"Authorization": f"Bearer {TEST_BEARER_TOKEN}"},
            json={"jsonrpc": "2.0"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "missing_bearer_token"
    assert response.headers["www-authenticate"] == "Bearer"
    assert allowed.status_code != 401


def test_streamable_http_app_enforces_origin_allowlist() -> None:
    server = create_mcp_server()
    app = create_streamable_http_app(
        server,
        build_http_boundary_security_config(
            allowed_origins=["https://trusted.example"],
            max_request_bytes=0,
        ),
    )

    with TestClient(app) as client:
        blocked = client.options(
            server.settings.streamable_http_path,
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        allowed = client.options(
            server.settings.streamable_http_path,
            headers={
                "Origin": "https://trusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert blocked.status_code == 403
    assert blocked.json()["error"] == "origin_not_allowed"
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://trusted.example"


def test_streamable_http_app_enforces_request_size_limit() -> None:
    server = create_mcp_server()
    app = create_streamable_http_app(
        server,
        build_http_boundary_security_config(
            max_request_bytes=32,
            allowed_origins=[],
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            server.settings.streamable_http_path,
            content="x" * 128,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["error"] == "request_too_large"
