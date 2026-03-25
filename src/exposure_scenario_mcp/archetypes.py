"""Packaged Tier B archetype library for deterministic envelope construction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.assets import read_text_asset
from exposure_scenario_mcp.errors import ExposureScenarioError, ensure
from exposure_scenario_mcp.models import (
    ArchetypeLibraryManifest,
    ArchetypeLibrarySet,
    ArchetypeLibraryTemplate,
    BuildExposureEnvelopeFromLibraryInput,
    BuildExposureEnvelopeInput,
    EnvelopeArchetypeInput,
    ExposureScenarioRequest,
    InhalationTier1ScenarioRequest,
)

ARCHETYPE_LIBRARY_REPO_RELATIVE_PATH = Path("archetypes/v1/envelope_archetype_library.json")
ARCHETYPE_LIBRARY_PACKAGE_RELATIVE_PATH = "data/archetypes/v1/envelope_archetype_library.json"


@dataclass(slots=True)
class ArchetypeLibraryRegistry:
    """Loads immutable Tier B archetype sets for deterministic envelope construction."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["library_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> ArchetypeLibraryRegistry:
        if path is not None:
            raw_text = path.read_text(encoding="utf-8")
            location = str(path)
            target = path
        else:
            raw_text, location, target = read_text_asset(
                ARCHETYPE_LIBRARY_PACKAGE_RELATIVE_PATH,
                str(ARCHETYPE_LIBRARY_REPO_RELATIVE_PATH),
            )
        payload = json.loads(raw_text)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return cls(path=target, location=location, payload=payload, sha256=sha256)

    def manifest(self) -> ArchetypeLibraryManifest:
        sets = [ArchetypeLibrarySet(**item) for item in self.payload.get("sets", [])]
        return ArchetypeLibraryManifest(
            libraryVersion=self.version,
            libraryHashSha256=self.sha256,
            path=self.location,
            setCount=len(sets),
            notes=list(self.payload.get("notes", [])),
            sets=sets,
        )

    def get_set(self, set_id: str) -> ArchetypeLibrarySet:
        for item in self.manifest().sets:
            if item.set_id == set_id:
                return item
        available = ", ".join(f"`{item.set_id}`" for item in self.manifest().sets)
        raise ExposureScenarioError(
            code="archetype_library_set_missing",
            message=f"Archetype library set `{set_id}` is not registered.",
            suggestion=(
                "Use one of the packaged archetype-library sets"
                + (f": {available}." if available else ".")
            ),
        )


def instantiate_library_request(
    template_set: ArchetypeLibrarySet,
    template: ArchetypeLibraryTemplate,
    *,
    chemical_id: str,
    chemical_name: str | None,
) -> ExposureScenarioRequest | InhalationTier1ScenarioRequest:
    if template.tier1_inhalation_parameters is not None:
        return InhalationTier1ScenarioRequest(
            chemical_id=chemical_id,
            chemical_name=chemical_name,
            route=template_set.route,
            scenario_class=template_set.scenario_class,
            product_use_profile=template.product_use_profile,
            population_profile=template.population_profile,
            source_distance_m=template.tier1_inhalation_parameters.source_distance_m,
            spray_duration_seconds=template.tier1_inhalation_parameters.spray_duration_seconds,
            near_field_volume_m3=template.tier1_inhalation_parameters.near_field_volume_m3,
            airflow_directionality=template.tier1_inhalation_parameters.airflow_directionality,
            particle_size_regime=template.tier1_inhalation_parameters.particle_size_regime,
            assumption_overrides={},
        )
    return ExposureScenarioRequest(
        chemical_id=chemical_id,
        chemical_name=chemical_name,
        route=template_set.route,
        scenario_class=template_set.scenario_class,
        product_use_profile=template.product_use_profile,
        population_profile=template.population_profile,
        assumption_overrides={},
    )


def build_envelope_input_from_library(
    params: BuildExposureEnvelopeFromLibraryInput,
    library: ArchetypeLibraryRegistry,
) -> tuple[BuildExposureEnvelopeInput, ArchetypeLibrarySet]:
    template_set = library.get_set(params.library_set_id)
    ensure(
        len(template_set.archetypes) >= 2,
        "archetype_library_set_too_small",
        f"Archetype library set `{template_set.set_id}` must contain at least two archetypes.",
        suggestion="Update the packaged library set so it includes bounded low/high variants.",
    )
    archetypes = [
        EnvelopeArchetypeInput(
            templateId=item.template_id,
            label=item.label,
            description=item.description,
            request=instantiate_library_request(
                template_set,
                item,
                chemical_id=params.chemical_id,
                chemical_name=params.chemical_name,
            ),
        )
        for item in template_set.archetypes
    ]
    return (
        BuildExposureEnvelopeInput(
            chemical_id=params.chemical_id,
            label=params.label or template_set.label,
            archetypes=archetypes,
        ),
        template_set,
    )
