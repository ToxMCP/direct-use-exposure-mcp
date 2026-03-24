"""Generate JSON Schemas, examples, contract manifests, and release metadata."""

from __future__ import annotations

import json
from pathlib import Path

from exposure_scenario_mcp.contracts import (
    build_contract_manifest,
    build_examples,
    build_release_metadata_report,
    schema_payloads,
)
from exposure_scenario_mcp.defaults import DEFAULTS_REPO_RELATIVE_PATH, DefaultsRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
EXAMPLES_DIR = SCHEMA_DIR / "examples"
DOC_SCHEMA_DIR = REPO_ROOT / "docs" / "contracts" / "schemas"
CONTRACT_MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"
DEFAULTS_MANIFEST_PATH = REPO_ROOT / "defaults" / "manifest.json"
RELEASE_METADATA_PATH = REPO_ROOT / "docs" / "releases" / "v0.1.0.release_metadata.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    defaults_registry = DefaultsRegistry.load()

    for schema_name, payload in schema_payloads().items():
        _write_json(SCHEMA_DIR / f"{schema_name}.json", payload)
        _write_json(DOC_SCHEMA_DIR / f"{schema_name}.json", payload)

    for example_name, payload in build_examples().items():
        _write_json(EXAMPLES_DIR / f"{example_name}.json", payload)

    manifest = build_contract_manifest(defaults_registry).model_dump(mode="json")
    _write_json(CONTRACT_MANIFEST_PATH, manifest)
    _write_json(
        RELEASE_METADATA_PATH,
        build_release_metadata_report(defaults_registry).model_dump(mode="json", by_alias=True),
    )
    _write_json(
        DEFAULTS_MANIFEST_PATH,
        {
            **defaults_registry.manifest(),
            "defaults_file": str(DEFAULTS_REPO_RELATIVE_PATH),
        },
    )


if __name__ == "__main__":
    main()
