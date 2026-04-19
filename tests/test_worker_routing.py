from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    ExposureScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
    TierLevel,
    WorkerSupportStatus,
    WorkerTaskRoutingInput,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.plugins.inhalation import build_inhalation_tier_1_screening_scenario
from exposure_scenario_mcp.runtime import PluginRegistry, ScenarioEngine
from exposure_scenario_mcp.worker_routing import route_worker_task


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def test_worker_router_prefers_tier1_inhalation_for_worker_spray() -> None:
    decision = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id="DTXSID123",
            route=Route.INHALATION,
            scenario_class=ScenarioClass.INHALATION,
            product_use_profile=ProductUseProfile(
                product_category="disinfectant",
                physical_form="spray",
                application_method="trigger_spray",
                retention_type="surface_contact",
                concentration_fraction=0.03,
                use_amount_per_event=15.0,
                use_amount_unit="mL",
                use_events_per_day=2.0,
            ),
            population_profile=PopulationProfile(
                population_group="adult",
                demographic_tags=["worker", "occupational"],
                region="EU",
            ),
            requested_tier=TierLevel.TIER_1,
        )
    )

    assert decision.worker_detected is True
    assert decision.support_status == WorkerSupportStatus.SUPPORTED_WITH_CAVEATS
    assert decision.recommended_tool == "exposure_build_inhalation_tier1_screening_scenario"
    assert decision.recommended_model_family == "inhalation_near_field_far_field_screening"
    assert decision.guidance_resource == "docs://worker-routing-guide"


def test_worker_router_escalates_unsupported_airborne_task() -> None:
    decision = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id="DTXSID123",
            route=Route.INHALATION,
            scenario_class=ScenarioClass.INHALATION,
            product_use_profile=ProductUseProfile(
                product_category="industrial_maintenance",
                physical_form="liquid",
                application_method="pour",
                retention_type="surface_contact",
                concentration_fraction=0.15,
                use_amount_per_event=25.0,
                use_amount_unit="mL",
                use_events_per_day=1.0,
            ),
            population_profile=PopulationProfile(
                population_group="worker",
                demographic_tags=["worker"],
                region="EU",
            ),
        )
    )

    assert decision.worker_detected is True
    assert decision.support_status == WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED
    assert decision.recommended_tool is None
    assert decision.recommended_model_family == "art_adapter_candidate"


def test_worker_router_recommends_dermal_bridge_for_absorbed_dose_path() -> None:
    decision = route_worker_task(
        WorkerTaskRoutingInput(
            chemical_id="DTXSID123",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="industrial_maintenance",
                physical_form="liquid",
                application_method="pour_transfer",
                retention_type="surface_contact",
                concentration_fraction=0.15,
                use_amount_per_event=12.0,
                use_amount_unit="mL",
                use_events_per_day=1.0,
            ),
            population_profile=PopulationProfile(
                population_group="worker",
                demographic_tags=["worker"],
                region="EU",
            ),
            prefer_current_mcp=False,
        )
    )

    assert decision.worker_detected is True
    assert decision.support_status == WorkerSupportStatus.FUTURE_ADAPTER_RECOMMENDED
    assert decision.recommended_tool == "worker_export_dermal_absorbed_dose_bridge"
    assert decision.recommended_model_family == "dermal_absorption_ppe_adapter_candidate"


def test_worker_context_is_threaded_into_screening_scenario() -> None:
    scenario = build_engine().build(
        ExposureScenarioRequest(
            chemical_id="DTXSID123",
            route=Route.DERMAL,
            scenario_class=ScenarioClass.SCREENING,
            product_use_profile=ProductUseProfile(
                product_category="household_cleaner",
                physical_form="liquid",
                application_method="wipe",
                retention_type="surface_contact",
                concentration_fraction=0.02,
                use_amount_per_event=8.0,
                use_amount_unit="g",
                use_events_per_day=2.0,
            ),
            population_profile=PopulationProfile(
                population_group="adult",
                demographic_tags=["worker", "occupational"],
                region="EU",
            ),
        )
    )

    assert scenario.route_metrics["worker_context_detected"] is True
    assert scenario.route_metrics["worker_support_status"] == "supported_with_caveats"
    assert scenario.route_metrics["worker_recommended_tool"] == (
        "exposure_build_screening_exposure_scenario"
    )
    assert any(flag.code == "worker_task_context" for flag in scenario.quality_flags)
    assert any(flag.code == "worker_shared_screening_engine" for flag in scenario.quality_flags)
    assert any(item.code == "worker_model_boundary" for item in scenario.limitations)
    assert "worker task triage" in scenario.fit_for_purpose.suitable_for


def test_worker_context_is_threaded_into_tier1_inhalation_service() -> None:
    scenario = build_inhalation_tier_1_screening_scenario(
        InhalationTier1ScenarioRequest(
            chemical_id="DTXSID123",
            route=Route.INHALATION,
            product_use_profile=ProductUseProfile(
                product_category="disinfectant",
                physical_form="spray",
                application_method="trigger_spray",
                retention_type="surface_contact",
                concentration_fraction=0.03,
                use_amount_per_event=15.0,
                use_amount_unit="mL",
                use_events_per_day=2.0,
                room_volume_m3=35.0,
                exposure_duration_hours=0.5,
                air_exchange_rate_per_hour=2.0,
            ),
            population_profile=PopulationProfile(
                population_group="adult",
                body_weight_kg=75.0,
                inhalation_rate_m3_per_hour=1.1,
                demographic_tags=["worker", "occupational"],
                region="EU",
            ),
            source_distance_m=0.35,
            spray_duration_seconds=10.0,
            near_field_volume_m3=2.0,
            airflow_directionality=AirflowDirectionality.CROSS_DRAFT,
            particle_size_regime=ParticleSizeRegime.COARSE_SPRAY,
        ),
        DefaultsRegistry.load(),
    )

    assert scenario.route_metrics["worker_context_detected"] is True
    assert scenario.route_metrics["worker_support_status"] == "supported_with_caveats"
    assert any(flag.code == "worker_task_context" for flag in scenario.quality_flags)
    assert any(item.code == "worker_model_boundary" for item in scenario.limitations)
