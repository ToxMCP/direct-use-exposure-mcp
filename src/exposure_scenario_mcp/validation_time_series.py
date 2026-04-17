"""Packaged executable validation time-series reference packs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.assets import read_text_asset
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    ValidationTimeSeriesReferenceManifest,
    ValidationTimeSeriesReferencePack,
)

REFERENCE_REPO_RELATIVE_PATH = Path("validation/v1/executable_time_series_reference_packs.json")
REFERENCE_PACKAGE_RELATIVE_PATH = "data/validation/v1/executable_time_series_reference_packs.json"


@dataclass(slots=True)
class ValidationTimeSeriesReferenceRegistry:
    """Loads immutable executable validation time-series reference packs."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["reference_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> ValidationTimeSeriesReferenceRegistry:
        if path is not None:
            raw_text = path.read_text(encoding="utf-8")
            location = str(path)
            target = path
        else:
            raw_text, location, target = read_text_asset(
                REFERENCE_PACKAGE_RELATIVE_PATH,
                str(REFERENCE_REPO_RELATIVE_PATH),
            )
        payload = json.loads(raw_text)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return cls(path=target, location=location, payload=payload, sha256=sha256)

    def manifest(self) -> ValidationTimeSeriesReferenceManifest:
        packs = [
            ValidationTimeSeriesReferencePack(**item) for item in self.payload.get("packs", [])
        ]
        point_count = sum(len(item.points) for item in packs)
        return ValidationTimeSeriesReferenceManifest(
            referenceVersion=self.version,
            referenceHashSha256=self.sha256,
            path=self.location,
            packCount=len(packs),
            pointCount=point_count,
            notes=list(self.payload.get("notes", [])),
            packs=packs,
        )

    def pack_for_id(self, reference_pack_id: str) -> ValidationTimeSeriesReferencePack:
        for item in self.manifest().packs:
            if item.reference_pack_id == reference_pack_id:
                return item
        available = ", ".join(f"`{item.reference_pack_id}`" for item in self.manifest().packs)
        raise ExposureScenarioError(
            code="validation_time_series_reference_pack_missing",
            message=(
                "Executable validation time-series reference pack "
                f"`{reference_pack_id}` is not registered."
            ),
            suggestion=(
                "Update validation/v1/executable_time_series_reference_packs.json"
                + (f" to include one of: {available}." if available else ".")
            ),
        )


def validation_time_series_reference_manifest() -> dict[str, Any]:
    return (
        ValidationTimeSeriesReferenceRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )
