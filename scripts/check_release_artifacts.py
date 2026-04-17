"""Verify published release metadata against built distribution artifacts."""

from __future__ import annotations

from pathlib import Path

from exposure_scenario_mcp.package_metadata import CURRENT_RELEASE_METADATA_RELATIVE_PATH
from exposure_scenario_mcp.release_artifacts import validate_release_metadata_report

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_METADATA_PATH = REPO_ROOT / CURRENT_RELEASE_METADATA_RELATIVE_PATH


def main() -> None:
    errors = validate_release_metadata_report(RELEASE_METADATA_PATH, REPO_ROOT)
    if errors:
        raise SystemExit("Release artifact verification failed:\n- " + "\n- ".join(errors))
    print(
        "Release artifact verification passed for "
        f"`{RELEASE_METADATA_PATH.relative_to(REPO_ROOT)}`."
    )


if __name__ == "__main__":
    main()
