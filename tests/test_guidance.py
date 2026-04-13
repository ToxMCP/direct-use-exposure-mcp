from __future__ import annotations

from pathlib import Path

from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.guidance import (
    archetype_library_guide,
    capability_maturity_matrix_guide,
    conformance_report_markdown,
    cross_mcp_contract_guide,
    defaults_curation_report_markdown,
    exposure_platform_architecture_guide,
    goldset_benchmark_guide,
    herbal_medicinal_routing_guide,
    inhalation_residual_air_reentry_guide,
    inhalation_tier_upgrade_guide,
    integrated_exposure_workflow_guide,
    probability_bounds_guide,
    release_notes_markdown,
    release_readiness_markdown,
    repository_slug_decision_guide,
    service_selection_guide,
    tier1_inhalation_parameter_guide,
    toxmcp_suite_index_guide,
    uncertainty_framework,
    validation_coverage_report_markdown,
    validation_dossier_markdown,
    validation_framework,
    validation_reference_bands_guide,
    validation_time_series_packs_guide,
    verification_summary_guide,
    worker_art_adapter_guide,
    worker_art_execution_guide,
    worker_art_external_exchange_guide,
    worker_dermal_adapter_guide,
    worker_dermal_bridge_guide,
    worker_dermal_execution_guide,
    worker_routing_guide,
    worker_tier2_bridge_guide,
)


def test_release_guidance_mentions_current_benchmark_matrix() -> None:
    registry = DefaultsRegistry.load()
    metadata = build_release_metadata_report(registry)
    readiness = build_release_readiness_report(registry)
    security_review = build_security_provenance_review_report(registry)

    release_notes = release_notes_markdown(metadata)
    readiness_markdown = release_readiness_markdown(readiness)
    conformance = conformance_report_markdown(metadata, readiness, security_review)

    assert "Benchmark Matrix" in release_notes
    assert "Benchmark Matrix" in readiness_markdown
    assert "`dermal_pbpk_external_import_package`" in release_notes
    assert "`dermal_pbpk_external_import_package`" in readiness_markdown
    assert f"Benchmark cases published: `{metadata.benchmark_case_count}`" in conformance
    assert "`dermal_pbpk_external_import_package`" in conformance


def test_published_release_notes_match_generated_markdown() -> None:
    registry = DefaultsRegistry.load()
    metadata = build_release_metadata_report(registry)
    published_path = Path(__file__).resolve().parents[1] / "docs" / "releases" / "v0.1.0.md"
    published = published_path.read_text()
    expected = release_notes_markdown(metadata).rstrip() + "\n"
    assert published == expected


def test_uncertainty_and_validation_guidance_expose_tier_a_b_posture() -> None:
    uncertainty = uncertainty_framework()
    validation = validation_framework()
    dossier = validation_dossier_markdown()
    coverage_report = validation_coverage_report_markdown()
    goldset = goldset_benchmark_guide()
    defaults_curation = defaults_curation_report_markdown()
    archetypes = archetype_library_guide()
    inhalation_tier_guide = inhalation_tier_upgrade_guide()
    tier1_parameter_guide = tier1_inhalation_parameter_guide()
    inhalation_reentry_guide = inhalation_residual_air_reentry_guide()
    probability_bounds = probability_bounds_guide()
    architecture = exposure_platform_architecture_guide()
    validation_bands = validation_reference_bands_guide()
    validation_time_series = validation_time_series_packs_guide()
    verification_summary = verification_summary_guide()
    capability_matrix = capability_maturity_matrix_guide()
    slug_decision = repository_slug_decision_guide()
    cross_mcp_contracts = cross_mcp_contract_guide()
    service_selection = service_selection_guide()
    herbal_routing = herbal_medicinal_routing_guide()
    suite_index = toxmcp_suite_index_guide()
    worker_routing = worker_routing_guide()
    worker_tier2 = worker_tier2_bridge_guide()
    worker_art = worker_art_adapter_guide()
    worker_art_exchange = worker_art_external_exchange_guide()
    worker_art_execution = worker_art_execution_guide()
    worker_dermal_bridge = worker_dermal_bridge_guide()
    worker_dermal_adapter = worker_dermal_adapter_guide()
    worker_dermal_execution = worker_dermal_execution_guide()
    integrated_workflow = integrated_exposure_workflow_guide()

    assert "Tier A" in uncertainty
    assert "Tier B" in uncertainty
    assert "Tier C" in uncertainty
    assert "Packaged Archetype Sets" in archetypes
    assert "`adult_leave_on_hand_cream`" in archetypes
    assert "`adult_personal_care_pump_spray_tier1`" in archetypes
    assert "Packaged Probability Profiles" in probability_bounds
    assert "`adult_leave_on_hand_cream_use_amount_per_event`" in probability_bounds
    assert "`child_direct_oral_liquid_use_events_per_day`" in probability_bounds
    assert "Packaged Scenario-Probability Profiles" in probability_bounds
    assert "`adult_leave_on_hand_cream_use_intensity_package`" in probability_bounds
    assert "`child_direct_oral_liquid_regimen_package`" in probability_bounds
    assert "`adult_personal_care_pump_spray_tier1_near_field_context_package`" in probability_bounds
    assert "`driverFamily`" in probability_bounds
    assert "`packageFamily`" in probability_bounds
    assert "requestedTier=tier_1" in inhalation_tier_guide
    assert "exposure_build_inhalation_tier1_screening_scenario" in inhalation_tier_guide
    assert "inhalationTier1ScenarioRequest.v1" in inhalation_tier_guide
    assert "exposureScenario.v1" in inhalation_tier_guide
    assert "tier1-inhalation://manifest" in inhalation_tier_guide
    assert "docs://tier1-inhalation-parameter-guide" in inhalation_tier_guide
    assert "Inhalation Residual-Air Reentry Guide" in inhalation_reentry_guide
    assert "exposure_build_inhalation_residual_air_reentry_scenario" in inhalation_reentry_guide
    assert "inhalationResidualAirReentryScenarioRequest.v1" in inhalation_reentry_guide
    assert "`tier1_profile_alignment_status`" in inhalation_tier_guide
    assert "`tier1_profile_anchor_divergence`" in inhalation_tier_guide
    assert "`household_cleaner_trigger_spray_tier1`" in inhalation_tier_guide
    assert "`personal_care_aerosol_spray_tier1`" in inhalation_tier_guide
    assert "Tier 1 Inhalation Parameter Guide" in tier1_parameter_guide
    assert "`benchmark_tier1_nf_ff_personal_care_profiles_v1`" in tier1_parameter_guide
    assert "`personal_care_pump_spray_tier1`" in tier1_parameter_guide
    assert "`tier1_profile_anchor_divergence`" in tier1_parameter_guide
    assert "source_distance_m" in inhalation_tier_guide
    assert "benchmarkDomains" not in validation
    assert "External Validation Datasets" in validation
    assert "`cleaning_trigger_spray_airborne_mass_fraction_2019`" in validation
    assert "pubmed.ncbi.nlm.nih.gov/31361572" in validation
    assert "Executable Validation Checks" in validation
    assert "validation://coverage-report" in validation
    assert "docs://validation-coverage-report" in validation
    assert "validation://reference-bands" in validation
    assert "benchmarks://goldset" in validation
    assert "executedValidationChecks" in validation
    assert "air-space insecticide aerosol concentration realism" in validation
    assert "wet-cloth contact mass realism" in validation
    assert "Validation Reference Bands" in validation_bands
    assert "`air_space_insecticide_aerosol_concentration_2001_band`" in validation_bands
    assert "`chlorpyrifos_residual_air_reentry_start_concentration_1990_band`" in (
        validation_bands
    )
    assert "`cleaning_trigger_spray_airborne_fraction_2019_band`" in validation_bands
    assert "`hand_cream_application_loading_2012_band`" in validation_bands
    assert "`herbal_medicinal_valerian_oral_daily_mass_2015_band`" in validation_bands
    assert "`medicinal_liquid_direct_oral_delivered_mass_2025_band`" in validation_bands
    assert "`consumer_disinfectant_trigger_spray_inhaled_dose_2015_band`" in validation_bands
    assert "`trigger_spray_aerosol_decay_half_life_2023_band`" in validation_bands
    assert "`worker_biocidal_handheld_trigger_spray_concentration_2023_band`" in (
        validation_bands
    )
    assert "`worker_biocidal_handheld_trigger_spray_dermal_mass_2023_band`" in (
        validation_bands
    )
    assert "`wet_cloth_contact_mass_2018_band`" in validation_bands
    assert "selectors:" in validation_bands
    assert "Validation Time-Series Packs" in validation_time_series
    assert "`air_space_insecticide_aerosol_room_air_series_2001`" in validation_time_series
    assert "`air_space_insecticide_aerosol_6h_concentration_2001`" in validation_time_series
    assert "`chlorpyrifos_residual_air_reentry_room_air_series_1990`" in validation_time_series
    assert "`chlorpyrifos_residual_air_reentry_24h_concentration_1990`" in validation_time_series
    assert "`diazinon_office_residual_air_series_1990`" in validation_time_series
    assert "`diazinon_residual_air_reentry_48h_concentration_1990`" in validation_time_series
    assert "Verification Summary" in verification_summary
    assert "verification://summary" in verification_summary
    assert "contract-surface-alignment" in verification_summary
    assert "validation-resource-publication" in verification_summary
    assert "release://metadata-report" in verification_summary
    assert "validation://coverage-report" in verification_summary
    assert "validation://time-series-packs" in validation
    assert "Validation Dossier" in dossier
    assert "Validation Coverage Report" in coverage_report
    assert "[benchmark_time_resolved]" in coverage_report
    assert "`inhalation_residual_air_reentry`" in coverage_report
    assert "`inhalation_well_mixed_spray`" in coverage_report
    assert "`worker_inhalation_control_aware_screening`" in coverage_report
    assert "`worker_dermal_absorbed_dose_screening`" in coverage_report
    assert "`consumer_air_space_insecticide_aerosol`" in coverage_report
    assert "`eu_diazinon_indoor_surface_insecticide`" in coverage_report
    assert "`heuristic_defaults_active`" in dossier
    assert "`tier1_nf_ff_external_validation_partial_only`" in dossier
    assert "`residual_air_reentry_validation_narrow_anchor_only`" in dossier
    assert "Goldset Benchmark Guide" in goldset
    assert "`consumer_trigger_spray_cleaner_aerosol`" in goldset
    assert "`eu_diazinon_indoor_surface_insecticide`" in goldset
    assert "`diazinon_office_postapplication_reentry`" in goldset
    assert "`chlorpyrifos_indoor_surface_insecticide_reentry`" in goldset
    assert "`worker_handheld_biocidal_trigger_spray_monitoring`" in goldset
    assert "`consumer_mosquito_aerosol_room_air_validation`" in goldset
    assert "`consumer_disinfectant_trigger_spray_tier1_monitoring`" in goldset
    assert "`eu_herbal_medicinal_oral_posology_alignment`" in goldset
    assert "`inhalation_residual_air_reentry_chlorpyrifos_time_series_1990`" in goldset
    assert "`worker_biocidal_spray_dermal_contact`" in goldset
    assert "`benchmark_regressed_showcase`" in goldset
    assert "pubmed.ncbi.nlm.nih.gov/31361572" in goldset
    assert "pubmed.ncbi.nlm.nih.gov/1693041" in goldset
    assert "`ema_traditional_herbal_medicinal_oral_context_2026`" in coverage_report
    assert "`ema_valerian_root_oral_posology_2015`" in coverage_report
    assert "`ec_food_supplement_capsule_context_2026`" in coverage_report
    assert "`who_traditional_medicine_topical_context_2026`" in coverage_report
    assert "`ema_arnica_topical_application_geometry_2014`" in coverage_report
    assert "Defaults Curation Report" in defaults_curation
    cleaner_wipe_transfer = (
        "`transfer_efficiency:application_method=wipe,product_category=household_cleaner`"
    )
    cleaner_surface_contact = (
        "`retention_factor:product_category=household_cleaner,retention_type=surface_contact`"
    )
    personal_care_pump_spray = (
        "`aerosolized_fraction:application_method=pump_spray,product_category=personal_care`"
    )
    personal_care_aerosol_spray = (
        "`aerosolized_fraction:application_method=aerosol_spray,product_category=personal_care`"
    )
    assert cleaner_wipe_transfer in defaults_curation
    assert cleaner_surface_contact in defaults_curation
    assert personal_care_pump_spray in defaults_curation
    assert personal_care_aerosol_spray in defaults_curation
    assert (
        "`ingestion_fraction:application_method=direct_oral,product_category=herbal_medicinal_product`"
        in defaults_curation
    )
    assert (
        "`ingestion_fraction:application_method=direct_oral,product_category=botanical_supplement`"
        in defaults_curation
    )
    assert "`ema_traditional_herbal_medicinal_products_guideline_2026`" in defaults_curation
    assert "`ec_food_supplements_page_2026`" in defaults_curation
    assert "`who_traditional_medicine_qna_2026`" in defaults_curation
    assert "Route-Semantic Highlights" in defaults_curation
    assert "`transfer_efficiency:application_method=trigger_spray`" in defaults_curation
    assert "`transfer_efficiency:application_method=hand_application`" in defaults_curation
    assert "Residual Heuristic Branches" in defaults_curation
    assert "Exposure Platform Architecture" in architecture
    assert "Fate MCP" in architecture
    assert "Dietary MCP" in architecture
    assert "Bioactivity-PoD MCP" in suite_index
    assert "docs://cross-mcp-contract-guide" in suite_index
    assert "docs/toxmcp_suite_index.md" in suite_index
    assert "Worker Exposure Mode" in architecture
    assert "PBPK remains a separate MCP boundary" in architecture
    assert "Capability Maturity Matrix" in capability_matrix
    assert "`benchmark-regressed`" in capability_matrix
    assert "`external-normalized`" in capability_matrix
    assert "`bounded surrogate`" in capability_matrix
    assert "docs/capability_maturity_matrix.md" in capability_matrix
    assert "Repository Slug Decision" in slug_decision
    assert "`ToxMCP/direct-use-exposure-mcp`" in slug_decision
    assert "`v0.1.x`" in slug_decision
    assert "docs/adr/0004-repository-slug.md" in slug_decision
    assert "Cross-MCP Contract Guide" in cross_mcp_contracts
    assert "`chemicalIdentity.v1`" in cross_mcp_contracts
    assert "`exposureScenarioDefinition.v1`" in cross_mcp_contracts
    assert "`routeDoseEstimate.v1`" in cross_mcp_contracts
    assert "`environmentalReleaseScenario.v1`" in cross_mcp_contracts
    assert "`concentrationSurface.v1`" in cross_mcp_contracts
    assert "diet-mediated oral belongs in Dietary MCP" in cross_mcp_contracts
    assert "`oralExposureContext`" in cross_mcp_contracts
    assert "Service Selection Guide" in service_selection
    assert "Direct-use oral stays in Direct-Use Exposure MCP" in service_selection
    assert "Traditional Chinese Medicine regimens" in service_selection
    assert "Supplement pills or capsules should be split explicitly" in service_selection
    assert "Environmental release, multimedia transfer" in service_selection
    assert "`pbpkExternalImportBundle.v1`" in service_selection
    assert "Herbal, TCM, and Supplement Routing Guide" in herbal_routing
    assert "`productUseProfile.intendedUseFamily=medicinal`" in herbal_routing
    assert "`productUseProfile.oralExposureContext=direct_use_supplement`" in herbal_routing
    assert "Herbal tea consumed as part of normal diet -> `Dietary MCP`" in herbal_routing
    assert "docs://herbal-medicinal-routing-guide" in suite_index
    assert "Worker Routing Guide" in worker_routing
    assert "exposure_route_worker_task" in worker_routing
    assert "workerTaskRoutingInput.v1" in worker_routing
    assert "workerTaskRoutingDecision.v1" in worker_routing
    assert "docs://worker-routing-guide" in worker_routing
    assert "Worker Tier 2 Bridge Guide" in worker_tier2
    assert "exposure_export_worker_inhalation_tier2_bridge" in worker_tier2
    assert "exportWorkerInhalationTier2BridgeRequest.v1" in worker_tier2
    assert "workerInhalationTier2BridgePackage.v1" in worker_tier2
    assert "docs://worker-tier2-bridge-guide" in worker_tier2
    assert "Worker ART Adapter Guide" in worker_art
    assert "worker_ingest_inhalation_tier2_task" in worker_art
    assert "workerInhalationTier2AdapterRequest.v1" in worker_art
    assert "workerInhalationTier2AdapterIngestResult.v1" in worker_art
    assert "docs://worker-art-adapter-guide" in worker_art
    assert "packaged determinant templates" in worker_art
    assert "`aligned`, `partial`, `heuristic`, or `none`" in worker_art
    assert "janitorial pump sprays" in worker_art
    assert "paint/coating aerosols" in worker_art
    assert "solvent/degreasing vapor tasks" in worker_art
    assert "open mixing/blending" in worker_art
    assert "enclosed transfer vapor tasks" in worker_art
    assert "outdoor or enhanced-ventilation" in worker_art
    assert "Worker ART Execution Guide" in worker_art_execution
    assert "worker_execute_inhalation_tier2_task" in worker_art_execution
    assert "executeWorkerInhalationTier2Request.v1" in worker_art_execution
    assert "workerInhalationTier2ExecutionResult.v1" in worker_art_execution
    assert "docs://worker-art-execution-guide" in worker_art_execution
    assert "room-average vapor-release surrogate" in worker_art_execution
    assert "worker_control_factor" in worker_art_execution
    assert "respiratory_protection_factor" in worker_art_execution
    assert "Worker ART External Exchange Guide" in worker_art_exchange
    assert "worker_export_inhalation_art_execution_package" in worker_art_exchange
    assert "exportWorkerArtExecutionPackageRequest.v1" in worker_art_exchange
    assert "workerArtExternalExecutionPackage.v1" in worker_art_exchange
    assert "worker_import_inhalation_art_execution_result" in worker_art_exchange
    assert "importWorkerArtExecutionResultRequest.v1" in worker_art_exchange
    assert "rawArtifacts" in worker_art_exchange
    assert "art_worker_execution_report_json_v1" in worker_art_exchange
    assert "art_worker_result_summary_csv_semicolon_v1" in worker_art_exchange
    assert "adapterHint" in worker_art_exchange
    assert "Worker Dermal Bridge Guide" in worker_dermal_bridge
    assert "exposure_export_worker_dermal_absorbed_dose_bridge" in worker_dermal_bridge
    assert "exportWorkerDermalAbsorbedDoseBridgeRequest.v1" in worker_dermal_bridge
    assert "workerDermalAbsorbedDoseBridgePackage.v1" in worker_dermal_bridge
    assert "docs://worker-dermal-bridge-guide" in worker_dermal_bridge
    assert "Worker Dermal Adapter Guide" in worker_dermal_adapter
    assert "worker_ingest_dermal_absorbed_dose_task" in worker_dermal_adapter
    assert "workerDermalAbsorbedDoseAdapterRequest.v1" in worker_dermal_adapter
    assert "workerDermalAbsorbedDoseAdapterIngestResult.v1" in worker_dermal_adapter
    assert "docs://worker-dermal-adapter-guide" in worker_dermal_adapter
    assert "janitorial wet-wipe glove contact" in worker_dermal_adapter
    assert "generic gloved or ungloved hand contact" in worker_dermal_adapter
    assert "Worker Dermal Execution Guide" in worker_dermal_execution
    assert "worker_execute_dermal_absorbed_dose_task" in worker_dermal_execution
    assert "executeWorkerDermalAbsorbedDoseRequest.v1" in worker_dermal_execution
    assert "workerDermalAbsorbedDoseExecutionResult.v1" in worker_dermal_execution
    assert "docs://worker-dermal-execution-guide" in worker_dermal_execution
    assert "externalSkinMassMgPerDay" in worker_dermal_execution
    assert "PPE penetration" in worker_dermal_execution
    assert "Integrated Exposure Workflow Guide" in integrated_workflow
    assert "exposure_run_integrated_workflow" in integrated_workflow
    assert "runIntegratedExposureWorkflowInput.v1" in integrated_workflow
    assert "integratedExposureWorkflowResult.v1" in integrated_workflow
    assert "docs://integrated-exposure-workflow-guide" in integrated_workflow
    assert (
        "CompTox, SCCS, SCCS opinion, CosIng, ConsExpo, nanomaterial, and microplastics"
        in integrated_workflow
    )
