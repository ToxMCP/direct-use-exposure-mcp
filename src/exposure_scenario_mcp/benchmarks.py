"""Benchmark corpus metadata for deterministic regression checks."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "benchmark_cases.json"


def load_benchmark_manifest() -> dict:
    return json.loads(BENCHMARK_FIXTURE_PATH.read_text(encoding="utf-8"))
