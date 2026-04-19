from __future__ import annotations

import pytest

from exposure_scenario_mcp import healthcheck
from exposure_scenario_mcp.__main__ import main
from exposure_scenario_mcp.server import create_mcp_server


def test_run_startup_healthcheck_reports_packaged_surface() -> None:
    summary = healthcheck.run_startup_healthcheck()

    assert summary.defaults_version
    assert len(summary.defaults_hash_sha256) == 64
    assert summary.tool_count >= len(healthcheck.REQUIRED_TOOL_NAMES)
    assert summary.resource_count >= len(healthcheck.REQUIRED_RESOURCE_URIS)
    assert summary.prompt_count >= len(healthcheck.REQUIRED_PROMPT_NAMES)


def test_validate_server_startup_fails_when_required_tool_is_missing(monkeypatch) -> None:
    server = create_mcp_server()
    monkeypatch.setattr(healthcheck, "REQUIRED_TOOL_NAMES", frozenset({"missing_tool"}))

    with pytest.raises(RuntimeError, match="Missing required tools: missing_tool"):
        healthcheck.validate_server_startup(server)


def test_main_healthcheck_returns_without_starting_transport() -> None:
    main(["--healthcheck"])
