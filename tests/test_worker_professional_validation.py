
import pytest
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.worker_tier2 import (
    ExportWorkerInhalationTier2BridgeRequest,
    build_worker_inhalation_tier2_bridge,
    execute_worker_inhalation_tier2_task,
    ExecuteWorkerInhalationTier2Request,
    WorkerInhalationTier2ExecutionOverrides,
)

def test_professional_cleaning_validation_check():
    registry = DefaultsRegistry.load()
    
    bridge_request = {
        "schema_version": "exportWorkerInhalationTier2BridgeRequest.v1",
        "baseRequest": {
          "schema_version": "inhalationTier1ScenarioRequest.v1",
          "chemical_id": "DTXSID7020182",
          "chemical_name": "Example Disinfectant",
          "route": "inhalation",
          "scenario_class": "inhalation",
          "product_use_profile": {
            "schema_version": "productUseProfile.v1",
            "product_name": "Professional Disinfectant Spray",
            "product_subtype": "professional_surface_disinfectant",
            "product_category": "disinfectant",
            "physical_form": "spray",
            "application_method": "trigger_spray",
            "retention_type": "surface_contact",
            "concentration_fraction": 0.005,
            "use_amount_per_event": 100.0,
            "use_amount_unit": "g",
            "use_events_per_day": 1.0,
            "room_volume_m3": 300.0,
            "air_exchange_rate_per_hour": 2.0,
            "exposure_duration_hours": 2.0
          },
          "population_profile": {
            "schema_version": "populationProfile.v1",
            "population_group": "adult",
            "body_weight_kg": 75.0,
            "inhalation_rate_m3_per_hour": 1.1,
            "region": "EU"
          },
          "requestedTier": "tier_1",
          "source_distance_m": 1.0,
          "spray_duration_seconds": 60.0,
          "near_field_volume_m3": 50.0,
          "airflow_directionality": "cross_draft",
          "particle_size_regime": "coarse_spray"
        },
        "targetModelFamily": "art",
        "taskDescription": "Professional surface disinfection spray task in an indoor room",
        "workplaceSetting": "indoor room",
        "taskDurationHours": 2.0,
        "ventilationContext": "general_ventilation",
        "localControls": [
          "professional cleaning control profile"
        ],
        "respiratoryProtection": "none",
        "emissionDescriptor": "professional trigger spray for large-surface disinfection",
        "contextOfUse": "worker-tier2-bridge"
    }

    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(**bridge_request),
        registry=registry,
    )
    
    execution = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=bridge_package.tool_call.arguments,
            execution_overrides=WorkerInhalationTier2ExecutionOverrides(
                controlFactor=0.45,
                respiratoryProtectionFactor=1.0
            ),
            context_of_use="worker-art-execution",
        ),
        registry=registry,
    )
    
    summary = execution.validation_summary
    assert "worker_inhalation_professional_surface_disinfectant_execution" in summary.benchmark_case_ids
    
    check = next((c for c in summary.executed_validation_checks if c.check_id == "worker_biocidal_professional_cleaning_concentration_2023"), None)
    assert check is not None
    assert check.status.value == "pass"
    assert check.observed_value == pytest.approx(0.03337553, rel=1e-6)
    assert check.reference_lower == 0.015
    assert check.reference_upper == 0.045

if __name__ == "__main__":
    test_professional_cleaning_validation_check()
    print("Validation check PASSED!")
