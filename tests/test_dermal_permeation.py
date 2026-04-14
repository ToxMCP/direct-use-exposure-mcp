import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PhyschemContext,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.worker_dermal import (
    ExecuteWorkerDermalAbsorbedDoseRequest,
    ExportWorkerDermalAbsorbedDoseBridgeRequest,
    WorkerDermalContactPattern,
    WorkerDermalPpeState,
    build_worker_dermal_absorbed_dose_bridge,
    execute_worker_dermal_absorbed_dose_task,
)


def test_potts_guy_permeation_constraint_is_applied() -> None:
    registry = DefaultsRegistry.load()

    # High MW (500), Low logKow (0.5) -> Very low Kp
    # log Kp = -2.72 + 0.71*0.5 - 0.0061*500 = -5.415
    # Kp = 10^-5.415 = 3.8459e-6 cm/h

    base_req = ExposureScenarioRequest(
        chemical_id="DTXSID_PERM",
        chemical_name="Low Permeability Chemical",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        physchem_context=PhyschemContext(
            molecular_weight_g_per_mol=500.0,
            log_kow=0.5,
            water_solubility_mg_per_l=100.0,
        ),
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="liquid",
            application_method="wipe",
            retention_type="leave_on",
            concentration_fraction=0.1,  # 10% solution
            use_amount_per_event=20.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            exposure_duration_hours=8.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80.0,
            exposed_surface_area_cm2=840.0,
        ),
    )

    bridge_req = ExportWorkerDermalAbsorbedDoseBridgeRequest(
        base_request=base_req,
        task_description="Long duration contact with low permeability chemical",
        workplace_setting="industrial",
        contact_duration_hours=8.0,
        contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
        exposed_body_areas=["hands"],
        ppe_state=WorkerDermalPpeState.NONE,
    )

    package = build_worker_dermal_absorbed_dose_bridge(bridge_req, registry=registry)

    execution = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=package.adapter_request,
            context_of_use="worker-art-execution",
        ),
        registry=registry,
    )

    # 1. Verify Kp calculation
    # log_kp = -2.72 + 0.71*0.5 - 0.0061*500 = -5.415
    # kp = 10^-5.415 = 0.0000038459
    assert execution.route_metrics["pottsGuyKpCmPerHour"] == pytest.approx(
        0.0000038459, rel=1e-4
    )

    # 2. Verify Permeation Limited Mass
    # Cv = Density (1.0) * 1000 * 0.1 = 100 mg/cm3
    # Flux J = Kp * Cv = 0.00038459 mg/cm2/h
    # Mass = J * Area (840) * Duration (8) = 0.00038459 * 840 * 8 = 2.584 mg
    expected_perm_mass = 0.000384591 * 840 * 8
    assert execution.route_metrics["permeationLimitedAbsorbedMassMgDay"] == pytest.approx(
        expected_perm_mass, rel=1e-4
    )

    # 3. Verify Fraction-based absorbed mass
    # External Mass = 20g * 1000 * 0.1 = 2000 mg
    # Base absorption fraction for liquid is 0.1 (10%)
    # Absorbed mass (fraction) = 2000 * 0.1 = 200 mg
    # Since 2.584 < 200, the permeation limit should be active
    assert execution.route_metrics["absorbedMassMgPerDay"] == pytest.approx(
        expected_perm_mass, rel=1e-4
    )

    # 4. Verify Quality Flag
    assert any(
        q.code == "worker_dermal_permeation_limit_active"
        for q in execution.quality_flags
    )

    # 5. Verify Rationale
    abs_mass_assumption = next(
        a for a in execution.assumptions if a.name == "absorbed_mass_mg_per_day"
    )
    assert "constrained by the mechanistic permeation limit" in abs_mass_assumption.rationale


def test_fraction_based_limit_is_applied_when_lower() -> None:
    registry = DefaultsRegistry.load()

    # High logKow (5.0), Low MW (100) -> Very high Kp
    # log Kp = -2.72 + 0.71*5.0 - 0.0061*100 = 0.22
    # Kp = 10^0.22 = 1.6596 cm/h

    base_req = ExposureScenarioRequest(
        chemical_id="DTXSID_FAST",
        chemical_name="High Permeability Chemical",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        physchem_context=PhyschemContext(
            molecular_weight_g_per_mol=100.0,
            log_kow=5.0,
            water_solubility_mg_per_l=10.0,
        ),
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="liquid",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.001,  # 0.1% solution
            use_amount_per_event=1.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=80.0,
            exposed_surface_area_cm2=100.0,
        ),
    )

    bridge_req = ExportWorkerDermalAbsorbedDoseBridgeRequest(
        base_request=base_req,
        task_description="Short duration contact with high permeability chemical",
        workplace_setting="industrial",
        contact_duration_hours=1.0,
        contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
        exposed_body_areas=["hands"],
        ppe_state=WorkerDermalPpeState.NONE,
    )

    package = build_worker_dermal_absorbed_dose_bridge(bridge_req, registry=registry)

    execution = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=package.adapter_request,
            context_of_use="worker-art-execution",
        ),
        registry=registry,
    )

    # Permeation Limited Mass
    # log Kp = 0.22 -> Kp = 1.6596 cm/h
    # Cv = 1.0 * 1000 * 0.001 = 1 mg/cm3
    # Flux J = 1.6596 * 1 = 1.6596 mg/cm2/h
    # Mass = 1.6596 * 100 * 1 = 165.96 mg

    # Fraction-based absorbed mass
    # External Mass = 1g * 1000 * 0.001 = 1 mg
    # Base absorption fraction for liquid is 0.1
    # Total factor = 0.1 * 1.0 * 1.0 * 1.0 * 0.8415 = 0.08415
    # Absorbed mass (fraction) = 1 * 0.08415 = 0.08415 mg
    
    # Since 0.08415 < 165.96, the fraction-based limit should be active
    assert execution.route_metrics["absorbedMassMgPerDay"] == pytest.approx(0.08415, rel=1e-4)
    assert not any(
        q.code == "worker_dermal_permeation_limit_active"
        for q in execution.quality_flags
    )
