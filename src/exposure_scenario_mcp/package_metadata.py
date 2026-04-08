"""Package metadata helpers that do not import the MCP server stack."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "exposure-scenario-mcp"
SERVER_NAME = "exposure_scenario_mcp"
PRODUCT_NAME = "Direct-Use Exposure MCP"
FALLBACK_VERSION = "0.1.0"


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION


__version__ = package_version()
