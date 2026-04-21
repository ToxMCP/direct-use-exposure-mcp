from __future__ import annotations

import json
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parents[1] / "ci" / "mypy_full_tree_baseline.json"


def test_mypy_baseline_is_well_formed() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["fileErrorCounts"], dict)
    assert payload["totalErrors"] == sum(payload["fileErrorCounts"].values())
    assert payload["mypyCommand"].endswith("src/exposure_scenario_mcp")
