from __future__ import annotations

from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.models import (
    AirflowDirectionality,
    InhalationScenarioRequest,
    InhalationTier1ScenarioRequest,
    ParticleSizeRegime,
    PopulationProfile,
    ProductUseProfile,
    Route,
    TierLevel,
)
from exposure_scenario_mcp.worker_tier2 import (
    ExecuteWorkerInhalationTier2Request,
    ExportWorkerArtExecutionPackageRequest,
    ExportWorkerInhalationTier2BridgeRequest,
    ImportWorkerArtExecutionResultRequest,
    WorkerArtArtifactAdapterId,
    WorkerArtExternalArtifact,
    WorkerArtExternalExecutionResult,
    WorkerInhalationTier2AdapterRequest,
    WorkerInhalationTier2ExecutionOverrides,
    WorkerTier2ModelFamily,
    WorkerVentilationContext,
    build_worker_inhalation_tier2_bridge,
    execute_worker_inhalation_tier2_task,
    export_worker_inhalation_art_execution_package,
    import_worker_inhalation_art_execution_result,
    ingest_worker_inhalation_tier2_task,
)


def _base_request() -> InhalationTier1ScenarioRequest:
    return InhalationTier1ScenarioRequest(
        chemical_id="DTXSID123",
        chemical_name="Example Worker Chemical",
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
            air_exchange_rate_per_hour=2.0,
            exposure_duration_hours=0.5,
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
    )


def _base_inhalation_request() -> InhalationScenarioRequest:
    return InhalationScenarioRequest(
        chemical_id="DTXSID123",
        chemical_name="Example Worker Chemical",
        route=Route.INHALATION,
        requested_tier=TierLevel.TIER_0,
        product_use_profile=ProductUseProfile(
            product_category="automotive_maintenance",
            physical_form="liquid",
            application_method="wipe",
            retention_type="surface_contact",
            concentration_fraction=0.8,
            use_amount_per_event=20.0,
            use_amount_unit="mL",
            use_events_per_day=3.0,
            room_volume_m3=80.0,
            air_exchange_rate_per_hour=3.0,
            exposure_duration_hours=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=75.0,
            inhalation_rate_m3_per_hour=1.2,
            demographic_tags=["worker", "occupational"],
            region="EU",
        ),
    )


def test_worker_tier2_bridge_builds_ready_package() -> None:
    package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.compatibility_report.ready_for_adapter is True
    assert package.adapter_request.target_model_family == WorkerTier2ModelFamily.ART
    assert package.tool_call.tool_name == "worker_ingest_inhalation_tier2_task"
    assert package.adapter_request.task_context.ventilation_context == (
        WorkerVentilationContext.GENERAL_VENTILATION
    )
    assert package.adapter_request.supporting_handoffs["workerRoutingDecision"][
        "support_status"
    ] == "future_adapter_recommended"
    assert any(flag.code == "worker_tier2_bridge_export" for flag in package.quality_flags)


def test_worker_tier2_bridge_reports_missing_fields() -> None:
    request = _base_request().model_copy(
        update={
            "population_profile": _base_request().population_profile.model_copy(
                update={"demographic_tags": []}
            ),
            "product_use_profile": _base_request().product_use_profile.model_copy(
                update={"exposure_duration_hours": None}
            ),
        }
    )
    package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=request,
            task_description="Worker inhalation task with incomplete Tier 2 metadata",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.compatibility_report.ready_for_adapter is False
    assert "taskDurationHours" in package.compatibility_report.missing_fields
    assert "ventilationContext" in package.compatibility_report.missing_fields
    assert "workplaceSetting" in package.compatibility_report.missing_fields
    assert "emissionDescriptor" in package.compatibility_report.missing_fields
    assert any(
        item.code == "worker_tier2_task_duration_missing"
        for item in package.compatibility_report.issues
    )
    assert any(flag.code == "worker_context_inferred_or_missing" for flag in package.quality_flags)


def test_worker_art_adapter_ingest_returns_ready_art_envelope() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_adapter_execution is True
    assert result.manual_review_required is False
    assert result.resolved_adapter == "art_worker_inhalation_adapter"
    assert result.art_task_envelope is not None
    assert result.art_task_envelope.activity_class == "trigger_spray_surface_application"
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "janitorial_disinfectant_trigger_spray_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.art_inputs["taskDurationHours"] == 0.5
    assert result.art_task_envelope.art_inputs["templateAlignmentStatus"] == "aligned"
    assert result.art_task_envelope.screening_handoff_summary["workerRoutingSupportStatus"] == (
        "future_adapter_recommended"
    )


def test_worker_art_adapter_ingest_rejects_unsupported_family() -> None:
    request = WorkerInhalationTier2AdapterRequest(
        target_model_family=WorkerTier2ModelFamily.STOFFENMANAGER,
        context_of_use="worker-tier2-bridge",
        chemical_identity={"chemicalId": "DTXSID123", "preferredName": "Example Worker Chemical"},
        task_context=build_worker_inhalation_tier2_bridge(
            ExportWorkerInhalationTier2BridgeRequest(
                base_request=_base_request(),
                task_description="Worker trigger-spray disinfection task",
            ),
            registry=DefaultsRegistry.load(),
        ).adapter_request.task_context,
        exposure_inputs={"applicationMethod": "trigger_spray", "physicalForm": "spray"},
    )

    result = ingest_worker_inhalation_tier2_task(
        request,
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is False
    assert result.ready_for_adapter_execution is False
    assert result.manual_review_required is True
    assert result.resolved_adapter is None
    assert result.art_task_envelope is None
    assert any(
        flag.code == "worker_tier2_adapter_family_unsupported" for flag in result.quality_flags
    )


def test_worker_art_adapter_ingest_marks_partial_template_match_when_subtype_missing() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={"product_category": "pesticide", "product_subtype": None}
                    ),
                    "chemical_name": "Example Worker Pesticide",
                }
            ),
            task_description="Worker pest treatment spray task",
            workplace_setting="treatment room",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short insect treatment spray near the baseboard",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "indoor_surface_pest_control_trigger_spray_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "partial"
    assert result.manual_review_required is True
    assert any(flag.code == "worker_art_template_partial" for flag in result.quality_flags)


def test_worker_art_adapter_ingest_matches_paint_coating_aerosol_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "paint_coating",
                            "application_method": "aerosol_spray",
                        }
                    ),
                    "chemical_name": "Example Worker Coating",
                }
            ),
            task_description="Worker paint booth aerosol coating task",
            workplace_setting="finishing booth",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.LOCAL_EXHAUST,
            local_controls=["local exhaust ventilation"],
            respiratory_protection="half_mask_respirator",
            emission_descriptor="pressurized coating aerosol near the painted surface",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "paint_coating_aerosol_spray_lev_booth_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "pressurized_aerosol_application"
    assert result.art_task_envelope.emission_profile == "pressurized_aerosol_release_profile"


def test_worker_art_adapter_ingest_matches_janitorial_pump_spray_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "household_cleaner",
                            "application_method": "pump_spray",
                        }
                    ),
                    "chemical_name": "Example Worker Surface Cleaner",
                }
            ),
            task_description="Worker janitorial pump-spray surface cleaning task",
            workplace_setting="custodial cart staging area",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="manual pump-spray cleaner mist toward the restroom surface",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "janitorial_cleaner_pump_spray_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "pump_spray_surface_application"
    assert result.art_task_envelope.emission_profile == "liquid_spray_mist_release_profile"


def test_worker_art_adapter_ingest_matches_solvent_vapor_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={
                    "product_use_profile": (
                        _base_inhalation_request().product_use_profile.model_copy(
                            update={"product_category": "automotive_maintenance"}
                        )
                    ),
                    "chemical_name": "Example Worker Degreasing Solvent",
                }
            ),
            task_description="Worker solvent degreasing task at the parts washer",
            workplace_setting="parts washer bay",
            task_duration_hours=1.0,
            ventilation_context=WorkerVentilationContext.LOCAL_EXHAUST,
            local_controls=["local exhaust ventilation"],
            respiratory_protection="none",
            emission_descriptor="volatile degreasing solvent vapor from the open parts washer",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "solvent_degreasing_vapor_task_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "vapor_generating_task"
    assert result.art_task_envelope.emission_profile == "vapor_release_profile"


def test_worker_art_adapter_ingest_matches_open_mixing_vapor_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={
                    "product_use_profile": (
                        _base_inhalation_request().product_use_profile.model_copy(
                            update={
                                "product_category": "adhesive_sealant",
                                "application_method": "hand_application",
                            }
                        )
                    ),
                    "chemical_name": "Example Worker Blend Solvent",
                }
            ),
            task_description="Worker blending solvent-based sealant in an open mixing vessel",
            workplace_setting="batch mixing tank",
            task_duration_hours=1.5,
            ventilation_context=WorkerVentilationContext.LOCAL_EXHAUST,
            local_controls=["local exhaust ventilation"],
            respiratory_protection="none",
            emission_descriptor="volatile vapor above the open blending vessel during mixing",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "open_mixing_blending_vapor_task_controlled_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "vapor_generating_task"
    assert result.art_task_envelope.emission_profile == "vapor_release_profile"


def test_worker_art_adapter_ingest_falls_back_to_broader_paint_template_without_control_context(
) -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "paint_coating",
                            "application_method": "aerosol_spray",
                        }
                    ),
                    "chemical_name": "Example Worker Coating",
                }
            ),
            task_description="Worker paint aerosol coating task",
            workplace_setting="finishing area",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="pressurized coating aerosol near the painted surface",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "paint_coating_aerosol_spray_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"


def test_worker_art_adapter_ingest_falls_back_to_broader_mixing_template_without_control_context(
) -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={
                    "product_use_profile": (
                        _base_inhalation_request().product_use_profile.model_copy(
                            update={
                                "product_category": "adhesive_sealant",
                                "application_method": "hand_application",
                            }
                        )
                    ),
                    "chemical_name": "Example Worker Blend Solvent",
                }
            ),
            task_description="Worker blending solvent-based sealant in an open vessel",
            workplace_setting="batch room",
            task_duration_hours=1.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="volatile vapor above the open blending vessel during mixing",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "open_mixing_blending_vapor_task_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"


def test_worker_art_adapter_ingest_matches_enclosed_pour_transfer_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={
                    "product_use_profile": (
                        _base_inhalation_request().product_use_profile.model_copy(
                            update={
                                "product_category": "adhesive_sealant",
                                "application_method": "pour_transfer",
                            }
                        )
                    ),
                    "chemical_name": "Example Worker Transfer Solvent",
                }
            ),
            task_description="Worker enclosed solvent transfer from drum to sealed charging line",
            workplace_setting="closed charging skid",
            task_duration_hours=1.0,
            ventilation_context=WorkerVentilationContext.ENCLOSED_PROCESS,
            local_controls=["sealed transfer line", "closed lid charging", "hard piped enclosure"],
            respiratory_protection="none",
            emission_descriptor=(
                "volatile vapor at the enclosed charging manifold during pour transfer"
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "enclosed_pour_transfer_vapor_task_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "vapor_generating_task"
    assert result.art_task_envelope.emission_profile == "vapor_release_profile"


def test_worker_art_adapter_ingest_falls_back_from_enclosed_transfer_template_without_enclosure(
) -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={
                    "product_use_profile": (
                        _base_inhalation_request().product_use_profile.model_copy(
                            update={
                                "product_category": "adhesive_sealant",
                                "application_method": "pour_transfer",
                            }
                        )
                    ),
                    "chemical_name": "Example Worker Transfer Solvent",
                }
            ),
            task_description="Worker solvent transfer from drum to vessel",
            workplace_setting="charging station",
            task_duration_hours=1.0,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="volatile vapor at the vessel during pour transfer",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "open_mixing_blending_vapor_task_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"


def test_worker_art_adapter_ingest_matches_enhanced_ventilation_spray_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={"product_category": "maintenance_chemical"}
                    ),
                    "chemical_name": "Example Worker Maintenance Spray",
                }
            ),
            task_description=(
                "Worker trigger-spray maintenance task in a mechanically ventilated bay"
            ),
            workplace_setting="ventilated service bay",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.ENHANCED_GENERAL_VENTILATION,
            local_controls=["enhanced mechanical ventilation", "makeup air supply"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray mist near the service surface",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "generic_worker_spray_mist_enhanced_ventilation_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "trigger_spray_surface_application"
    assert result.art_task_envelope.emission_profile == "liquid_spray_mist_release_profile"


def test_worker_art_adapter_ingest_matches_outdoor_spray_template() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request().model_copy(
                update={
                    "product_use_profile": _base_request().product_use_profile.model_copy(
                        update={
                            "product_category": "maintenance_chemical",
                            "application_method": "pump_spray",
                        }
                    ),
                    "chemical_name": "Example Worker Exterior Cleaner",
                }
            ),
            task_description="Worker outdoor pump-spray washdown task",
            workplace_setting="exterior loading dock",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.OUTDOOR,
            local_controls=["outdoor air dilution"],
            respiratory_protection="none",
            emission_descriptor="manual pump-spray mist around exterior equipment",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = ingest_worker_inhalation_tier2_task(
        bridge_package.tool_call.arguments,
        registry=DefaultsRegistry.load(),
    )

    assert result.art_task_envelope is not None
    assert result.art_task_envelope.determinant_template_match.template_id == (
        "generic_worker_spray_mist_outdoor_v1"
    )
    assert result.art_task_envelope.determinant_template_match.alignment_status.value == "aligned"
    assert result.art_task_envelope.activity_class == "pump_spray_surface_application"
    assert result.art_task_envelope.emission_profile == "liquid_spray_mist_release_profile"


def test_worker_art_execution_returns_control_adjusted_tier1_screening_result() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.LOCAL_EXHAUST,
            local_controls=["local exhaust ventilation"],
            respiratory_protection="half_mask_respirator",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=bridge_package.tool_call.arguments,
            context_of_use="worker-art-execution-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.baseline_dose is not None
    assert result.external_dose is not None
    assert result.route_metrics["baselineModelFamily"] == "tier1_nf_ff_screening"
    assert result.route_metrics["workerControlFactor"] == 0.4
    assert result.route_metrics["respiratoryProtectionFactor"] == 0.1
    assert result.external_dose.value == round(result.baseline_dose.value * 0.04, 8)
    assert result.validation_summary is not None
    assert result.validation_summary.route_mechanism == "worker_inhalation_control_aware_screening"
    assert result.validation_summary.benchmark_case_ids == [
        "worker_inhalation_janitorial_trigger_spray_execution"
    ]
    assert "worker_biocidal_spray_foam_inhalation_2023" in (
        result.validation_summary.external_dataset_ids
    )
    assert any(
        assumption.name == "normalized_worker_inhaled_dose_mg_per_kg_day"
        for assumption in result.assumptions
    )


def test_worker_art_execution_runs_handheld_biocidal_external_anchor_check() -> None:
    study_like_request = _base_request().model_copy(
        update={
            "chemical_id": "DTXSID7020182",
            "chemical_name": "Benzalkonium chloride",
            "product_use_profile": _base_request().product_use_profile.model_copy(
                update={
                    "product_name": "Study-like BAC Spray",
                    "concentration_fraction": 0.0016,
                    "use_amount_per_event": 96.0,
                    "use_events_per_day": 1.0,
                    "room_volume_m3": 300.0,
                    "exposure_duration_hours": 2.0,
                }
            ),
            "source_distance_m": 1.0,
            "spray_duration_seconds": 60.0,
            "near_field_volume_m3": 50.0,
        }
    )
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=study_like_request,
            task_description="Small-scale handheld surface disinfection spray task on a workbench",
            workplace_setting="workbench area",
            task_duration_hours=2.0,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="handheld BAC trigger spray for small-surface disinfection",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=bridge_package.tool_call.arguments,
            execution_overrides=WorkerInhalationTier2ExecutionOverrides(
                control_factor=1.0,
                respiratory_protection_factor=1.0,
            ),
            context_of_use="worker-art-execution-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.validation_summary is not None
    assert result.validation_summary.benchmark_case_ids == [
        "worker_inhalation_handheld_biocidal_trigger_spray_execution"
    ]
    assert result.validation_summary.evidence_readiness.value == "external_partial"
    check_ids = {item.check_id for item in result.validation_summary.executed_validation_checks}
    assert "worker_biocidal_handheld_trigger_spray_concentration_2023" in check_ids
    assert all(
        item.status.value == "pass" for item in result.validation_summary.executed_validation_checks
    )


def test_worker_art_execution_uses_room_average_vapor_surrogate_for_non_spray_task() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_inhalation_request().model_copy(
                update={"chemical_name": "Example Worker Degreasing Solvent"}
            ),
            task_description="Worker solvent degreasing task at the parts washer",
            workplace_setting="parts washer bay",
            task_duration_hours=1.0,
            ventilation_context=WorkerVentilationContext.LOCAL_EXHAUST,
            local_controls=["local exhaust ventilation"],
            respiratory_protection="none",
            emission_descriptor="volatile degreasing solvent vapor from the open parts washer",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = execute_worker_inhalation_tier2_task(
        ExecuteWorkerInhalationTier2Request(
            adapter_request=bridge_package.tool_call.arguments,
            execution_overrides=WorkerInhalationTier2ExecutionOverrides(
                vapor_release_fraction=0.05
            ),
            context_of_use="worker-art-execution-test",
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.manual_review_required is True
    assert result.baseline_dose is not None
    assert result.external_dose is not None
    assert result.route_metrics["baselineModelFamily"] == "room_average_vapor_release_surrogate"
    assert result.route_metrics["workerControlFactor"] == 0.4
    assert result.route_metrics["respiratoryProtectionFactor"] == 1.0
    assert result.external_dose.value == round(result.baseline_dose.value * 0.4, 8)
    assert result.validation_summary is not None
    assert result.validation_summary.executed_validation_checks == []
    assert any(
        item.code == "worker_art_execution_vapor_surrogate" for item in result.limitations
    )


def test_worker_art_external_execution_package_exports_ready_payload() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    package = export_worker_inhalation_art_execution_package(
        ExportWorkerArtExecutionPackageRequest(
            adapter_request=bridge_package.tool_call.arguments,
        ),
        registry=DefaultsRegistry.load(),
    )

    assert package.ready_for_external_execution is True
    assert package.art_task_envelope is not None
    assert package.external_execution_payload["schemaVersion"] == (
        "workerArtExternalExecutionPayload.v1"
    )
    assert package.external_execution_payload["artInputs"]["templateId"] == (
        "janitorial_disinfectant_trigger_spray_v1"
    )
    assert package.result_import_tool_call.tool_name == (
        "worker_import_inhalation_art_execution_result"
    )


def test_worker_art_external_result_import_returns_tier2_execution_result() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                source_run_id="art-run-001",
                model_version="ART-1.5.0",
                result_status="completed",
                breathing_zone_concentration_mg_per_m3=0.72,
                inhaled_mass_mg_per_day=1.575,
                normalized_external_dose_mg_per_kg_day=0.021,
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART run summary",
                        locator="artifact://art-run-001/summary.json",
                        media_type="application/json",
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.manual_review_required is False
    assert result.resolved_adapter == "art_worker_inhalation_external_adapter"
    assert result.baseline_dose is not None
    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.tier_semantics.tier_earned.value == "tier_2"
    assert result.route_metrics["importedSourceSystem"] == "ART"
    assert result.route_metrics["externalRunId"] == "art-run-001"
    assert result.route_metrics["importedDoseDerivationMethod"] == (
        "explicit_normalized_external_dose"
    )
    assert result.validation_summary is not None
    assert result.validation_summary.route_mechanism == "worker_inhalation_external_art_import"
    assert result.validation_summary.external_dataset_ids == ["ART:art-run-001"]


def test_worker_art_external_result_import_uses_structured_result_payload() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                result_payload={
                    "schemaVersion": "workerArtExternalResultSummary.v1",
                    "sourceRunId": "art-run-payload-001",
                    "modelVersion": "ART-1.5.0",
                    "resultStatus": "completed",
                    "taskDurationHours": 0.5,
                    "breathingZoneConcentrationMgPerM3": 0.72,
                    "inhaledMassMgPerDay": 1.575,
                    "normalizedExternalDoseMgPerKgDay": 0.021,
                    "determinantSnapshot": {
                        "templateId": "janitorial_disinfectant_trigger_spray_v1"
                    },
                },
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.manual_review_required is False
    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["externalRunId"] == "art-run-payload-001"
    assert result.route_metrics["importedResultPayloadUsed"] is True
    assert result.route_metrics["importedResultPayloadSchemaVersion"] == (
        "workerArtExternalResultSummary.v1"
    )
    assert result.route_metrics["importedDoseDerivationMethod"] == (
        "explicit_normalized_external_dose"
    )
    assert any(
        flag.code == "worker_art_external_result_payload_present"
        for flag in result.quality_flags
    )
    assert any(
        flag.code == "worker_art_external_result_payload_without_raw_artifacts"
        for flag in result.quality_flags
    )


def test_worker_art_external_result_import_uses_inline_artifact_payload() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART run summary",
                        locator="artifact://art-run-inline-001/summary.json",
                        media_type="application/json",
                        content_json={
                            "schemaVersion": "workerArtExternalResultSummary.v1",
                            "sourceRunId": "art-run-inline-001",
                            "modelVersion": "ART-1.5.0",
                            "resultStatus": "completed",
                            "taskDurationHours": 0.5,
                            "breathingZoneConcentrationMgPerM3": 0.72,
                            "inhaledMassMgPerDay": 1.575,
                            "normalizedExternalDoseMgPerKgDay": 0.021,
                            "determinantSnapshot": {
                                "templateId": "janitorial_disinfectant_trigger_spray_v1"
                            },
                        },
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.manual_review_required is False
    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["externalRunId"] == "art-run-inline-001"
    assert result.route_metrics["importedArtifactPayloadUsed"] is True
    assert result.route_metrics["importedResultPayloadUsed"] is True
    assert result.route_metrics["importedResultPayloadSchemaVersion"] == (
        "workerArtExternalResultSummary.v1"
    )
    assert result.route_metrics["artifactFormatAdapterId"] == "art_worker_result_summary_json_v1"
    assert any(
        flag.code == "worker_art_external_result_artifact_payload_present"
        for flag in result.quality_flags
    )
    assert any(
        flag.code == "worker_art_external_result_artifact_payload_used_without_explicit_summary"
        for flag in result.quality_flags
    )


def test_worker_art_external_result_import_uses_csv_artifact_payload() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART CSV run summary",
                        locator="artifact://art-run-csv-001/summary.csv",
                        media_type="text/csv",
                        content_text=(
                            "schemaVersion,sourceRunId,modelVersion,resultStatus,"
                            "taskDurationHours,breathingZoneConcentrationMgPerM3,"
                            "inhaledMassMgPerDay,normalizedExternalDoseMgPerKgDay\n"
                            "workerArtExternalResultSummary.v1,art-run-csv-001,ART-1.5.0,"
                            "completed,0.5,0.72,1.575,0.021\n"
                        ),
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.supported_by_adapter is True
    assert result.ready_for_execution is True
    assert result.manual_review_required is False
    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["externalRunId"] == "art-run-csv-001"
    assert result.route_metrics["importedArtifactPayloadUsed"] is True
    assert result.route_metrics["importedResultPayloadSchemaVersion"] == (
        "workerArtExternalResultSummary.v1"
    )
    assert result.route_metrics["artifactFormatAdapterId"] == (
        "art_worker_result_summary_csv_wide_v1"
    )
    assert any(
        flag.code == "worker_art_external_result_artifact_payload_present"
        for flag in result.quality_flags
    )


def test_worker_art_external_result_import_uses_execution_report_adapter() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART runner execution report",
                        locator="artifact://art-run-report-001/report.json",
                        media_type="application/json",
                        adapter_hint=WorkerArtArtifactAdapterId.EXECUTION_REPORT_JSON_V1,
                        content_json={
                            "schemaVersion": "artWorkerExecutionReport.v1",
                            "run": {
                                "id": "art-run-report-001",
                                "modelVersion": "ART-1.5.0",
                            },
                            "task": {"durationHours": 0.5},
                            "results": {
                                "status": "completed",
                                "breathingZoneConcentrationMgPerM3": 0.72,
                                "inhaledMassMgPerDay": 1.575,
                                "normalizedExternalDoseMgPerKgDay": 0.021,
                            },
                            "determinants": {
                                "templateId": "janitorial_disinfectant_trigger_spray_v1"
                            },
                        },
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["artifactFormatAdapterId"] == (
        "art_worker_execution_report_json_v1"
    )
    assert result.route_metrics["importedDeterminantSnapshot"] == {
        "templateId": "janitorial_disinfectant_trigger_spray_v1"
    }


def test_worker_art_external_result_import_uses_key_value_csv_adapter() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART key-value summary",
                        locator="artifact://art-run-kv-001/summary.csv",
                        media_type="text/csv",
                        adapter_hint=WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_KEY_VALUE_V1,
                        content_text=(
                            "key,value\n"
                            "schemaVersion,workerArtExternalResultSummary.v1\n"
                            "sourceRunId,art-run-kv-001\n"
                            "modelVersion,ART-1.5.0\n"
                            "resultStatus,completed\n"
                            "breathingZoneConcentrationMgPerM3,0.72\n"
                            "inhaledMassMgPerDay,1.575\n"
                            "normalizedExternalDoseMgPerKgDay,0.021\n"
                        ),
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["artifactFormatAdapterId"] == (
        "art_worker_result_summary_csv_key_value_v1"
    )
    assert result.route_metrics["externalRunId"] == "art-run-kv-001"


def test_worker_art_external_result_import_uses_semicolon_csv_adapter() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART semicolon CSV summary",
                        locator="artifact://art-run-semi-001/summary.csv",
                        media_type="text/csv",
                        adapter_hint=WorkerArtArtifactAdapterId.RESULT_SUMMARY_CSV_SEMICOLON_V1,
                        content_text=(
                            "schemaVersion;sourceRunId;modelVersion;resultStatus;"
                            "taskDurationHours;breathingZoneConcentrationMgPerM3;"
                            "inhaledMassMgPerDay;normalizedExternalDoseMgPerKgDay\n"
                            "workerArtExternalResultSummary.v1;art-run-semi-001;ART-1.5.0;"
                            "completed;0.5;0.72;1.575;0.021\n"
                        ),
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.external_dose is not None
    assert result.external_dose.value == 0.021
    assert result.route_metrics["artifactFormatAdapterId"] == (
        "art_worker_result_summary_csv_semicolon_v1"
    )
    assert result.route_metrics["externalRunId"] == "art-run-semi-001"


def test_worker_art_external_result_import_flags_payload_metric_mismatch() -> None:
    bridge_package = build_worker_inhalation_tier2_bridge(
        ExportWorkerInhalationTier2BridgeRequest(
            base_request=_base_request(),
            target_model_family=WorkerTier2ModelFamily.ART,
            task_description="Worker trigger-spray disinfection task",
            workplace_setting="janitorial closet",
            task_duration_hours=0.5,
            ventilation_context=WorkerVentilationContext.GENERAL_VENTILATION,
            local_controls=["general ventilation"],
            respiratory_protection="none",
            emission_descriptor="short trigger-spray cleaning mist near the breathing zone",
        ),
        registry=DefaultsRegistry.load(),
    )

    result = import_worker_inhalation_art_execution_result(
        ImportWorkerArtExecutionResultRequest(
            adapter_request=bridge_package.tool_call.arguments,
            external_result=WorkerArtExternalExecutionResult(
                source_system="ART",
                source_run_id="art-run-002",
                result_status="completed",
                breathing_zone_concentration_mg_per_m3=0.72,
                normalized_external_dose_mg_per_kg_day=0.021,
                result_payload={
                    "schemaVersion": "workerArtExternalResultSummary.v1",
                    "sourceRunId": "art-run-002",
                    "resultStatus": "completed",
                    "breathingZoneConcentrationMgPerM3": 0.9,
                    "normalizedExternalDoseMgPerKgDay": 0.03,
                },
                raw_artifacts=[
                    WorkerArtExternalArtifact(
                        label="ART result payload",
                        locator="artifact://art-run-002/result.json",
                        media_type="application/json",
                    )
                ],
            ),
        ),
        registry=DefaultsRegistry.load(),
    )

    assert result.ready_for_execution is True
    assert result.manual_review_required is True
    assert any(
        flag.code == "worker_art_external_result_payload_concentration_mismatch"
        for flag in result.quality_flags
    )
    assert any(
        flag.code == "worker_art_external_result_payload_dose_mismatch"
        for flag in result.quality_flags
    )
