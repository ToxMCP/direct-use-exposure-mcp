"""Packaged Tier C scenario-package probability profiles."""

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
    ScenarioPackageProbabilityManifest,
    ScenarioPackageProbabilityProfile,
)

PROFILE_REPO_RELATIVE_PATH = Path(
    "probability_bounds/v1/scenario_package_probability_profiles.json"
)
PROFILE_PACKAGE_RELATIVE_PATH = (
    "data/probability_bounds/v1/scenario_package_probability_profiles.json"
)


@dataclass(slots=True)
class ScenarioProbabilityPackageRegistry:
    """Loads immutable coupled-driver scenario-package probability profiles."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["profile_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> ScenarioProbabilityPackageRegistry:
        if path is not None:
            raw_text = path.read_text(encoding="utf-8")
            location = str(path)
            target = path
        else:
            raw_text, location, target = read_text_asset(
                PROFILE_PACKAGE_RELATIVE_PATH,
                str(PROFILE_REPO_RELATIVE_PATH),
            )
        payload = json.loads(raw_text)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return cls(path=target, location=location, payload=payload, sha256=sha256)

    def manifest(self) -> ScenarioPackageProbabilityManifest:
        profiles = [
            ScenarioPackageProbabilityProfile(**item) for item in self.payload.get("profiles", [])
        ]
        return ScenarioPackageProbabilityManifest(
            profileVersion=self.version,
            profileHashSha256=self.sha256,
            path=self.location,
            profileCount=len(profiles),
            notes=list(self.payload.get("notes", [])),
            profiles=profiles,
        )

    def get_profile(self, profile_id: str) -> ScenarioPackageProbabilityProfile:
        for item in self.manifest().profiles:
            if item.profile_id == profile_id:
                return item
        available = ", ".join(f"`{item.profile_id}`" for item in self.manifest().profiles)
        raise ExposureScenarioError(
            code="scenario_package_probability_profile_missing",
            message=f"Scenario-package probability profile `{profile_id}` is not registered.",
            suggestion=(
                "Use one of the packaged scenario-package probability profiles"
                + (f": {available}." if available else ".")
            ),
        )
