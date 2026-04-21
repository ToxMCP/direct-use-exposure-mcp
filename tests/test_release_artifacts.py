from __future__ import annotations

import json
from pathlib import Path

from exposure_scenario_mcp.package_metadata import CURRENT_VERSION
from exposure_scenario_mcp.release_artifacts import (
    distribution_artifacts_for_release,
    sha256_path,
    validate_release_metadata_report,
)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_distribution_artifacts_track_presence_without_pinning_local_build_digests(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist"
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}-py3-none-any.whl",
        b"wheel-bytes",
    )
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}.tar.gz",
        b"sdist-bytes",
    )

    artifacts = distribution_artifacts_for_release(
        "exposure-scenario-mcp", CURRENT_VERSION, dist_dir
    )

    assert [artifact.kind for artifact in artifacts] == ["wheel", "sdist"]
    assert all(artifact.present for artifact in artifacts)
    assert artifacts[0].sha256 == sha256_path(dist_dir / artifacts[0].filename)
    assert artifacts[0].size_bytes == (dist_dir / artifacts[0].filename).stat().st_size
    assert artifacts[1].sha256 == sha256_path(dist_dir / artifacts[1].filename)
    assert artifacts[1].size_bytes == (dist_dir / artifacts[1].filename).stat().st_size


def test_validate_release_metadata_report_detects_integrity_mismatch(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}-py3-none-any.whl",
        b"wheel-bytes",
    )
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}.tar.gz",
        b"sdist-bytes",
    )
    artifacts = distribution_artifacts_for_release(
        "exposure-scenario-mcp", CURRENT_VERSION, dist_dir
    )
    payload = {
        "releaseVersion": CURRENT_VERSION,
        "packageVersion": CURRENT_VERSION,
        "distributionArtifacts": [
            {
                **artifact.model_dump(mode="json", by_alias=True),
                "sha256": "bad-digest" if artifact.kind == "wheel" else artifact.sha256,
            }
            for artifact in artifacts
        ],
    }
    metadata_path = tmp_path / "release_metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    errors = validate_release_metadata_report(metadata_path, tmp_path)

    assert len(errors) == 1
    assert "sha256 mismatch" in errors[0]


def test_validate_release_metadata_report_allows_present_artifacts_without_pinned_digests(
    tmp_path: Path,
) -> None:
    dist_dir = tmp_path / "dist"
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}-py3-none-any.whl",
        b"wheel-bytes",
    )
    _write_bytes(
        dist_dir / f"exposure_scenario_mcp-{CURRENT_VERSION}.tar.gz",
        b"sdist-bytes",
    )
    artifacts = distribution_artifacts_for_release(
        "exposure-scenario-mcp", CURRENT_VERSION, dist_dir
    )
    payload = {
        "releaseVersion": CURRENT_VERSION,
        "packageVersion": CURRENT_VERSION,
        "distributionArtifacts": [
            {
                **artifact.model_dump(mode="json", by_alias=True),
                "sha256": None,
                "sizeBytes": None,
            }
            for artifact in artifacts
        ],
    }
    metadata_path = tmp_path / "release_metadata.json"
    metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    errors = validate_release_metadata_report(metadata_path, tmp_path)

    assert errors == []
