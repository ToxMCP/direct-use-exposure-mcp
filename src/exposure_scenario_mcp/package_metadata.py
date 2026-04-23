"""Package metadata helpers that do not import the MCP server stack."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "exposure-scenario-mcp"
SERVER_NAME = "exposure_scenario_mcp"
PRODUCT_NAME = "Direct-Use Exposure MCP"
CURRENT_VERSION = "0.2.1"
CURRENT_RELEASE_TAG = f"v{CURRENT_VERSION}"
CURRENT_RELEASE_NOTES_RELATIVE_PATH = f"docs/releases/{CURRENT_RELEASE_TAG}.md"
CURRENT_RELEASE_METADATA_RELATIVE_PATH = (
    f"docs/releases/{CURRENT_RELEASE_TAG}.release_metadata.json"
)
FALLBACK_VERSION = CURRENT_VERSION


def package_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION


__version__ = CURRENT_VERSION
