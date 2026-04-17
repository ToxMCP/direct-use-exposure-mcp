from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
CONTRACT_MANIFEST_PATH = REPO_ROOT / "docs" / "contracts" / "contract_manifest.json"


def _section_between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _backtick_bullets(text: str) -> set[str]:
    return set(re.findall(r"- `([^`]+)`", text))


def test_readme_catalogs_match_contract_manifest() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    manifest = json.loads(CONTRACT_MANIFEST_PATH.read_text(encoding="utf-8"))

    tool_section = _section_between(readme, "## Tool catalog", "## Resource catalog")
    resource_section = _section_between(readme, "## Resource catalog", "## Prompt catalog")
    prompt_section = _section_between(readme, "## Prompt catalog", "## Quick start")

    readme_tools = _backtick_bullets(tool_section)
    readme_resources = _backtick_bullets(resource_section)
    readme_prompts = _backtick_bullets(prompt_section)

    manifest_tools = {item["name"] for item in manifest["tools"]}
    manifest_resources = {item["uri"] for item in manifest["resources"]}
    manifest_prompts = {item["name"] for item in manifest["prompts"]}

    assert readme_tools == manifest_tools
    assert readme_resources == manifest_resources
    assert readme_prompts == manifest_prompts


def test_readme_surface_counts_match_contract_manifest() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    manifest = json.loads(CONTRACT_MANIFEST_PATH.read_text(encoding="utf-8"))

    match = re.search(
        r"- `(\d+)` tools\s+"
        r"- `(\d+)` resources\s+"
        r"- `(\d+)` prompts\s+"
        r"- `(\d+)` schemas\s+"
        r"- `(\d+)` examples",
        readme,
    )

    assert match is not None
    counts = tuple(int(value) for value in match.groups())

    assert counts == (
        len(manifest["tools"]),
        len(manifest["resources"]),
        len(manifest["prompts"]),
        len(manifest["schemas"]),
        len(manifest["examples"]),
    )
