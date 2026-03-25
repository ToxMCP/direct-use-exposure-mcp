from __future__ import annotations

from exposure_scenario_mcp.contracts import (
    build_release_metadata_report,
    build_release_readiness_report,
    build_security_provenance_review_report,
)
from exposure_scenario_mcp.defaults import DefaultsRegistry
from exposure_scenario_mcp.guidance import (
    archetype_library_guide,
    conformance_report_markdown,
    defaults_curation_report_markdown,
    inhalation_tier_upgrade_guide,
    probability_bounds_guide,
    release_notes_markdown,
    release_readiness_markdown,
    tier1_inhalation_parameter_guide,
    uncertainty_framework,
    validation_dossier_markdown,
    validation_framework,
    validation_reference_bands_guide,
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


def test_uncertainty_and_validation_guidance_expose_tier_a_b_posture() -> None:
    uncertainty = uncertainty_framework()
    validation = validation_framework()
    dossier = validation_dossier_markdown()
    defaults_curation = defaults_curation_report_markdown()
    archetypes = archetype_library_guide()
    inhalation_tier_guide = inhalation_tier_upgrade_guide()
    tier1_parameter_guide = tier1_inhalation_parameter_guide()
    probability_bounds = probability_bounds_guide()
    validation_bands = validation_reference_bands_guide()

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
    assert "validation://reference-bands" in validation
    assert "executedValidationChecks" in validation
    assert "wet-cloth contact mass realism" in validation
    assert "Validation Reference Bands" in validation_bands
    assert "`hand_cream_application_loading_2012_band`" in validation_bands
    assert "`wet_cloth_contact_mass_2018_band`" in validation_bands
    assert "selectors:" in validation_bands
    assert "Validation Dossier" in dossier
    assert "`heuristic_defaults_active`" in dossier
    assert "`tier1_nf_ff_external_validation_partial_only`" in dossier
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
    assert "Route-Semantic Highlights" in defaults_curation
    assert "`transfer_efficiency:application_method=trigger_spray`" in defaults_curation
    assert "`transfer_efficiency:application_method=hand_application`" in defaults_curation
    assert "Residual Heuristic Branches" in defaults_curation
