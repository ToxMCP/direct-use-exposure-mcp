"""Packaged executable validation reference-band registry."""

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
    ValidationReferenceBand,
    ValidationReferenceBandManifest,
)

REFERENCE_REPO_RELATIVE_PATH = Path("validation/v1/executable_reference_bands.json")
REFERENCE_PACKAGE_RELATIVE_PATH = "data/validation/v1/executable_reference_bands.json"


@dataclass(slots=True)
class ValidationReferenceBandRegistry:
    """Loads immutable executable validation reference bands for narrow realism checks."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["reference_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> ValidationReferenceBandRegistry:
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

    def manifest(self) -> ValidationReferenceBandManifest:
        bands = [ValidationReferenceBand(**item) for item in self.payload.get("bands", [])]
        return ValidationReferenceBandManifest(
            referenceVersion=self.version,
            referenceHashSha256=self.sha256,
            path=self.location,
            bandCount=len(bands),
            notes=list(self.payload.get("notes", [])),
            bands=bands,
        )

    def band_for_check(self, check_id: str) -> ValidationReferenceBand:
        for item in self.manifest().bands:
            if item.check_id == check_id:
                return item
        available = ", ".join(f"`{item.check_id}`" for item in self.manifest().bands)
        raise ExposureScenarioError(
            code="validation_reference_band_missing",
            message=f"Executable validation reference band `{check_id}` is not registered.",
            suggestion=(
                "Update validation/v1/executable_reference_bands.json"
                + (f" to include one of: {available}." if available else ".")
            ),
        )


def validation_reference_band_manifest() -> dict[str, Any]:
    return ValidationReferenceBandRegistry.load().manifest().model_dump(mode="json", by_alias=True)
