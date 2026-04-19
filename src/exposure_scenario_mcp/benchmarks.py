"""Benchmark corpus metadata for deterministic regression checks."""

from __future__ import annotations

import json
from typing import Any, cast

from exposure_scenario_mcp.assets import read_text_asset


def load_benchmark_manifest() -> dict[str, Any]:
    raw_text, _, _ = read_text_asset(
        "data/benchmarks/benchmark_cases.json",
        "tests/fixtures/benchmark_cases.json",
    )
    return cast(dict[str, Any], json.loads(raw_text))


def load_goldset_manifest() -> dict[str, Any]:
    raw_text, _, _ = read_text_asset(
        "data/benchmarks/goldset_cases.json",
        "tests/fixtures/goldset_cases.json",
    )
    return cast(dict[str, Any], json.loads(raw_text))
