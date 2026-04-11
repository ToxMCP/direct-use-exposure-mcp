from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    ExposureScenarioRequest,
    PhyschemContext,
    PopulationProfile,
    ProductAmountUnit,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.worker_dermal import (
    ExecuteWorkerDermalAbsorbedDoseRequest,
    ExportWorkerDermalAbsorbedDoseBridgeRequest,
    WorkerDermalAbsorbedDoseExecutionOverrides,
    WorkerDermalBarrierMaterial,
    WorkerDermalChemicalContext,
    WorkerDermalContactPattern,
    WorkerDermalModelFamily,
    WorkerDermalPpeState,
    WorkerSkinCondition,
    build_worker_dermal_absorbed_dose_bridge,
    execute_worker_dermal_absorbed_dose_task,
    ingest_worker_dermal_absorbed_dose_task,
)


def _base_request() -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="DTXSID123",
        chemical_name="Example Worker Chemical",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="liquid",
            application_method="wipe",
            retention_type="surface_contact",
            concentration_fraction=0.02,
            use_amount_per_event=10.0,
            use_amount_unit="g",
            use_events_per_day=3.0,
            exposure_duration_hours=0.75,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=75.0,
            exposed_surface_area_cm2=840.0,
            demographic_tags=["worker", "occupational"],
            region="EU",
        ),
    )


def test_worker_dermal_bridge_builds_ready_package() -> None:
    package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request(),
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.compatibility_report.ready_for_adapter is True
    assert package.adapter_request.target_model_family == (
        WorkerDermalModelFamily.DERMAL_ABSORPTION_PPE
    )
    assert package.tool_call.tool_name == "worker_ingest_dermal_absorbed_dose_task"
    assert package.adapter_request.task_context.contact_pattern == (
        WorkerDermalContactPattern.SURFACE_TRANSFER
    )
    assert package.adapter_request.supporting_handoffs["workerRoutingDecision"][
        "support_status"
    ] == "future_adapter_recommended"
    assert any(flag.code == "worker_dermal_bridge_export" for flag in package.quality_flags)


def test_worker_dermal_bridge_promotes_shared_physchem_context() -> None:
    package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "physchem_context": PhyschemContext(
                        vapor_pressure_mmhg=8.0,
                        molecular_weight_g_per_mol=120.15,
                        log_kow=2.1,
                        water_solubility_mg_per_l=950.0,
                    )
                }
            ),
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.adapter_request.chemical_context is not None
    assert package.adapter_request.chemical_context.vapor_pressure_mmhg == 8.0
    assert package.adapter_request.chemical_context.molecular_weight_g_per_mol == 120.15
    assert package.adapter_request.chemical_context.log_kow == 2.1
    assert package.adapter_request.chemical_context.water_solubility_mg_per_l == 950.0
    assert any(
        flag.code == "worker_dermal_physchem_context_from_base_request"
        for flag in package.quality_flags
    )


def test_worker_dermal_bridge_reports_missing_fields() -> None:
    package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={"exposure_duration_hours": None}
                    )
                }
            ),
            task_description="Worker dermal task with incomplete absorbed-dose metadata",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.compatibility_report.ready_for_adapter is False
    assert "contactDurationHours" in package.compatibility_report.missing_fields
    assert "contactPattern" in package.compatibility_report.missing_fields
    assert "exposedBodyAreas" in package.compatibility_report.missing_fields
    assert "ppeState" in package.compatibility_report.missing_fields
    assert "surfaceLoadingContext" in package.compatibility_report.missing_fields
    assert any(
        item.code == "worker_dermal_contact_pattern_missing"
        for item in package.compatibility_report.issues
    )


def test_worker_dermal_adapter_ingest_matches_janitorial_template() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request(),
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_dermal_absorbed_dose_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_adapter_execution is True
    assert result.manual_review_required is False
    assert result.resolved_adapter == "worker_dermal_absorption_ppe_adapter"
    assert result.dermal_task_envelope is not None
    assert result.dermal_task_envelope.determinant_template_match.template_id == (
        "janitorial_wet_wipe_gloved_hands_v1"
    )
    assert result.dermal_task_envelope.determinant_template_match.alignment_status.value == (
        "aligned"
    )
    assert result.dermal_task_envelope.contact_profile == "surface_transfer_contact_profile"
    assert result.dermal_task_envelope.ppe_profile == "general_work_glove_barrier_profile"


def test_worker_dermal_adapter_ingest_matches_solvent_transfer_template() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "automotive_maintenance",
                            "application_method": "pour_transfer",
                        }
                    ),
                    "chemical_name": "Example Worker Degreasing Solvent",
                }
            ),
            task_description="Worker solvent transfer from drum to parts washer",
            workplace_setting="parts washer bay",
            contact_duration_hours=0.5,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            control_measures=["closed transfer connection"],
            surface_loading_context="direct liquid contact during solvent transfer",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_dermal_absorbed_dose_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.dermal_task_envelope is not None
    assert result.dermal_task_envelope.determinant_template_match.template_id == (
        "solvent_transfer_gloved_hands_v1"
    )
    assert result.dermal_task_envelope.determinant_template_match.alignment_status.value == (
        "aligned"
    )
    assert result.dermal_task_envelope.contact_profile == "direct_handling_contact_profile"
    assert result.dermal_task_envelope.ppe_profile == (
        "chemical_resistant_glove_barrier_profile"
    )


def test_worker_dermal_adapter_ingest_uses_generic_ungloved_template() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={"product_category": "maintenance_chemical"}
                    ),
                    "chemical_name": "Example Worker Maintenance Cleaner",
                }
            ),
            task_description="Worker direct hand contact with maintenance residue",
            workplace_setting="service bay",
            contact_duration_hours=0.25,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.NONE,
            control_measures=["prompt hand washing"],
            surface_loading_context="residual liquid contact during manual handling",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_dermal_absorbed_dose_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.dermal_task_envelope is not None
    assert result.dermal_task_envelope.determinant_template_match.template_id == (
        "generic_ungloved_hand_contact_v1"
    )
    assert result.dermal_task_envelope.determinant_template_match.alignment_status.value == (
        "heuristic"
    )
    assert result.manual_review_required is True


def test_worker_dermal_adapter_ingest_rejects_unsupported_family() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerDermalModelFamily.IH_SKINPERM,
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_dermal_absorbed_dose_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is False
    assert result.ready_for_adapter_execution is False
    assert result.manual_review_required is True
    assert result.resolved_adapter is None
    assert result.dermal_task_envelope is None
    assert any(
        flag.code == "worker_dermal_adapter_family_unsupported"
        for flag in result.quality_flags
    )


def test_worker_dermal_execution_returns_ppe_adjusted_absorbed_dose() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request(),
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.external_dose is not None
    assert result.absorbed_dose is not None
    assert result.external_dose.value == 0.8
    assert result.absorbed_dose.value == 0.0144
    assert result.route_metrics["ppePenetrationFactor"] == 0.4
    assert result.route_metrics["dermalAbsorptionFraction"] == 0.045
    assert result.validation_summary is not None
    assert result.validation_summary.route_mechanism == "worker_dermal_absorbed_dose_screening"
    assert result.validation_summary.benchmark_case_ids == [
        "worker_dermal_wet_wipe_gloved_hands_execution"
    ]
    assert result.validation_summary.evidence_readiness.value == (
        "benchmark_plus_external_candidates"
    )
    assert "rivm_wet_cloth_dermal_contact_loading_2018" in (
        result.validation_summary.external_dataset_ids
    )
    assert any(
        assumption.name == "normalized_absorbed_dose_mg_per_kg_day"
        for assumption in result.assumptions
    )


def test_worker_dermal_execution_runs_handheld_biocidal_external_anchor_check() -> None:
    study_like_request = _base_request().model_copy(
        update={
            "chemical_id": "DTXSID7020182",
            "chemical_name": "Benzalkonium chloride",
            "product_use_profile": _base_request().product_use_profile.model_copy(
                update={
                    "product_name": "Study-like BAC Surface Spray",
                    "product_category": "disinfectant",
                    "physical_form": "spray",
                    "application_method": "trigger_spray",
                    "concentration_fraction": 0.0016,
                    "use_amount_per_event": 40.0,
                    "use_amount_unit": ProductAmountUnit.G,
                    "use_events_per_day": 1.0,
                    "exposure_duration_hours": 1.0,
                }
            ),
        }
    )
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=study_like_request,
            task_description="Small-scale handheld BAC spray contact during workbench disinfection",
            workplace_setting="workbench area",
            contact_duration_hours=1.0,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["general ventilation"],
            surface_loading_context="spray-and-wipe surface transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.validation_summary is not None
    assert result.validation_summary.benchmark_case_ids == [
        "worker_dermal_handheld_biocidal_trigger_spray_execution"
    ]
    assert result.validation_summary.evidence_readiness.value == "external_partial"
    assert "worker_biocidal_spray_foam_dermal_2023" in (
        result.validation_summary.external_dataset_ids
    )
    check_ids = {item.check_id for item in result.validation_summary.executed_validation_checks}
    assert "worker_biocidal_handheld_trigger_spray_dermal_mass_2023" in check_ids
    assert all(
        item.status.value == "pass" for item in result.validation_summary.executed_validation_checks
    )


def test_worker_dermal_execution_honors_explicit_overrides() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request(),
            task_description="Worker wet-wipe cleaning task with gloved hand contact",
            workplace_setting="custodial closet",
            contact_duration_hours=0.75,
            contact_pattern=WorkerDermalContactPattern.SURFACE_TRANSFER,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.WORK_GLOVES,
            control_measures=["task segregation"],
            surface_loading_context="wet cleaning cloth transfer to gloved hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            execution_overrides=WorkerDermalAbsorbedDoseExecutionOverrides(
                external_skin_mass_mg_per_day=0.6,
                ppe_penetration_factor=0.2,
                dermal_absorption_fraction=0.3,
            ),
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.external_dose is not None
    assert result.absorbed_dose is not None
    assert result.external_dose.value == 0.008
    assert result.absorbed_dose.value == 0.00048
    assert result.route_metrics["externalSkinMassMgPerDay"] == 0.6
    assert result.route_metrics["ppePenetrationFactor"] == 0.2
    assert result.route_metrics["dermalAbsorptionFraction"] == 0.3
    assert result.validation_summary is not None
    assert result.validation_summary.executed_validation_checks == []
    assert any(
        assumption.name == "external_skin_mass_mg_per_day"
        and assumption.source_kind.value == "user_input"
        for assumption in result.assumptions
    )


def test_worker_dermal_execution_applies_barrier_material_and_chemical_context_modifiers() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "chemical_name": "Example Worker Degreasing Solvent",
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "automotive_maintenance",
                            "application_method": "pour_transfer",
                            "concentration_fraction": 0.05,
                            "use_amount_per_event": 5.0,
                            "use_events_per_day": 2.0,
                            "exposure_duration_hours": 0.5,
                        }
                    ),
                }
            ),
            task_description="Worker solvent transfer with nitrile glove contact",
            workplace_setting="parts washer bay",
            contact_duration_hours=0.5,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            barrier_material=WorkerDermalBarrierMaterial.NITRILE,
            control_measures=["closed transfer connection"],
            surface_loading_context="direct liquid contact during solvent transfer",
            skin_condition=WorkerSkinCondition.INTACT,
            chemical_context=WorkerDermalChemicalContext(
                log_kow=3.0,
                molecular_weight_g_per_mol=250.0,
                water_solubility_mg_per_l=20000.0,
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.external_dose is not None
    assert result.absorbed_dose is not None
    assert result.external_dose.value == 1.2
    assert result.absorbed_dose.value == 0.00512325
    assert result.chemical_context is not None
    assert result.route_metrics["externalSkinMassMgPerDay"] == 90.0
    assert result.route_metrics["basePpePenetrationFactor"] == 0.1
    assert result.route_metrics["barrierMaterial"] == "nitrile"
    assert result.route_metrics["barrierMaterialFactor"] == 0.75
    assert result.route_metrics["barrierChemistryProfile"] == "mixed_organic"
    assert result.route_metrics["barrierChemistryFactor"] == 0.9
    assert result.route_metrics["barrierBreakthroughProfile"] == "mixed_organic"
    assert result.route_metrics["barrierBreakthroughLagHours"] == 0.25
    assert result.route_metrics["barrierBreakthroughTransitionHours"] == 0.25
    assert result.route_metrics["barrierBreakthroughFraction"] == 1.0
    assert result.route_metrics["ppePenetrationFactor"] == 0.0675
    assert result.route_metrics["baseDermalAbsorptionFraction"] == 0.1
    assert result.route_metrics["contactPatternFactor"] == 1.0
    assert result.route_metrics["contactDurationFactor"] == 0.5
    assert result.route_metrics["skinConditionFactor"] == 1.0
    assert result.route_metrics["chemicalContextFactor"] == 1.265
    assert result.route_metrics["logKow"] == 3.0
    assert result.route_metrics["logKowFactor"] == 1.15
    assert result.route_metrics["molecularWeightGPerMol"] == 250.0
    assert result.route_metrics["molecularWeightFactor"] == 1.0
    assert result.route_metrics["waterSolubilityMgPerL"] == 20000.0
    assert result.route_metrics["waterSolubilityFactor"] == 1.1
    assert result.route_metrics["dermalAbsorptionFraction"] == 0.06325
    assert any(
        limitation.code == "worker_dermal_execution_bounded_physchem_absorption"
        for limitation in result.limitations
    )
    assert any(
        limitation.code == "worker_dermal_execution_bounded_barrier_material"
        for limitation in result.limitations
    )


def test_worker_dermal_execution_applies_vapor_pressure_modifier() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "chemical_name": "Example Worker Degreasing Solvent",
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "automotive_maintenance",
                            "application_method": "pour_transfer",
                            "concentration_fraction": 0.05,
                            "use_amount_per_event": 5.0,
                            "use_events_per_day": 2.0,
                            "exposure_duration_hours": 0.5,
                        }
                    ),
                }
            ),
            task_description="Worker solvent transfer with nitrile glove contact",
            workplace_setting="parts washer bay",
            contact_duration_hours=0.5,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            barrier_material=WorkerDermalBarrierMaterial.NITRILE,
            control_measures=["closed transfer connection"],
            surface_loading_context="direct liquid contact during solvent transfer",
            skin_condition=WorkerSkinCondition.INTACT,
            chemical_context=WorkerDermalChemicalContext(
                log_kow=3.0,
                molecular_weight_g_per_mol=250.0,
                water_solubility_mg_per_l=20000.0,
                vapor_pressure_mmhg=15.0,
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.absorbed_dose is not None
    assert result.absorbed_dose.value == 0.00435476
    assert result.route_metrics["vaporPressureMmhg"] == 15.0
    assert result.route_metrics["vaporPressureFactor"] == 0.85
    assert result.route_metrics["evaporationCompetitionFactor"] == 0.85
    assert result.route_metrics["evaporationRatePerHour"] == 0.32503786
    assert result.route_metrics["chemicalContextFactor"] == 1.265
    assert result.route_metrics["dermalAbsorptionFraction"] == 0.0537625


def test_worker_dermal_execution_caps_surface_loading_and_reports_runoff() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "application_method": "hand_application",
                            "use_amount_per_event": 500.0,
                            "use_events_per_day": 1.0,
                        }
                    )
                }
            ),
            task_description="Worker direct liquid handling with heavy splash loading",
            workplace_setting="mix room",
            contact_duration_hours=1.0,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.NONE,
            control_measures=["prompt hand washing"],
            surface_loading_context="high liquid contact on hands",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.route_metrics["externalSkinMassMgPerDay"] == 2000.0
    assert result.route_metrics["surfaceLoadingMgPerCm2Day"] == 2.38095238
    assert result.route_metrics["maxRetainedLoadingMgPerCm2Day"] == 2.0
    assert result.route_metrics["retainedExternalSkinMassMgPerDay"] == 1680.0
    assert result.route_metrics["retainedSurfaceLoadingMgPerCm2Day"] == 2.0
    assert result.route_metrics["runoffMassMgPerDay"] == 320.0
    assert result.route_metrics["runoffFraction"] == 0.16
    assert result.route_metrics["surfaceLoadingCapApplied"] is True
    assert any(
        flag.code == "worker_dermal_surface_loading_cap_applied"
        for flag in result.quality_flags
    )
    assert any(
        limitation.code == "worker_dermal_execution_surface_loading_cap"
        for limitation in result.limitations
    )


def test_worker_dermal_execution_applies_breakthrough_lag_for_short_contact() -> None:
    bridge_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={"exposure_duration_hours": 0.1}
                    )
                }
            ),
            task_description="Short worker solvent transfer with nitrile glove contact",
            workplace_setting="parts washer bay",
            contact_duration_hours=0.1,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            barrier_material=WorkerDermalBarrierMaterial.NITRILE,
            control_measures=["closed transfer connection"],
            surface_loading_context="brief liquid contact during solvent transfer",
            skin_condition=WorkerSkinCondition.INTACT,
            chemical_context=WorkerDermalChemicalContext(
                log_kow=3.0,
                molecular_weight_g_per_mol=250.0,
                water_solubility_mg_per_l=20000.0,
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.absorbed_dose is not None
    assert result.absorbed_dose.value == 0.0
    assert result.route_metrics["barrierBreakthroughLagHours"] == 0.25
    assert result.route_metrics["barrierBreakthroughTransitionHours"] == 0.25
    assert result.route_metrics["barrierBreakthroughFraction"] == 0.0
    assert result.route_metrics["ppePenetrationFactor"] == 0.0
    assert any(
        flag.code == "worker_dermal_breakthrough_lag_applied"
        for flag in result.quality_flags
    )
    assert any(
        limitation.code == "worker_dermal_execution_bounded_breakthrough_timing"
        for limitation in result.limitations
    )


def test_worker_dermal_execution_applies_duration_aware_evaporation_competition() -> None:
    short_contact_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "automotive_maintenance",
                            "application_method": "pour_transfer",
                            "concentration_fraction": 0.05,
                            "use_amount_per_event": 5.0,
                            "use_events_per_day": 2.0,
                            "exposure_duration_hours": 0.5,
                        }
                    )
                }
            ),
            task_description="Worker solvent transfer with volatile liquid contact",
            workplace_setting="parts washer bay",
            contact_duration_hours=0.5,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            barrier_material=WorkerDermalBarrierMaterial.NITRILE,
            control_measures=["closed transfer connection"],
            surface_loading_context="direct liquid contact during solvent transfer",
            skin_condition=WorkerSkinCondition.INTACT,
            chemical_context=WorkerDermalChemicalContext(
                log_kow=3.0,
                molecular_weight_g_per_mol=250.0,
                water_solubility_mg_per_l=20000.0,
                vapor_pressure_mmhg=150.0,
            ),
        ),
        registry=DefaultsRegistry.load(),
    )
    long_contact_package = build_worker_dermal_absorbed_dose_bridge(
        ExportWorkerDermalAbsorbedDoseBridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "automotive_maintenance",
                            "application_method": "pour_transfer",
                            "concentration_fraction": 0.05,
                            "use_amount_per_event": 5.0,
                            "use_events_per_day": 2.0,
                            "exposure_duration_hours": 4.0,
                        }
                    )
                }
            ),
            task_description="Worker solvent transfer with prolonged volatile liquid contact",
            workplace_setting="parts washer bay",
            contact_duration_hours=4.0,
            contact_pattern=WorkerDermalContactPattern.DIRECT_HANDLING,
            exposed_body_areas=["hands"],
            ppe_state=WorkerDermalPpeState.CHEMICAL_RESISTANT_GLOVES,
            barrier_material=WorkerDermalBarrierMaterial.NITRILE,
            control_measures=["closed transfer connection"],
            surface_loading_context="direct liquid contact during solvent transfer",
            skin_condition=WorkerSkinCondition.INTACT,
            chemical_context=WorkerDermalChemicalContext(
                log_kow=3.0,
                molecular_weight_g_per_mol=250.0,
                water_solubility_mg_per_l=20000.0,
                vapor_pressure_mmhg=150.0,
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    short_result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=short_contact_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )
    long_result = execute_worker_dermal_absorbed_dose_task(
        ExecuteWorkerDermalAbsorbedDoseRequest(
            adapter_request=long_contact_package.tool_call.arguments,
            context_of_use="worker-dermal-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert short_result.absorbed_dose is not None
    assert long_result.absorbed_dose is not None
    assert short_result.route_metrics["evaporationRatePerHour"] == 0.71334989
    assert long_result.route_metrics["evaporationRatePerHour"] == 0.71334989
    assert short_result.route_metrics["evaporationCompetitionFactor"] == 0.7
    assert long_result.route_metrics["evaporationCompetitionFactor"] < 0.1
    assert long_result.absorbed_dose.value < short_result.absorbed_dose.value
    assert any(
        limitation.code == "worker_dermal_execution_bounded_evaporation_competition"
        for limitation in long_result.limitations
    )
