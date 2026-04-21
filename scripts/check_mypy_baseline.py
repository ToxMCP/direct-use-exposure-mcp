"""Check that full-tree mypy debt does not exceed the tracked baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_PATH = REPO_ROOT / "ci" / "mypy_full_tree_baseline.json"
MYPY_COMMAND = [
    "uv",
    "run",
    "mypy",
    "--no-incremental",
    "--hide-error-context",
    "--no-pretty",
    "src/exposure_scenario_mcp",
]
ERROR_PATTERN = re.compile(r"^(?P<path>[^:]+):\d+:")


def _collect_error_counts(output: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for line in output.splitlines():
        match = ERROR_PATTERN.match(line)
        if match is not None:
            counts[match.group("path")] += 1
    return dict(sorted(counts.items()))


def _build_summary(output: str) -> dict[str, Any]:
    file_error_counts = _collect_error_counts(output)
    return {
        "description": (
            "Temporary full-tree mypy debt baseline. The baseline may shrink, but CI must fail "
            "if any file count or the total count grows."
        ),
        "mypyCommand": " ".join(MYPY_COMMAND),
        "totalErrors": sum(file_error_counts.values()),
        "fileErrorCounts": file_error_counts,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_mypy() -> tuple[int, str]:
    completed = subprocess.run(  # noqa: S603
        MYPY_COMMAND,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output


def _print_failures(failures: list[str], actual: dict[str, Any], baseline: dict[str, Any]) -> None:
    print("Full-tree mypy baseline regression detected:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Actual summary:", file=sys.stderr)
    print(json.dumps(actual, indent=2, sort_keys=True), file=sys.stderr)
    print("", file=sys.stderr)
    print("Baseline summary:", file=sys.stderr)
    print(json.dumps(baseline, indent=2, sort_keys=True), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to the tracked mypy debt baseline JSON file.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline file from the current full-tree mypy output.",
    )
    args = parser.parse_args(argv)

    returncode, output = _run_mypy()
    if returncode not in {0, 1}:
        print(output, file=sys.stderr)
        raise SystemExit(returncode)

    actual = _build_summary(output)
    if args.write_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote baseline to {args.baseline}")
        return 0

    baseline = _load_json(args.baseline)
    baseline_counts = baseline.get("fileErrorCounts", {})
    actual_counts = actual["fileErrorCounts"]
    failures: list[str] = []

    if actual["totalErrors"] > baseline.get("totalErrors", 0):
        failures.append(
            f"total errors increased from {baseline['totalErrors']} to {actual['totalErrors']}"
        )

    for file_path, count in actual_counts.items():
        allowed = baseline_counts.get(file_path)
        if allowed is None:
            failures.append(f"new mypy debt file {file_path} appeared with {count} errors")
            continue
        if count > allowed:
            failures.append(f"{file_path} increased from {allowed} to {count} errors")

    if failures:
        _print_failures(failures, actual, baseline)
        return 1

    improved_files = [
        file_path
        for file_path, allowed in baseline_counts.items()
        if actual_counts.get(file_path, 0) < allowed
    ]
    if improved_files:
        print("Full-tree mypy debt improved in:", ", ".join(sorted(improved_files)))
    else:
        print("Full-tree mypy debt matches the tracked baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
