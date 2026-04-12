"""Versioned defaults registry for Direct-Use Exposure MCP."""

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
    AssumptionSourceReference,
    DefaultsCurationEntry,
    DefaultsCurationReport,
    DefaultsCurationStatus,
)

DEFAULTS_REPO_RELATIVE_PATH = Path("defaults/v1/core_defaults.json")
DEFAULTS_PACKAGE_RELATIVE_PATH = "data/defaults/v1/core_defaults.json"
DEFAULT_PARAMETER_UNITS = {
    "body_weight_kg": "kg",
    "inhalation_rate_m3_per_hour": "m3/h",
    "exposed_surface_area_cm2": "cm2",
    "density_g_per_ml": "g/mL",
    "retention_factor": "fraction",
    "transfer_efficiency": "fraction",
    "ingestion_fraction": "fraction",
    "aerosolized_fraction": "fraction",
    "room_volume_m3": "m3",
    "air_exchange_rate_per_hour": "1/h",
    "exposure_duration_hours": "h",
}


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
        product_subtype: str | None = None,
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
        if product_subtype:
            subtype_entry = section.get("product_subtype_overrides", {}).get(
                product_subtype.lower()
            )
            if subtype_entry:
                entry = subtype_entry
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
        product_subtype: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        key = application_method.lower()
        values = self.payload["aerosolized_fraction_defaults"]
        if "global" in values:
            resolved = values["global"]
            if product_subtype:
                subtype_values = values.get("product_subtype_overrides", {}).get(
                    product_subtype.lower(),
                    {},
                )
                if key in subtype_values:
                    entry = subtype_values[key]
                    return float(entry["value"]), self._source(entry["source_id"])
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
        self,
        region: str = "global",
        *,
        product_category: str | None = None,
        product_subtype: str | None = None,
        application_method: str | None = None,
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
        region_key = region.lower()
        candidates: list[dict[str, Any]] = [global_entry]

        regional_override = entry.get("regional_overrides", {}).get(region_key, {})
        if regional_override:
            candidates.append(regional_override)

        def append_selector_candidates(
            selector_key: str,
            selector_value: str | None,
        ) -> None:
            if not selector_value:
                return
            selector_entry = entry.get(selector_key, {}).get(selector_value.lower(), {})
            if selector_entry:
                candidates.append(selector_entry)
                selector_region_entry = selector_entry.get("regional_overrides", {}).get(
                    region_key,
                    {},
                )
                if selector_region_entry:
                    candidates.append(selector_region_entry)

        append_selector_candidates("product_category_overrides", product_category)
        append_selector_candidates("application_method_overrides", application_method)
        append_selector_candidates("product_subtype_overrides", product_subtype)

        def resolve_value(name: str) -> float:
            for candidate in reversed(candidates):
                if name in candidate:
                    return float(candidate[name])
            return float(global_entry[name])

        def resolve_source(name: str, source_field: str) -> AssumptionSourceReference:
            for candidate in reversed(candidates):
                if source_field in candidate:
                    return self._source(candidate[source_field])
                if name in candidate and "source_id" in candidate:
                    return self._source(candidate["source_id"])
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

    def inhalation_deposition_rate_per_hour(
        self,
        *,
        particle_size_regime: str | None = None,
        application_method: str | None = None,
        physical_form: str | None = None,
        product_subtype: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["inhalation_physical_caps"]["deposition_rate_per_hour"]
        entry = section["global"]

        if physical_form:
            candidate = section.get("physical_form_overrides", {}).get(physical_form.lower())
            if candidate:
                entry = candidate
        if application_method:
            candidate = section.get("application_method_overrides", {}).get(
                application_method.lower()
            )
            if candidate:
                entry = candidate
        if product_subtype:
            candidate = section.get("product_subtype_overrides", {}).get(product_subtype.lower())
            if candidate:
                entry = candidate
        if particle_size_regime:
            candidate = section.get("particle_size_regime_overrides", {}).get(
                particle_size_regime.lower()
            )
            if candidate:
                entry = candidate

        return float(entry["value"]), self._source(entry["source_id"])

    def inhalation_extrathoracic_swallow_fraction(
        self,
        *,
        particle_size_regime: str | None = None,
        application_method: str | None = None,
        product_subtype: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["inhalation_physical_caps"]["extrathoracic_swallow_fraction"]
        entry = section["global"]

        if application_method:
            candidate = section.get("application_method_overrides", {}).get(
                application_method.lower()
            )
            if candidate:
                entry = candidate
        if product_subtype:
            candidate = section.get("product_subtype_overrides", {}).get(product_subtype.lower())
            if candidate:
                entry = candidate
        if particle_size_regime:
            candidate = section.get("particle_size_regime_overrides", {}).get(
                particle_size_regime.lower()
            )
            if candidate:
                entry = candidate

        return float(entry["value"]), self._source(entry["source_id"])

    def inhalation_saturation_cap_policy(self) -> tuple[dict[str, Any], AssumptionSourceReference]:
        entry = self.payload["inhalation_physical_caps"]["volatility_saturation_cap_policy"]
        return (
            {
                "reference_temperature_c": float(entry["reference_temperature_c"]),
                "requires_fields": list(entry["requires_fields"]),
                "skip_when_particle_material_context_present": bool(
                    entry.get("skip_when_particle_material_context_present", True)
                ),
            },
            self._source(entry["source_id"]),
        )

    def native_residual_air_reentry_surface_residue_fraction(
        self, product_subtype: str | None = None
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["inhalation_physical_caps"]["native_residual_air_reentry"][
            "surface_residue_fraction"
        ]
        entry = section["global"]
        if product_subtype:
            candidate = section.get("product_subtype_overrides", {}).get(product_subtype.lower())
            if candidate:
                entry = candidate
        return float(entry["value"]), self._source(entry["source_id"])

    def native_residual_air_reentry_surface_emission_rate_per_hour(
        self,
        *,
        vapor_pressure_mmhg: float | None = None,
        product_subtype: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["inhalation_physical_caps"]["native_residual_air_reentry"][
            "surface_emission_rate_per_hour"
        ]

        if vapor_pressure_mmhg is not None:
            best_match: dict[str, Any] | None = None
            for candidate in section.get("vapor_pressure_bands_mmhg", []):
                if vapor_pressure_mmhg >= float(candidate["minimum"]):
                    if best_match is None or float(candidate["minimum"]) > float(
                        best_match["minimum"]
                    ):
                        best_match = candidate
            if best_match is not None:
                return float(best_match["value"]), self._source(best_match["source_id"])

        entry = section["global"]
        if product_subtype:
            candidate = section.get("product_subtype_fallbacks", {}).get(product_subtype.lower())
            if candidate:
                entry = candidate
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_body_zone_surface_area_cm2(
        self, body_zone_profile: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = body_zone_profile.lower()
        values = self.payload["worker_dermal_execution_defaults"]["body_zone_surface_area_cm2"]
        ensure(
            key in values,
            "worker_dermal_body_zone_unsupported",
            f"Worker dermal body-zone profile '{body_zone_profile}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_ppe_penetration_factor(
        self, ppe_state: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = ppe_state.lower()
        values = self.payload["worker_dermal_execution_defaults"]["ppe_penetration_factor"]
        ensure(
            key in values,
            "worker_dermal_ppe_state_unsupported",
            f"Worker dermal PPE state '{ppe_state}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_barrier_material_factor(
        self, barrier_material: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = barrier_material.lower()
        values = self.payload["worker_dermal_execution_defaults"]["barrier_material_factor"]
        ensure(
            key in values,
            "worker_dermal_barrier_material_unsupported",
            f"Worker dermal barrier material '{barrier_material}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_barrier_chemistry_factor(
        self,
        barrier_material: str,
        *,
        log_kow: float | None = None,
        water_solubility_mg_per_l: float | None = None,
    ) -> tuple[str, float, AssumptionSourceReference]:
        profile = "generic"
        if (
            water_solubility_mg_per_l is not None
            and water_solubility_mg_per_l >= 10000.0
            and (log_kow is None or log_kow < 2.0)
        ):
            profile = "aqueous_polar"
        elif (
            log_kow is not None
            and log_kow >= 4.0
            and (water_solubility_mg_per_l is None or water_solubility_mg_per_l < 1000.0)
        ):
            profile = "hydrophobic_solvent_like"
        elif log_kow is not None or water_solubility_mg_per_l is not None:
            profile = "mixed_organic"

        values = self.payload["worker_dermal_execution_defaults"]["barrier_chemistry_factor"]
        profile_values = values.get(profile, values["generic"])
        material_key = barrier_material.lower()
        entry = profile_values.get(material_key, profile_values["unknown"])
        return profile, float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_barrier_breakthrough_lag_hours(
        self,
        barrier_material: str,
        *,
        chemistry_profile: str = "generic",
    ) -> tuple[float, AssumptionSourceReference]:
        values = self.payload["worker_dermal_execution_defaults"][
            "barrier_breakthrough_lag_hours"
        ]
        profile_values = values.get(chemistry_profile, values["generic"])
        material_key = barrier_material.lower()
        entry = profile_values.get(material_key, profile_values["unknown"])
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_barrier_breakthrough_transition_hours(
        self,
    ) -> tuple[float, AssumptionSourceReference]:
        entry = self.payload["worker_dermal_execution_defaults"][
            "barrier_breakthrough_transition_hours"
        ]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_skin_condition_factor(
        self, skin_condition: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = skin_condition.lower()
        values = self.payload["worker_dermal_execution_defaults"]["skin_condition_factor"]
        ensure(
            key in values,
            "worker_dermal_skin_condition_unsupported",
            f"Worker dermal skin condition '{skin_condition}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_base_absorption_fraction(
        self, physical_form: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = physical_form.lower()
        values = self.payload["worker_dermal_execution_defaults"]["absorption_fraction_defaults"]
        if key not in values:
            key = "global"
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_contact_pattern_factor(
        self, contact_pattern: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = contact_pattern.lower()
        values = self.payload["worker_dermal_execution_defaults"]["contact_pattern_factor"]
        ensure(
            key in values,
            "worker_dermal_contact_pattern_unsupported",
            f"Worker dermal contact pattern '{contact_pattern}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_contact_duration_factor(
        self, contact_duration_hours: float
    ) -> tuple[float, AssumptionSourceReference]:
        ensure(
            contact_duration_hours > 0.0,
            "worker_dermal_contact_duration_invalid",
            "Worker dermal contact duration must be positive.",
        )
        entry = self.payload["worker_dermal_execution_defaults"]["contact_duration_scaling"]
        reference_hours = float(entry["reference_hours"])
        minimum_factor = float(entry["minimum_factor"])
        maximum_factor = float(entry["maximum_factor"])
        factor = min(max(contact_duration_hours / reference_hours, minimum_factor), maximum_factor)
        return factor, self._source(entry["source_id"])

    def _worker_dermal_threshold_factor(
        self,
        section_name: str,
        value: float,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["worker_dermal_execution_defaults"][section_name]
        entry = section["default"]
        for candidate in section.get("thresholds", []):
            minimum = float(candidate["minimum"])
            if value >= minimum:
                entry = candidate
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_dermal_log_kow_factor(
        self, log_kow: float
    ) -> tuple[float, AssumptionSourceReference]:
        return self._worker_dermal_threshold_factor("log_kow_factor", log_kow)

    def worker_dermal_molecular_weight_factor(
        self, molecular_weight_g_per_mol: float
    ) -> tuple[float, AssumptionSourceReference]:
        return self._worker_dermal_threshold_factor(
            "molecular_weight_factor",
            molecular_weight_g_per_mol,
        )

    def worker_dermal_water_solubility_factor(
        self, water_solubility_mg_per_l: float
    ) -> tuple[float, AssumptionSourceReference]:
        return self._worker_dermal_threshold_factor(
            "water_solubility_factor",
            water_solubility_mg_per_l,
        )

    def worker_dermal_evaporation_rate_per_hour(
        self, vapor_pressure_mmhg: float
    ) -> tuple[float, AssumptionSourceReference]:
        return self._worker_dermal_threshold_factor(
            "evaporation_competition_rate_per_hour",
            vapor_pressure_mmhg,
        )

    def worker_dermal_chemical_context_factor_bounds(
        self,
    ) -> tuple[tuple[float, float], AssumptionSourceReference]:
        entry = self.payload["worker_dermal_execution_defaults"]["chemical_context_factor_bounds"]
        return (
            (float(entry["minimum_factor"]), float(entry["maximum_factor"])),
            self._source(entry["source_id"]),
        )

    def worker_dermal_max_retained_surface_loading_mg_per_cm2(
        self,
        *,
        physical_form: str | None = None,
        contact_profile: str | None = None,
    ) -> tuple[float, AssumptionSourceReference]:
        section = self.payload["worker_dermal_execution_defaults"][
            "max_retained_surface_loading_mg_per_cm2"
        ]
        entry = section["global"]
        if physical_form:
            candidate = section.get("physical_form_overrides", {}).get(physical_form.lower())
            if candidate:
                entry = candidate
        if contact_profile:
            candidate = section.get("contact_profile_overrides", {}).get(contact_profile.lower())
            if candidate:
                entry = candidate
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_inhalation_control_profile_factor(
        self, control_profile: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = control_profile.lower()
        values = self.payload["worker_inhalation_execution_defaults"]["control_profile_factor"]
        ensure(
            key in values,
            "worker_inhalation_control_profile_unsupported",
            f"Worker inhalation control profile '{control_profile}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_inhalation_control_context_factor(
        self, context_terms: list[str]
    ) -> tuple[str, float, AssumptionSourceReference]:
        values = self.payload["worker_inhalation_execution_defaults"]["control_context_factor"]
        normalized_terms = " ".join(
            item.strip().lower().replace("-", "_").replace(" ", "_")
            for item in context_terms
            if item and item.strip()
        )
        label = "generic"
        entry = values[label]
        for candidate_label, candidate_entry in values.items():
            tokens = tuple(str(item).lower() for item in candidate_entry.get("tokens", []))
            if not tokens:
                continue
            if any(token in normalized_terms for token in tokens):
                if float(candidate_entry["value"]) < float(entry["value"]):
                    label = candidate_label
                    entry = candidate_entry
        return label, float(entry["value"]), self._source(entry["source_id"])

    def worker_inhalation_respiratory_protection_factor(
        self, respiratory_protection: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = respiratory_protection.lower()
        values = self.payload["worker_inhalation_execution_defaults"][
            "respiratory_protection_factor"
        ]
        if key not in values and "respirator" in key:
            key = "generic_respirator"
        ensure(
            key in values,
            "worker_inhalation_respiratory_protection_unsupported",
            (
                "Worker inhalation respiratory protection state "
                f"'{respiratory_protection}' is not supported."
            ),
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_inhalation_vapor_release_fraction(
        self, emission_profile: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = emission_profile.lower()
        values = self.payload["worker_inhalation_execution_defaults"][
            "vapor_release_fraction_defaults"
        ]
        if key not in values:
            key = "generic_inhalation_release_profile"
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])

    def worker_inhalation_task_intensity_factor(
        self, task_intensity: str
    ) -> tuple[float, AssumptionSourceReference]:
        key = task_intensity.lower()
        values = self.payload["worker_inhalation_execution_defaults"]["task_intensity_factor"]
        ensure(
            key in values,
            "worker_inhalation_task_intensity_unsupported",
            f"Worker inhalation task intensity '{task_intensity}' is not supported.",
            suggestion=f"Use one of: {', '.join(sorted(values))}.",
        )
        entry = values[key]
        return float(entry["value"]), self._source(entry["source_id"])


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
            "  `direct_oral=1.0`, the direct-intake oral ingestion fraction of `1.0`, and",
            "  the dermal `hand_application` and `trigger_spray` transfer defaults of `1.0`",
            "  when the modeled product amount is interpreted as the skin-boundary amount",
            "  for direct-application or spray-contact screening.",
            "",
            "### Heuristic Density Defaults",
            "",
            "- `heuristic_density_defaults_v1` covers liquid-product density screening values and",
            "  the current category/form overrides. These are still benchmark heuristics and",
            "  should be replaced with product-family packs when curated density data are",
            "  available.",
            "",
            "### Heuristic Pest-Control Aerosol Density Bridge 2026",
            "",
            "- `heuristic_consexpo_pest_control_aerosol_density_bridge_2026` is an explicit",
            "  interim density branch for subtype-specific pest-control aerosol scenarios such",
            "  as `air_space_insecticide`, where solvent-propellant style product families are",
            "  not well represented by the generic liquid screening density.",
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
            "### SCCS Notes of Guidance Retention Defaults",
            "",
            "- `sccs_notes_of_guidance_12th_revision_2023` anchors the immediate rinse-off",
            "  retention factor of `0.01` directly to the official SCCS Notes of Guidance",
            "  retention-factor convention for rinse-off cosmetic products.",
            "",
            "### Heuristic Transfer Defaults",
            "",
            "- `heuristic_transfer_efficiency_defaults_v1` now covers only the residual",
            "  fallback transfer-efficiency benchmarks for wiping and pouring contexts.",
            "",
            "### Worker Dermal Body-Zone Area Heuristics 2026",
            "",
            "- `worker_dermal_body_zone_area_heuristics_2026` provides bounded body-zone area",
            "  anchors for worker dermal absorbed-dose execution when callers do not supply an",
            "  explicit exposed surface area. These are not intended to replace task-specific",
            "  patch or wipe measurements.",
            "",
            "### Inhalation Physical Caps 2026",
            "",
            "- `inhalation_deposition_sink_heuristics_2026` adds a bounded first-order",
            "  deposition sink to room-air inhalation screening. These defaults are simple",
            "  settling heuristics keyed to spray family or particle-size regime, not a full",
            "  aerosol transport solver.",
            "- `inhalation_extrathoracic_oral_handoff_heuristics_2026` adds bounded",
            "  extrathoracic swallowed-fraction splits for spray inhalation families so coarse",
            "  and mixed sprays can expose an oral handoff estimate without claiming a full",
            "  regional-deposition model.",
            "- `inhalation_volatility_saturation_cap_policy_2026` publishes the shared",
            "  thermodynamic saturation-cap policy used when both vapor pressure and molecular",
            "  weight are available. The cap prevents impossible supersaturated room-air",
            "  concentrations in volatility-aware screening runs.",
            "- `native_residual_air_reentry_emission_heuristics_2026` adds a bounded treated-",
            "  surface residue fraction and first-order surface-emission rate for the native",
            "  residual-air reentry mode. These defaults are deliberately simple indoor",
            "  screening heuristics, not SVOC partitioning or chamber-emission physics.",
            "",
            "### Worker Dermal Surface-Cap Heuristics 2026",
            "",
            "- `worker_dermal_surface_loading_cap_heuristics_2026` bounds retained skin-surface",
            "  loading before PPE and absorption are applied. Excess mass is treated as runoff",
            "  or non-retained loading rather than silently accumulating at the skin boundary.",
            "",
            "### Worker Dermal PPE Penetration Heuristics 2026",
            "",
            "- `worker_dermal_ppe_penetration_heuristics_2026` provides generic residual",
            "  penetration factors for work gloves, chemical-resistant gloves, protective",
            "  clothing, and combined barriers. These are screening barrier modifiers, not",
            "  glove-breakthrough kinetics or material-specific permeation data.",
            "",
            "### Worker Dermal Barrier-Material Heuristics 2026",
            "",
            "- `worker_dermal_barrier_material_heuristics_2026` adds bounded material-specific",
            "  modifiers for nitrile, latex, neoprene, butyl, PVC, laminate, and textile",
            "  barriers. These refine the residual penetration factor but still do not model",
            "  certified glove performance or full permeation kinetics.",
            "- The same source family now also carries bounded barrier-chemistry interaction",
            "  profiles so solvent-like versus aqueous contexts can refine the effective",
            "  barrier assumption without claiming certified glove permeation data.",
            "",
            "### Worker Dermal Breakthrough-Timing Heuristics 2026",
            "",
            "- `worker_dermal_breakthrough_timing_heuristics_2026` adds bounded lag-time and",
            "  transition-window defaults so short-duration worker contacts can attenuate the",
            "  effective PPE penetration factor before steady residual penetration is assumed.",
            "  These are screening timing profiles, not certified EN 374 breakthrough curves",
            "  or material-specific permeation kinetics.",
            "",
            "### Worker Dermal Absorption Fraction Heuristics 2026",
            "",
            "- `worker_dermal_absorption_fraction_heuristics_2026` provides bounded physical-",
            "  form screening anchors for translating skin-boundary mass into absorbed dermal",
            "  mass when no chemical-specific dermal permeability or absorption dataset is",
            "  available.",
            "",
            "### Worker Dermal Physchem Modifier Heuristics 2026",
            "",
            "- `worker_dermal_physchem_modifier_heuristics_2026` adds bounded modifiers from",
            "  caller-supplied `logKow`, molecular weight, and water solubility so worker",
            "  dermal execution can be chemistry-aware without claiming a true permeation",
            "  model.",
            "",
            "### Worker Dermal Evaporation-Competition Heuristics 2026",
            "",
            "- `worker_dermal_evaporation_competition_heuristics_2026` adds a bounded",
            "  vapor-pressure-driven evaporation rate so high-volatility contacts can reduce",
            "  effective dermal absorption as contact time increases. This is a screening",
            "  competition term, not a full mass-transfer or finite-dose evaporation model.",
            "",
            "### Worker Dermal Contact Duration Scaling Heuristics 2026",
            "",
            "- `worker_dermal_contact_duration_scaling_heuristics_2026` provides a saturating",
            "  duration adjustment for absorbed-dose screening so very short contacts do not",
            "  silently inherit full-shift absorption semantics.",
            "",
            "### Worker Inhalation Control-Factor Heuristics 2026",
            "",
            "- `worker_inhalation_control_factor_heuristics_2026` provides bounded workplace",
            "  control-profile modifiers for the executable worker inhalation surrogate layer.",
            "  These factors are intended for transparent screening refinement, not as",
            "  substitutes for ART determinants or measured control efficiency.",
            "",
            "### Worker Inhalation Control-Context Heuristics 2026",
            "",
            "- `worker_inhalation_control_context_heuristics_2026` provides bounded",
            "  refinements for explicit capture hoods, spray booths, portable extractors,",
            "  and segregation/distance controls layered on top of the broader",
            "  `controlProfile` factor. These modifiers remain screening heuristics and",
            "  should not be treated as measured LEV capture efficiency.",
            "",
            "### Worker Inhalation Respiratory-Protection Heuristics 2026",
            "",
            "- `worker_inhalation_rpe_factor_heuristics_2026` provides residual inhalation",
            "  intake fractions for broad respiratory-protection states. They are screening",
            "  intake modifiers, not assigned protection factors for a compliance program.",
            "",
            "### Worker Inhalation Vapor-Release Heuristics 2026",
            "",
            "- `worker_inhalation_vapor_release_fraction_heuristics_2026` provides bounded",
            "  non-spray release fractions for worker inhalation execution when the current",
            "  task is vapor-generating and no direct spray airborne-fraction default applies.",
            "",
            "### Worker Inhalation Task-Intensity Heuristics 2026",
            "",
            "- `worker_inhalation_task_intensity_heuristics_2026` provides bounded",
            "  inhalation-rate scaling factors for light, moderate, and high worker task",
            "  intensity classes. These are screening physiology modifiers, not measured",
            "  minute-ventilation or metabolic-rate models.",
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
            "### RIVM Disinfectant Trigger-Spray Airborne Fraction Defaults 2006",
            "",
            "- `rivm_disinfectant_trigger_spray_airborne_fraction_defaults_2006` maps the",
            "  RIVM Disinfectant Products Fact Sheet surface trigger-spray default onto the MCP",
            "  inhalation screening abstraction for `disinfectant` contexts. The current branch",
            "  uses `trigger_spray=0.2` for short surface-spray tasks.",
            "",
            "### RIVM Cosmetics Sprays Airborne Fraction Defaults 2025",
            "",
            "- `rivm_cosmetics_sprays_airborne_fraction_defaults_2025` maps RIVM Cosmetics",
            "  Fact Sheet spray-product defaults onto the MCP inhalation screening abstraction",
            "  for `personal_care` contexts. The current curated anchors are `pump_spray=0.2`",
            "  and `aerosol_spray=0.9`, reflecting product-family screening defaults for",
            "  cosmetic pump and aerosol sprays rather than a universal spray model.",
            "",
            "### Heuristic Pest-Control Trigger-Spray Airborne Fraction Bridge 2026",
            "",
            "- `heuristic_consexpo_pest_control_trigger_spray_airborne_fraction_bridge_2026`",
            "  is an explicit interim bridge for generic `pest_control` and `pesticide`",
            "  trigger-spray scenarios. The current `0.15` branch centers the RIVM ConsExpo",
            "  spray-family evidence between the `0.2` plant-spray trigger-spray family and the",
            "  `0.1` crawling-insect trigger-spray family, and keeps the branch heuristic until",
            "  broader use-subtype-specific packs are published.",
            "",
            "### Heuristic Pest-Control Aerosol Airborne Fraction Bridge 2026",
            "",
            "- `heuristic_consexpo_pest_control_aerosol_airborne_fraction_bridge_2026` is an",
            "  explicit interim bridge for `air_space_insecticide` aerosol scenarios. The",
            "  current `aerosol_spray=1.0` branch treats the emitted active mass as a whole-room",
            "  airborne release boundary for screening, while keeping the pack heuristic until a",
            "  richer aerosol-use determinant set is published.",
            "",
            "### Heuristic Spray Airborne Fraction Defaults",
            "",
            "- `heuristic_residual_spray_airborne_fraction_defaults_v1` covers the remaining",
            "  spray airborne-fraction branches outside the curated cleaner and personal-care",
            "  product families that still need evidence-linked product-family packs.",
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
            "### Heuristic Pest-Control Air-Space Room Defaults Bridge 2026",
            "",
            "- `heuristic_consexpo_pest_control_air_space_room_defaults_bridge_2026` provides",
            "  subtype-specific whole-room anchors for `air_space_insecticide` scenarios, using",
            "  a larger room volume and longer post-application duration than the default short",
            "  surface-spray screening room branch.",
            "",
            "### ECHA Consumer Inhalation Room Defaults",
            "",
            "- `echa_consumer_inhalation_room_defaults` is used only for EU-region inhalation room",
            "  defaults, where a higher ventilation benchmark is appropriate for consumer",
            "  spray-style screening than the generic global fallback.",
            "",
            "- Density resolution follows `global -> product category -> physical form ->",
            "  product_subtype`, so subtype-specific screening packs can override broad family",
            "  and form defaults when they are available.",
            "- Transfer efficiency uses method-specific global defaults with product-category",
            "  overrides applied only where the defaults pack declares them explicitly.",
            "- Aerosolized fraction resolves in the order `product_subtype -> product category",
            "  -> global` for each application method, so subtype-specific ConsExpo branches can",
            "  override broad family defaults without changing the caller-supplied scenario class.",
            "- Inhalation room defaults resolve in the order `global -> region -> product",
            "  category -> application method -> product_subtype`, with selector-specific",
            "  regional branches taking precedence when a defaults pack publishes them.",
        ]
    )
    return "\n".join(lines)


def _curation_status(source_id: str) -> DefaultsCurationStatus:
    if source_id.startswith("heuristic_"):
        return DefaultsCurationStatus.HEURISTIC
    if source_id.startswith("screening_"):
        return DefaultsCurationStatus.ROUTE_SEMANTIC
    return DefaultsCurationStatus.CURATED


def _path_id(parameter_name: str, applicability: dict[str, object]) -> str:
    if not applicability:
        return f"{parameter_name}:global"
    selectors = ",".join(f"{key}={applicability[key]}" for key in sorted(applicability))
    return f"{parameter_name}:{selectors}"


def _entry_note(
    parameter_name: str,
    source_id: str,
    applicability: dict[str, object],
) -> str | None:
    if source_id.startswith("heuristic_"):
        return (
            f"`{parameter_name}` still resolves from a heuristic screening family for this "
            "applicability branch."
        )
    if source_id.startswith("screening_"):
        return (
            f"`{parameter_name}` is treated as a route-semantic boundary condition for this "
            "branch rather than an empirical fitted factor."
        )
    if applicability:
        selectors = ", ".join(f"{key}={value}" for key, value in sorted(applicability.items()))
        return f"Curated default branch resolved for {selectors}."
    return "Curated default branch resolved for the global fallback."


def _append_entry(
    entries: list[DefaultsCurationEntry],
    registry: DefaultsRegistry,
    *,
    parameter_name: str,
    value: object,
    source_id: str,
    applicability: dict[str, object] | None = None,
) -> None:
    applicability = applicability or {}
    source = registry.source_reference(source_id)
    entries.append(
        DefaultsCurationEntry(
            pathId=_path_id(parameter_name, applicability),
            parameterName=parameter_name,
            applicability=applicability,
            value=value,
            unit=DEFAULT_PARAMETER_UNITS.get(parameter_name),
            sourceId=source.source_id,
            sourceLocator=source.locator,
            curationStatus=_curation_status(source.source_id),
            note=_entry_note(parameter_name, source.source_id, applicability),
        )
    )


def build_defaults_curation_report(
    registry: DefaultsRegistry | None = None,
) -> DefaultsCurationReport:
    active_registry = registry or DefaultsRegistry.load()
    payload = active_registry.payload
    entries: list[DefaultsCurationEntry] = []

    for population_group, entry in payload.get("population_defaults", {}).items():
        for parameter_name in (
            "body_weight_kg",
            "inhalation_rate_m3_per_hour",
            "exposed_surface_area_cm2",
        ):
            _append_entry(
                entries,
                active_registry,
                parameter_name=parameter_name,
                value=entry[parameter_name],
                source_id=entry["source_id"],
                applicability={"population_group": population_group},
            )

    conversion_defaults = payload.get("conversion_defaults", {})
    global_density = conversion_defaults.get("global")
    if global_density:
        _append_entry(
            entries,
            active_registry,
            parameter_name="density_g_per_ml",
            value=global_density["density_g_per_ml"],
            source_id=global_density["source_id"],
        )
    for product_category, entry in (
        conversion_defaults.get("product_category_overrides", {}).items()
    ):
        _append_entry(
            entries,
            active_registry,
            parameter_name="density_g_per_ml",
            value=entry["density_g_per_ml"],
            source_id=entry["source_id"],
            applicability={"product_category": product_category},
        )
    for physical_form, entry in conversion_defaults.get("physical_form_overrides", {}).items():
        _append_entry(
            entries,
            active_registry,
            parameter_name="density_g_per_ml",
            value=entry["density_g_per_ml"],
            source_id=entry["source_id"],
            applicability={"physical_form": physical_form},
        )
    for product_subtype, entry in (
        conversion_defaults.get("product_subtype_overrides", {}).items()
    ):
        _append_entry(
            entries,
            active_registry,
            parameter_name="density_g_per_ml",
            value=entry["density_g_per_ml"],
            source_id=entry["source_id"],
            applicability={"product_subtype": product_subtype},
        )

    def append_method_family(
        section_name: str,
        parameter_name: str,
        selector_key: str,
    ) -> None:
        section = payload.get(section_name, {})
        global_entries = section.get("global", section if "global" not in section else {})
        for selector_value, entry in global_entries.items():
            if not isinstance(entry, dict) or "value" not in entry:
                continue
            _append_entry(
                entries,
                active_registry,
                parameter_name=parameter_name,
                value=entry["value"],
                source_id=entry["source_id"],
                applicability={selector_key: selector_value},
            )
        for category, category_entries in section.get("product_category_overrides", {}).items():
            for selector_value, entry in category_entries.items():
                _append_entry(
                    entries,
                    active_registry,
                    parameter_name=parameter_name,
                    value=entry["value"],
                    source_id=entry["source_id"],
                    applicability={"product_category": category, selector_key: selector_value},
                )
        for subtype, subtype_entries in section.get("product_subtype_overrides", {}).items():
            for selector_value, entry in subtype_entries.items():
                _append_entry(
                    entries,
                    active_registry,
                    parameter_name=parameter_name,
                    value=entry["value"],
                    source_id=entry["source_id"],
                    applicability={"product_subtype": subtype, selector_key: selector_value},
                )

    append_method_family("retention_factor_defaults", "retention_factor", "retention_type")
    append_method_family(
        "transfer_efficiency_defaults",
        "transfer_efficiency",
        "application_method",
    )

    for application_method, entry in payload.get("ingestion_fraction_defaults", {}).items():
        _append_entry(
            entries,
            active_registry,
            parameter_name="ingestion_fraction",
            value=entry["value"],
            source_id=entry["source_id"],
            applicability={"application_method": application_method},
        )

    append_method_family(
        "aerosolized_fraction_defaults",
        "aerosolized_fraction",
        "application_method",
    )

    room_defaults = payload.get("room_defaults", {})
    room_global = room_defaults.get("global", {})
    for parameter_name, source_field in (
        ("room_volume_m3", "room_volume_source_id"),
        ("air_exchange_rate_per_hour", "air_exchange_rate_source_id"),
        ("exposure_duration_hours", "exposure_duration_source_id"),
    ):
        if parameter_name in room_global:
            _append_entry(
                entries,
                active_registry,
                parameter_name=parameter_name,
                value=room_global[parameter_name],
                source_id=room_global[source_field],
            )
    def append_room_selector_entry(
        selector_key: str,
        selector_value: str,
        selector_entry: dict[str, Any],
    ) -> None:
        for parameter_name, source_field in (
            ("room_volume_m3", "room_volume_source_id"),
            ("air_exchange_rate_per_hour", "air_exchange_rate_source_id"),
            ("exposure_duration_hours", "exposure_duration_source_id"),
        ):
            if parameter_name not in selector_entry:
                continue
            source_id = selector_entry.get(source_field, selector_entry.get("source_id"))
            _append_entry(
                entries,
                active_registry,
                parameter_name=parameter_name,
                value=selector_entry[parameter_name],
                source_id=source_id,
                applicability={selector_key: selector_value},
            )
        for region, regional_entry in selector_entry.get("regional_overrides", {}).items():
            for parameter_name, source_field in (
                ("room_volume_m3", "room_volume_source_id"),
                ("air_exchange_rate_per_hour", "air_exchange_rate_source_id"),
                ("exposure_duration_hours", "exposure_duration_source_id"),
            ):
                if parameter_name not in regional_entry:
                    continue
                source_id = regional_entry.get(source_field, regional_entry.get("source_id"))
                _append_entry(
                    entries,
                    active_registry,
                    parameter_name=parameter_name,
                    value=regional_entry[parameter_name],
                    source_id=source_id,
                    applicability={selector_key: selector_value, "region": region},
                )

    for region, entry in room_defaults.get("regional_overrides", {}).items():
        append_room_selector_entry("region", region, entry)
    for selector_key in (
        "product_category_overrides",
        "application_method_overrides",
        "product_subtype_overrides",
    ):
        selector_name = selector_key.removesuffix("_overrides")
        for selector_value, selector_entry in room_defaults.get(selector_key, {}).items():
            append_room_selector_entry(selector_name, selector_value, selector_entry)

    curated_count = sum(
        1 for item in entries if item.curation_status == DefaultsCurationStatus.CURATED
    )
    heuristic_count = sum(
        1 for item in entries if item.curation_status == DefaultsCurationStatus.HEURISTIC
    )
    route_semantic_count = sum(
        1 for item in entries if item.curation_status == DefaultsCurationStatus.ROUTE_SEMANTIC
    )
    return DefaultsCurationReport(
        defaultsVersion=active_registry.version,
        defaultsHashSha256=active_registry.sha256,
        entryCount=len(entries),
        curatedEntryCount=curated_count,
        heuristicEntryCount=heuristic_count,
        routeSemanticEntryCount=route_semantic_count,
        entries=entries,
        notes=[
            "This report resolves the published defaults pack into parameter-level branches with "
            "explicit applicability selectors.",
            "Curated means the branch resolves from a non-heuristic evidence-linked source family.",
            "Route-semantic means the branch is a deterministic screening boundary condition "
            "rather than an empirical exposure-factor fit.",
        ],
    )
