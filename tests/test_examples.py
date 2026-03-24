from __future__ import annotations

from exposure_scenario_mcp.examples import build_examples


def test_build_examples_is_deterministic() -> None:
    assert build_examples() == build_examples()
