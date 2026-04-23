"""Release artifact inventory and verification helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from exposure_scenario_mcp.models import ReleaseDistributionArtifact

DistributionKind = Literal["wheel", "sdist"]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distribution_artifacts_for_release(
    package_name: str, version: str, dist_dir: Path | None
) -> list[ReleaseDistributionArtifact]:
    normalized = package_name.replace("-", "_")
    expected: list[tuple[DistributionKind, str]] = [
        ("wheel", f"{normalized}-{version}-py3-none-any.whl"),
        ("sdist", f"{normalized}-{version}.tar.gz"),
    ]
    artifacts: list[ReleaseDistributionArtifact] = []
    dist_label = dist_dir.name if dist_dir is not None else "dist"
    for kind, filename in expected:
        artifact_path = None if dist_dir is None else dist_dir / filename
        if artifact_path is not None and artifact_path.exists():
            artifacts.append(
                ReleaseDistributionArtifact(
                    kind=kind,
                    filename=filename,
                    relativePath=f"{dist_label}/{filename}",
                    present=True,
                    sha256=sha256_path(artifact_path),
                    sizeBytes=artifact_path.stat().st_size,
                )
            )
            continue
        artifacts.append(
            ReleaseDistributionArtifact(
                kind=kind,
                filename=filename,
                relativePath=f"{dist_label}/{filename}",
                present=False,
            )
        )
    return artifacts


def validate_release_metadata_report(metadata_path: Path, repo_root: Path) -> list[str]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifacts = payload.get("distributionArtifacts")
    if not isinstance(artifacts, list):
        return ["release metadata is missing a distributionArtifacts list"]

    if payload.get("releaseVersion") != payload.get("packageVersion"):
        errors.append("releaseVersion and packageVersion must match for published release metadata")

    seen_kinds: set[str] = set()
    for artifact in artifacts:
        kind = str(artifact.get("kind"))
        if kind in seen_kinds:
            errors.append(f"duplicate distribution artifact kind `{kind}` in release metadata")
            continue
        seen_kinds.add(kind)

        relative_path = artifact.get("relativePath")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"artifact `{kind}` is missing a relativePath")
            continue

        artifact_path = repo_root / relative_path
        exists = artifact_path.exists()
        declared_present = bool(artifact.get("present"))
        if exists != declared_present:
            errors.append(
                f"artifact `{kind}` presence mismatch: metadata says `{declared_present}` "
                f"but filesystem says `{exists}` for `{relative_path}`"
            )

        declared_sha = artifact.get("sha256")
        declared_size = artifact.get("sizeBytes")
        if not exists:
            if declared_sha is not None:
                errors.append(f"artifact `{kind}` should not declare sha256 when missing")
            if declared_size is not None:
                errors.append(f"artifact `{kind}` should not declare sizeBytes when missing")
            continue

        actual_sha = sha256_path(artifact_path)
        actual_size = artifact_path.stat().st_size
        if declared_sha is not None and declared_sha != actual_sha:
            errors.append(
                f"artifact `{kind}` sha256 mismatch for `{relative_path}`: "
                f"declared `{declared_sha}`, actual `{actual_sha}`"
            )
        if declared_size is not None and declared_size != actual_size:
            errors.append(
                f"artifact `{kind}` size mismatch for `{relative_path}`: "
                f"declared `{declared_size}`, actual `{actual_size}`"
            )

    return errors
