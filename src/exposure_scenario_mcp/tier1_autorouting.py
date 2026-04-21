"""Benchmark-backed gating for Tier 1 two-zone auto-selection."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, cast

from exposure_scenario_mcp.assets import read_text_asset
from exposure_scenario_mcp.models import InhalationTier1ScenarioRequest

TIER_1_SPRAY_METHODS = {"trigger_spray", "pump_spray", "aerosol_spray"}
TIER1_TWO_ZONE_AUTO_ENABLED = False


@lru_cache(maxsize=1)
def tier1_two_zone_autorouting_manifest() -> dict[str, Any]:
    raw_text, _, _ = read_text_asset(
        "data/tier1_inhalation/v1/two_zone_autorouting_manifest.json",
        "tier1_inhalation/v1/two_zone_autorouting_manifest.json",
    )
    return cast(dict[str, Any], json.loads(raw_text))


def approved_two_zone_profile_ids() -> frozenset[str]:
    payload = tier1_two_zone_autorouting_manifest()
    approved_profiles = payload.get("approvedProfileIds", [])
    if not isinstance(approved_profiles, list):
        return frozenset()
    return frozenset(item for item in approved_profiles if isinstance(item, str))


def can_auto_select_two_zone(
    request: InhalationTier1ScenarioRequest,
    matched_profile: Any,
    *,
    saturation_cap_applied: bool,
) -> bool:
    """Return True only when the current benchmark-backed gating conditions are satisfied."""

    if not TIER1_TWO_ZONE_AUTO_ENABLED:
        return False
    if request.product_use_profile.application_method not in TIER_1_SPRAY_METHODS:
        return False
    if saturation_cap_applied or matched_profile is None:
        return False
    if not getattr(matched_profile, "supports_two_zone", False):
        return False
    profile_id = getattr(matched_profile, "profile_id", None)
    return isinstance(profile_id, str) and profile_id in approved_two_zone_profile_ids()
