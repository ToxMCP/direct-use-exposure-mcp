"""Versioned defaults registry for Exposure Scenario MCP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.errors import ExposureScenarioError, ensure
from exposure_scenario_mcp.models import AssumptionSourceReference

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS_PATH = PACKAGE_ROOT / "defaults" / "v1" / "core_defaults.json"


@dataclass(slots=True)
class DefaultsRegistry:
    """Loads immutable defaults and source metadata for deterministic calculations."""

    path: Path
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["defaults_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> DefaultsRegistry:
        target = path or DEFAULTS_PATH
        raw_text = target.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return cls(path=target, payload=payload, sha256=sha256)

    def manifest(self) -> dict[str, Any]:
        room_defaults = self.payload.get("room_defaults", {})
        regional_overrides = room_defaults.get("regional_overrides", {})
        return {
            "defaults_version": self.version,
            "defaults_hash_sha256": self.sha256,
            "source_count": len(self.payload.get("sources", [])),
            "supported_regions": sorted(["global", *regional_overrides.keys()]),
            "path": str(self.path),
        }

    def _source(self, source_id: str) -> AssumptionSourceReference:
        for source in self.payload.get("sources", []):
            if source["source_id"] == source_id:
                return AssumptionSourceReference(**source, hash_sha256=self.sha256)
        raise ExposureScenarioError(
            code="defaults_source_missing",
            message=f"Defaults source '{source_id}' is not registered.",
            suggestion=(
                "Update defaults/v1/core_defaults.json so every default "
                "points to a declared source."
            ),
        )

    def source_reference(self, source_id: str) -> AssumptionSourceReference:
        return self._source(source_id)

    def default_density_g_per_ml(
        self,
        product_category: str | None = None,
        physical_form: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["conversion_defaults"]
        if "global" not in section:
            return float(section["density_g_per_ml"]), self._source(section["source_id"])

        entry = section["global"]
        if product_category:
            category_entry = section.get("product_category_overrides", {}).get(
                product_category.lower()
            )
            if category_entry:
                entry = category_entry
        if physical_form:
            form_entry = section.get("physical_form_overrides", {}).get(physical_form.lower())
            if form_entry:
                entry = form_entry
        return float(entry["density_g_per_ml"]), self._source(entry["source_id"])

    def population_defaults(
        self, population_group: str
    ) -> tuple[dict[str, float], AssumptionSourceReference]:
        population_group = population_group.lower()
        populations = self.payload["population_defaults"]
        ensure(
            population_group in populations,
            "population_group_unsupported",
            f"Population group '{population_group}' is not supported by the defaults registry.",
            suggestion=f"Use one of: {', '.join(sorted(populations))}.",
        )
        entry = populations[population_group]
        return {
            "body_weight_kg": float(entry["body_weight_kg"]),
            "inhalation_rate_m3_per_hour": float(entry["inhalation_rate_m3_per_hour"]),
            "exposed_surface_area_cm2": float(entry["exposed_surface_area_cm2"]),
        }, self._source(entry["source_id"])

    def retention_factor(self, retention_type: str) -> tuple[float, AssumptionSourceReference]:
        key = retention_type.lower()
        values = self.payload["retention_factor_defaults"]
        ensure(
            key in values,
            "retention_type_unsupported",
            f"Retention type '{retention_type}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def transfer_efficiency(
        self,
        application_method: str,
        product_category: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        key = application_method.lower()
        values = self.payload["transfer_efficiency_defaults"]
        if "global" in values:
            resolved = values["global"]
            if product_category:
                category_values = values.get("product_category_overrides", {}).get(
                    product_category.lower(),
                    {},
                )
                if key in category_values:
                    entry = category_values[key]
                    return float(entry["value"]), self._source(entry["source_id"])
            values = resolved
        ensure(
            key in values,
            "application_method_unsupported",
            (
                f"Application method '{application_method}' is not supported "
                "for transfer efficiency defaults."
            ),
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def ingestion_fraction(
        self, application_method: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = application_method.lower()
        values = self.payload["ingestion_fraction_defaults"]
        ensure(
            key in values,
            "ingestion_method_unsupported",
            (
                f"Application method '{application_method}' is not supported "
                "for oral ingestion defaults."
            ),
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def aerosolized_fraction(
        self,
        application_method: str,
        product_category: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        key = application_method.lower()
        values = self.payload["aerosolized_fraction_defaults"]
        if "global" in values:
            resolved = values["global"]
            if product_category:
                category_values = values.get("product_category_overrides", {}).get(
                    product_category.lower(),
                    {},
                )
                if key in category_values:
                    entry = category_values[key]
                    return float(entry["value"]), self._source(entry["source_id"])
            values = resolved
        ensure(
            key in values,
            "aerosol_method_unsupported",
            f"Application method '{application_method}' is not supported for inhalation defaults.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def room_defaults(
        self, region: str = "global"
    ) -> tuple[dict[str, float], AssumptionSourceReference]:
        entry = self.payload["room_defaults"]
        if "global" in entry:
            base = dict(entry["global"])
            override = entry.get("regional_overrides", {}).get(region.lower())
            if override:
                base.update(override)
            entry = base
        return {
            "room_volume_m3": float(entry["room_volume_m3"]),
            "air_exchange_rate_per_hour": float(entry["air_exchange_rate_per_hour"]),
            "exposure_duration_hours": float(entry["exposure_duration_hours"]),
        }, self._source(entry["source_id"])


def defaults_evidence_map(registry: DefaultsRegistry | None = None) -> str:
    active_registry = registry or DefaultsRegistry.load()
    sources = active_registry.payload.get("sources", [])
    lines = [
        "# Defaults Evidence Map",
        "",
        "These defaults are benchmark screening values. They are intended for auditable",
        "scenario construction, not for final exposure-factor selection in a regulatory dossier.",
        "",
        "## Source Register",
        "",
    ]
    for source in sources:
        lines.append(f"- `{source['source_id']}`: {source['title']}")
        lines.append(f"  locator: {source['locator']}")
        lines.append(f"  version: {source['version']}")
    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- `benchmark_population_defaults_v1` maps adult body-weight and inhalation-rate",
            "  screening values to EPA Exposure Factors Handbook source families, while keeping",
            "  exposed skin area as an explicit screening benchmark rather than a",
            "  total-body default.",
            "- `echa_consumer_inhalation_room_defaults` is used only for EU-region inhalation room",
            "  defaults, where a higher ventilation benchmark is appropriate for",
            "  consumer spray-style",
            "  screening than the generic global fallback.",
            "- `heuristic_screening_defaults_v1` covers transfer efficiency, retention, density,",
            "  ingestion fraction, aerosolized fraction, and global room defaults that remain",
            "  benchmark heuristics pending a curated evidence pack. Product-category and",
            "  physical-form overrides are still heuristic unless a future source pack",
            "  replaces them.",
            "- Density resolution follows `global -> product category -> physical form`, so form-",
            "  specific benchmarks can override broad category defaults when both are present.",
            "- Transfer efficiency and aerosolized fraction use method-specific global defaults,",
            "  with product-category method overrides applied only where the defaults pack",
            "  declares them explicitly.",
        ]
    )
    return "\n".join(lines)
