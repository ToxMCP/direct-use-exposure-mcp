"""Versioned defaults registry for Exposure Scenario MCP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.assets import read_text_asset
from exposure_scenario_mcp.errors import ExposureScenarioError, ensure
from exposure_scenario_mcp.models import AssumptionSourceReference

DEFAULTS_REPO_RELATIVE_PATH = Path("defaults/v1/core_defaults.json")
DEFAULTS_PACKAGE_RELATIVE_PATH = "data/defaults/v1/core_defaults.json"


@dataclass(slots=True)
class DefaultsRegistry:
    """Loads immutable defaults and source metadata for deterministic calculations."""

    path: Path | None
    location: str
    payload: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.payload["defaults_version"])

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: Path | None = None) -> DefaultsRegistry:
        if path is not None:
            raw_text = path.read_text(encoding="utf-8")
            location = str(path)
            target = path
        else:
            raw_text, location, target = read_text_asset(
                DEFAULTS_PACKAGE_RELATIVE_PATH,
                str(DEFAULTS_REPO_RELATIVE_PATH),
            )
        payload = json.loads(raw_text)
        sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return cls(path=target, location=location, payload=payload, sha256=sha256)

    def manifest(self) -> dict[str, Any]:
        room_defaults = self.payload.get("room_defaults", {})
        regional_overrides = room_defaults.get("regional_overrides", {})
        return {
            "defaults_version": self.version,
            "defaults_hash_sha256": self.sha256,
            "source_count": len(self.payload.get("sources", [])),
            "supported_regions": sorted(["global", *regional_overrides.keys()]),
            "path": self.location,
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

    def retention_factor(
        self,
        retention_type: str,
        product_category: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        key = retention_type.lower()
        values = self.payload["retention_factor_defaults"]
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
    ) -> tuple[dict[str, float], dict[str, AssumptionSourceReference]]:
        entry = self.payload["room_defaults"]
        if "global" not in entry:
            source = self._source(entry["source_id"])
            values = {
                "room_volume_m3": float(entry["room_volume_m3"]),
                "air_exchange_rate_per_hour": float(entry["air_exchange_rate_per_hour"]),
                "exposure_duration_hours": float(entry["exposure_duration_hours"]),
            }
            return values, {name: source for name in values}

        global_entry = entry["global"]
        override = entry.get("regional_overrides", {}).get(region.lower(), {})

        def resolve_value(name: str) -> float:
            if name in override:
                return float(override[name])
            return float(global_entry[name])

        def resolve_source(name: str, source_field: str) -> AssumptionSourceReference:
            if source_field in override:
                return self._source(override[source_field])
            if name in override and "source_id" in override:
                return self._source(override["source_id"])
            if source_field in global_entry:
                return self._source(global_entry[source_field])
            return self._source(global_entry["source_id"])

        values = {
            "room_volume_m3": resolve_value("room_volume_m3"),
            "air_exchange_rate_per_hour": resolve_value("air_exchange_rate_per_hour"),
            "exposure_duration_hours": resolve_value("exposure_duration_hours"),
        }
        sources = {
            "room_volume_m3": resolve_source("room_volume_m3", "room_volume_source_id"),
            "air_exchange_rate_per_hour": resolve_source(
                "air_exchange_rate_per_hour",
                "air_exchange_rate_source_id",
            ),
            "exposure_duration_hours": resolve_source(
                "exposure_duration_hours",
                "exposure_duration_source_id",
            ),
        }
        return values, sources


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
            "### Population Defaults",
            "",
            "- `benchmark_population_defaults_v1` maps adult body-weight and inhalation-rate",
            "  screening values to EPA Exposure Factors Handbook source families, while keeping",
            "  exposed skin area as an explicit screening benchmark rather than a total-body",
            "  default.",
            "",
            "### Screening Route Semantics",
            "",
            "- `screening_route_semantics_defaults_v1` is reserved for deterministic screening",
            "  semantics where the default is effectively a route boundary condition rather than",
            "  a fitted exposure factor. Current examples are `leave_on=1.0`,",
            "  `direct_oral=1.0`, and the direct-intake oral ingestion fraction of `1.0`.",
            "",
            "### Heuristic Density Defaults",
            "",
            "- `heuristic_density_defaults_v1` covers liquid-product density screening values and",
            "  the current category/form overrides. These are still benchmark heuristics and",
            "  should be replaced with product-family packs when curated density data are",
            "  available.",
            "",
            "### Heuristic Retention Defaults",
            "",
            "- `heuristic_retention_defaults_v1` now covers only the residual surface-contact",
            "  retention contexts that remain screening heuristics pending better route- and",
            "  use-specific retention evidence.",
            "",
            "### RIVM Cleaning Surface-Contact Retention Defaults 2018",
            "",
            "- `rivm_cleaning_surface_contact_retention_defaults_2018` maps the RIVM Cleaning",
            "  Products Fact Sheet wet-cloth contact defaults onto the MCP screening",
            "  `surface_contact` retention abstraction for `household_cleaner` contexts. The",
            "  current `0.2` value is an evidence-linked screening midpoint when paired with",
            "  the curated wet-cloth transfer default and a nominal `5 g/event` cleaning task.",
            "",
            "### FDA/SCCS Retention Factor Defaults 2024",
            "",
            "- `fda_sccs_retention_factor_defaults_2024` anchors the immediate rinse-off",
            "  retention factor of `0.01` to the official retention-factor conventions cited",
            "  in the FDA PFAS cosmetics report and SCCS Notes of Guidance.",
            "",
            "### Heuristic Transfer Defaults",
            "",
            "- `heuristic_transfer_efficiency_defaults_v1` now covers only the residual",
            "  fallback transfer-efficiency benchmarks for non-curated hand-application,",
            "  wiping, pouring, and spray-contact contexts.",
            "",
            "### RIVM Cosmetics Hand-Cream Direct Application Defaults 2025",
            "",
            "- `rivm_cosmetics_hand_cream_direct_application_defaults_2025` maps the RIVM",
            "  Cosmetics Fact Sheet hand-cream direct-contact model onto the MCP screening",
            "  transfer abstraction. For `personal_care` + `hand_application`, the product",
            "  amount supplied for a leave-on application is treated as fully available at",
            "  the skin boundary, so the transfer efficiency defaults to `1.0` and the",
            "  retention factor carries the wash-off distinction separately.",
            "",
            "### RIVM Cleaning Wet-Cloth Transfer Defaults 2018",
            "",
            "- `rivm_cleaning_wet_cloth_transfer_defaults_2018` maps the RIVM Cleaning",
            "  Products Fact Sheet wet-cloth dermal-contact defaults onto the MCP screening",
            "  transfer abstraction for `household_cleaner` + `wipe` contexts. The current",
            "  `0.5` transfer default is a curated screening bridge that centers the RIVM",
            "  wet-cloth contact amounts when combined with the curated household-cleaner",
            "  `surface_contact` retention default and a nominal `5 g/event` cleaner-loading",
            "  task.",
            "",
            "### Heuristic Incidental Oral Defaults",
            "",
            "- `heuristic_incidental_oral_defaults_v1` is limited to incidental oral transfer",
            "  semantics and should not be treated as a calibrated ingestion-factor source.",
            "",
            "### Peer-Reviewed Cleaning Trigger Spray Airborne Fraction 2019",
            "",
            "- `peer_reviewed_cleaning_trigger_spray_airborne_fraction_2019` links the trigger-",
            "  spray airborne-fraction default to an external cleaning-spray study instead of a",
            "  generic heuristic pack. It is still only a partial validation anchor, not a full",
            "  scenario-calibration dataset.",
            "",
            "### RIVM Cleaning Sprays Airborne Fraction 2018",
            "",
            "- `rivm_cleaning_sprays_airborne_fraction_2018` anchors the household-cleaner",
            "  surface-spray airborne fraction to the updated RIVM Cleaning Products Fact Sheet,",
            "  which sets a default airborne fraction of `0.2` for cleaning sprays used toward",
            "  surfaces.",
            "",
            "### Heuristic Spray Airborne Fraction Defaults",
            "",
            "- `heuristic_residual_spray_airborne_fraction_defaults_v1` covers the remaining",
            "  non-cleaner pump-spray and aerosol-spray airborne fractions that still need curated",
            "  product-family evidence packs.",
            "",
            "### RIVM General Fact Sheet Unspecified Room Defaults 2014",
            "",
            "- `rivm_general_fact_sheet_unspecified_room_defaults_2014` anchors the generic",
            "  unspecified-room volume (`20 m3`) and air exchange rate (`0.6 1/h`) to the RIVM",
            "  General Fact Sheet rather than a purely internal heuristic pack.",
            "",
            "### Heuristic Time-Limited Release Duration Defaults",
            "",
            "- `heuristic_time_limited_release_duration_defaults_v1` covers the post-use exposure",
            "  duration fallback for short room-release scenarios. This remains heuristic because",
            "  duration is strongly use-context dependent even when the room geometry is known.",
            "",
            "### ECHA Consumer Inhalation Room Defaults",
            "",
            "- `echa_consumer_inhalation_room_defaults` is used only for EU-region inhalation room",
            "  defaults, where a higher ventilation benchmark is appropriate for consumer",
            "  spray-style screening than the generic global fallback.",
            "",
            "- Density resolution follows `global -> product category -> physical form`, so form-",
            "  specific benchmarks can override broad category defaults when both are present.",
            "- Transfer efficiency and aerosolized fraction use method-specific global defaults,",
            "  with product-category method overrides applied only where the defaults pack",
            "  declares them explicitly.",
        ]
    )
    return "\n".join(lines)
