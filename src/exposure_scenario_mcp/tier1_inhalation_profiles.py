"""Packaged Tier 1 inhalation screening parameter and product-profile registry."""

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
    AirflowDirectionality,
    AssumptionSourceReference,
    ParticleSizeRegime,
    Tier1AirflowClassProfile,
    Tier1InhalationParameterManifest,
    Tier1InhalationProductProfile,
    Tier1ParticleRegimeProfile,
)

PROFILE_REPO_RELATIVE_PATH = Path("tier1_inhalation/v1/screening_parameter_profiles.json")
PROFILE_PACKAGE_RELATIVE_PATH = "data/tier1_inhalation/v1/screening_parameter_profiles.json"


@dataclass(slots=True)
class Tier1InhalationProfileRegistry:
    """Loads immutable Tier 1 NF/FF screening parameters and product-family profiles."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["profile_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> Tier1InhalationProfileRegistry:
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

    def _source(self, source_id: str) -> AssumptionSourceReference:
        for source in self.payload.get("sources", []):
            if source["source_id"] == source_id:
                return AssumptionSourceReference(**source, hash_sha256=self.sha256)
        raise ExposureScenarioError(
            code="tier1_inhalation_source_missing",
            message=f"Tier 1 inhalation source `{source_id}` is not registered.",
            suggestion=(
                "Update tier1_inhalation/v1/screening_parameter_profiles.json so every "
                "parameter entry points to a declared source."
            ),
        )

    def source_reference(self, source_id: str) -> AssumptionSourceReference:
        return self._source(source_id)

    def manifest(self) -> Tier1InhalationParameterManifest:
        sources = [self._source(item["source_id"]) for item in self.payload.get("sources", [])]
        directionality_profiles = [
            Tier1AirflowClassProfile(**item)
            for item in self.payload.get("directionality_profiles", [])
        ]
        particle_profiles = [
            Tier1ParticleRegimeProfile(**item) for item in self.payload.get("particle_profiles", [])
        ]
        profiles = [
            Tier1InhalationProductProfile(**item) for item in self.payload.get("profiles", [])
        ]
        return Tier1InhalationParameterManifest(
            profileVersion=self.version,
            profileHashSha256=self.sha256,
            path=self.location,
            sourceCount=len(sources),
            directionalityProfileCount=len(directionality_profiles),
            particleProfileCount=len(particle_profiles),
            profileCount=len(profiles),
            notes=list(self.payload.get("notes", [])),
            sources=sources,
            directionalityProfiles=directionality_profiles,
            particleProfiles=particle_profiles,
            profiles=profiles,
        )

    def airflow_profile(self, directionality: AirflowDirectionality) -> Tier1AirflowClassProfile:
        for item in self.manifest().directionality_profiles:
            if item.directionality == directionality:
                return item
        available = ", ".join(
            f"`{item.directionality.value}`" for item in self.manifest().directionality_profiles
        )
        raise ExposureScenarioError(
            code="tier1_airflow_directionality_missing",
            message=(
                f"Tier 1 airflow directionality `{directionality.value}` is not registered."
            ),
            suggestion=(
                "Use one of the packaged Tier 1 airflow classes"
                + (f": {available}." if available else ".")
            ),
        )

    def particle_profile(self, regime: ParticleSizeRegime) -> Tier1ParticleRegimeProfile:
        for item in self.manifest().particle_profiles:
            if item.particle_size_regime == regime:
                return item
        available = ", ".join(
            f"`{item.particle_size_regime.value}`" for item in self.manifest().particle_profiles
        )
        raise ExposureScenarioError(
            code="tier1_particle_regime_missing",
            message=f"Tier 1 particle regime `{regime.value}` is not registered.",
            suggestion=(
                "Use one of the packaged Tier 1 particle regimes"
                + (f": {available}." if available else ".")
            ),
        )

    def matching_profiles(
        self,
        *,
        product_family: str,
        application_method: str,
        product_subtype: str | None = None,
    ) -> list[Tier1InhalationProductProfile]:
        family = product_family.lower()
        method = application_method.lower()
        candidates = [
            item
            for item in self.manifest().profiles
            if item.product_family.lower() == family and item.application_method.lower() == method
        ]
        if product_subtype:
            subtype = product_subtype.lower()
            exact_matches = [
                item
                for item in candidates
                if item.product_subtype is not None and item.product_subtype.lower() == subtype
            ]
            if exact_matches:
                return exact_matches
        return [item for item in candidates if item.product_subtype is None]
