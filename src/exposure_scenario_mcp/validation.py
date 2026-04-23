"""Validation posture and benchmark-domain metadata."""

from __future__ import annotations

import math

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest
from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.models import (
    DefaultsCurationStatus,
    ExecutedValidationCheck,
    ExposureScenario,
    ExternalValidationDataset,
    ExternalValidationDatasetStatus,
    ProductAmountUnit,
    Route,
    ScalarValue,
    TierLevel,
    UncertaintyTier,
    ValidationBenchmarkDomain,
    ValidationCheckStatus,
    ValidationCoverageDomainSummary,
    ValidationCoverageReport,
    ValidationDossierReport,
    ValidationEvidenceReadiness,
    ValidationGap,
    ValidationGapSeverity,
    ValidationStatus,
    ValidationSummary,
)
from exposure_scenario_mcp.source_classification import is_warning_heuristic_source_id
from exposure_scenario_mcp.validation_reference_bands import ValidationReferenceBandRegistry
from exposure_scenario_mcp.validation_time_series import ValidationTimeSeriesReferenceRegistry

BENCHMARK_CASE_DOMAINS = {
    "dermal_face_cream_sccs_screening": "dermal_direct_application",
    "dermal_hand_cream_screening": "dermal_direct_application",
    "dermal_density_precedence_volume_case": "dermal_direct_application",
    "dermal_tcm_topical_balm_screening": "dermal_direct_application",
    "dermal_herbal_topical_spray_label_amount_screening": "dermal_direct_application",
    "dermal_herbal_recovery_patch_label_amount_screening": "dermal_direct_application",
    "dermal_capsicum_hydrogel_patch_label_amount_screening": "dermal_direct_application",
    "oral_direct_oral_screening": "oral_direct_intake",
    "oral_medicinal_liquid_delivered_dose_screening": "oral_direct_intake",
    "oral_herbal_medicinal_valerian_posology_screening": "oral_direct_intake",
    "oral_herbal_medicinal_valerian_infusion_posology_screening": "oral_direct_intake",
    "oral_tcm_medicinal_direct_use_screening": "oral_direct_intake",
    "oral_botanical_supplement_direct_use_screening": "oral_direct_intake",
    "oral_dietary_supplement_iron_capsule_label_screening": "oral_direct_intake",
    "inhalation_trigger_spray_screening": "inhalation_well_mixed_spray",
    "inhalation_saturation_cap_stress_case": "inhalation_well_mixed_spray",
    "inhalation_air_space_insecticide_aerosol_screening": "inhalation_well_mixed_spray",
    "inhalation_air_space_insecticide_aerosol_time_series_0p75h_2001": (
        "inhalation_well_mixed_spray"
    ),
    "inhalation_air_space_insecticide_aerosol_time_series_6h_2001": ("inhalation_well_mixed_spray"),
    "inhalation_residual_air_reentry_chlorpyrifos_screening": ("inhalation_residual_air_reentry"),
    "inhalation_residual_air_reentry_chlorpyrifos_time_series_1990": (
        "inhalation_residual_air_reentry"
    ),
    "inhalation_residual_air_reentry_diazinon_time_series_1990": (
        "inhalation_residual_air_reentry"
    ),
    "inhalation_residual_air_reentry_diazinon_home_use_native_screening": (
        "inhalation_residual_air_reentry"
    ),
    "inhalation_residual_air_reentry_native_treated_surface_screening": (
        "inhalation_residual_air_reentry"
    ),
    "inhalation_tier1_trigger_spray_nf_ff": "inhalation_near_field_far_field",
    "inhalation_tier1_local_entrainment_floor_screening": "inhalation_near_field_far_field",
    "inhalation_tier1_coarse_spray_settling_sensitivity": "inhalation_near_field_far_field",
    "inhalation_tier1_disinfectant_trigger_spray_external_2015": (
        "inhalation_near_field_far_field"
    ),
    "inhalation_tier1_scenario_package_probability": "inhalation_near_field_far_field",
    "cross_route_aggregate_summary": "aggregate_cross_route_screening",
    "cross_route_aggregate_internal_equivalent_summary": "aggregate_cross_route_screening",
    "zero_baseline_comparison": "scenario_delta_comparison",
    "dermal_pbpk_export": "pbpk_external_handoff",
    "inhalation_pbpk_export_transient_profile": "pbpk_external_handoff",
    "dermal_pbpk_external_import_package": "pbpk_external_handoff",
    "worker_inhalation_janitorial_trigger_spray_execution": (
        "worker_inhalation_control_aware_screening"
    ),
    "worker_inhalation_handheld_biocidal_trigger_spray_execution": (
        "worker_inhalation_control_aware_screening"
    ),
    "worker_dermal_wet_wipe_gloved_hands_execution": "worker_dermal_absorbed_dose_screening",
    "worker_dermal_handheld_biocidal_trigger_spray_execution": (
        "worker_dermal_absorbed_dose_screening"
    ),
    "worker_dermal_extreme_loading_surface_cap_execution": (
        "worker_dermal_absorbed_dose_screening"
    ),
}

BENCHMARK_DOMAIN_NOTES = {
    "dermal_direct_application": [
        (
            "Current executable coverage is deterministic benchmark regression across "
            "core leave-on cream, SCCS face-cream, and direct-use herbal topical-balm "
            "and spray cases, now paired with executable topical-herbal geometry, "
            "official-label delivered-amount anchors, and patch unit-mass anchors rather "
            "than a true dermal absorption calibration set."
        )
    ],
    "oral_direct_intake": [
        (
            "Current executable coverage now verifies direct-intake screening arithmetic "
            "across generic direct-oral, medicinal-liquid, EMA-aligned herbal medicinal "
            "solid-dose and infusion-style regimens, medicinal tablet, and product-centric "
            "supplement capsule cases including an official-label serving anchor, but it "
            "still does not benchmark distributional use factors."
        )
    ],
    "inhalation_well_mixed_spray": [
        (
            "Current benchmark coverage protects the Tier 0 room-average spray path "
            "against numeric drift."
        )
    ],
    "inhalation_near_field_far_field": [
        (
            "Current benchmark coverage includes a canonical Tier 1 NF/FF scenario, a "
            "bounded local-entrainment-floor scenario, a narrow externally anchored consumer "
            "disinfectant trigger-spray dose case, and a Tier C package built from governed "
            "Tier 1 support points."
        )
    ],
    "inhalation_residual_air_reentry": [
        (
            "Current residual-air reentry coverage is narrow: it anchors the dedicated "
            "chlorpyrifos post-application reentry-start concentration, a diazinon home-use "
            "native residual-air anchor, sparse chlorpyrifos and diazinon room-air decay "
            "series, one bounded native treated-surface same-room screening branch, and "
            "decay arithmetic, not full treated-surface emission dynamics across indoor "
            "pesticide families."
        )
    ],
    "aggregate_cross_route_screening": [
        (
            "Aggregate validation remains bookkeeping-oriented until a broader "
            "population engine and external proxies are wired in. Current coverage "
            "locks both external-dose summaries and opt-in route-bioavailability-adjusted "
            "internal-equivalent screening totals."
        )
    ],
    "pbpk_external_handoff": [
        (
            "These benchmarks verify handoff semantics and request-shape fidelity, "
            "including additive transient inhalation concentration profiles when "
            "requested, not PBPK model correctness."
        )
    ],
    "worker_inhalation_control_aware_screening": [
        (
            "Current worker inhalation coverage is a governed surrogate benchmark for "
            "control-aware janitorial trigger-spray execution plus a narrow small-scale "
            "handheld biocidal spray concentration anchor, not a true ART validation set."
        )
    ],
    "worker_dermal_absorbed_dose_screening": [
        (
            "Current worker dermal coverage is a governed PPE-aware wet-wipe benchmark plus "
            "a narrow handheld biocidal spray dermal-mass anchor, not a chemical-specific "
            "permeation or glove-breakthrough validation set."
        )
    ],
}

EXTERNAL_VALIDATION_DATASETS = [
    ExternalValidationDataset(
        datasetId="cleaning_trigger_spray_airborne_mass_fraction_2019",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="total airborne mass fraction and aerosol size distribution",
        targetMetrics=["aerosolized_fraction", "average_air_concentration_mg_per_m3"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner"],
        referenceTitle=(
            "Characterization of airborne particles from cleaning sprays and their "
            "corresponding respiratory deposition fractions"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/31361572/",
        note=(
            "Seven ready-to-use trigger cleaning sprays produced total airborne mass "
            "fractions between 2.7% and 32.2% of emitted mass. This is a useful emission-side "
            "anchor for Tier 0 spray screening, but it is not a full executable "
            "scenario-to-dose calibration set."
        ),
    ),
    ExternalValidationDataset(
        datasetId="spray_cleaning_disinfection_decay_half_life_2023",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="room-air aerosol decay half-life for trigger and pressurized spray products",
        targetMetrics=["room_air_decay_half_life_hours"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner", "disinfectant"],
        referenceTitle=(
            "Characterization of the aerosol release from spray cleaning and disinfection "
            "products - Spray scenarios in a climate chamber"
        ),
        referenceLocator=(
            "https://perpus-utama.poltekkes-malang.ac.id/assets/file/jurnal/volume_252_2023.pdf"
        ),
        note=(
            "A climate-chamber study of professional cleaning and disinfection sprays reported "
            "an average aerosol total-particle-mass half-life of about 0.25 h for 13 trigger "
            "sprays, with large between-product variation. This supports a narrow executable "
            "half-life realism check for trigger-spray room-decay behavior, but it is not a "
            "chemical-specific active-substance calibration set."
        ),
    ),
    ExternalValidationDataset(
        datasetId="household_mosquito_aerosol_indoor_air_2001",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="closed-room indoor air concentration after household mosquito aerosol use",
        targetMetrics=["average_air_concentration_mg_per_m3"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["air_space_insecticide"],
        referenceTitle=(
            "Exposures of infants and young children to pyrethroid pesticides in mosquito "
            "coils and indoor insecticide sprays"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/11354726/",
        note=(
            "Indoor insecticide spray testing in a closed room reported a prallethrin air "
            "concentration of 0.0138 ppm within 30 to 45 minutes after use and most residues "
            "dissipated below 0.0001 ppm by 6 hours. This supports a narrow room-air "
            "benchmark for air-space insecticide aerosol screening plus a sparse late-decay "
            "time-series anchor after conversion to mg/m3."
        ),
    ),
    ExternalValidationDataset(
        datasetId="consumer_spray_inhalation_exposure_2015",
        domain="inhalation_near_field_far_field",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="breathing-zone inhalation exposure and deposited dose during spray use",
        targetMetrics=[
            "breathing_zone_time_weighted_average_mg_per_m3",
            "inhaled_mass_mg_per_day",
        ],
        applicableTierClaims=[TierLevel.TIER_1],
        productFamilies=["household_cleaner", "personal_care"],
        referenceTitle=(
            "Quantitative assessment of inhalation exposure and deposited dose of aerosol "
            "from nanotechnology-based consumer sprays"
        ),
        referenceLocator="https://pmc.ncbi.nlm.nih.gov/articles/PMC4303255/",
        note=(
            "Mannequin-head sampling under realistic consumer spray application reported "
            "product-specific inhalation exposure and deposited-dose ranges. This is useful "
            "for near-field burden checks, but it is not a direct calibration dataset for "
            "the MCP NF/FF mass-balance solver."
        ),
    ),
    ExternalValidationDataset(
        datasetId="consumer_disinfectant_trigger_spray_inhalation_2015",
        domain="inhalation_near_field_far_field",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=("total inhalation exposure during a consumer disinfectant trigger-spray task"),
        targetMetrics=[
            "normalized_external_dose",
            "inhaled_mass_mg_per_day",
            "breathing_zone_time_weighted_average_mg_per_m3",
        ],
        applicableTierClaims=[TierLevel.TIER_1],
        productFamilies=["disinfectant"],
        referenceTitle=(
            "Quantitative assessment of inhalation exposure and deposited dose of aerosol "
            "from nanotechnology-based consumer sprays (Supplementary Information)"
        ),
        referenceLocator="https://www.rsc.org/suppdata/en/c3/c3en00053b/c3en00053b.pdf",
        note=(
            "The supplementary disinfectant-spray case reports a mean total inhalation "
            "exposure of about 1076 ng/kg bw/application and supports a narrow executable "
            "dose band for a study-like Tier 1 NF/FF trigger-spray scenario. It is useful "
            "for a product-specific external check, but it is still not a full chamber "
            "time-series calibration set for the NF/FF solver."
        ),
    ),
    ExternalValidationDataset(
        datasetId="worker_biocidal_professional_cleaning_2023",
        domain="inhalation_well_mixed_spray",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="professional surface disinfection air concentration and daily mass",
        targetMetrics=[
            "control_adjusted_average_air_concentration_mg_per_m3",
            "adjusted_inhaled_mass_mg_per_day",
        ],
        applicableTierClaims=[TierLevel.TIER_2],
        productFamilies=["disinfectant"],
        referenceTitle="ART 1.5 Calibration Set - Professional Cleaning",
        referenceLocator="https://www.advancedreachtool.com/",
        note=(
            "Professional surface-disinfection data derived from ART 1.5 calibration training "
            "sets for professional janitorial trigger-spraying with localized-behavior controls."
        ),
    ),
    ExternalValidationDataset(
        datasetId="worker_biocidal_spray_foam_inhalation_2023",
        domain="worker_inhalation_control_aware_screening",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "personal air sampling of non-volatile active substances during occupational "
            "biocidal spray and foam applications"
        ),
        targetMetrics=[
            "controlAdjustedAverageAirConcentrationMgPerM3",
            "normalized_worker_inhaled_dose",
        ],
        applicableTierClaims=[TierLevel.TIER_2],
        productFamilies=["disinfectant", "pest_control"],
        referenceTitle=(
            "Inhalation and dermal exposure to biocidal products during foam and spray applications"
        ),
        referenceLocator=(
            "https://www.baua.de/EN/Service/Publications/Essays/article3676.pdf"
            "?__blob=publicationFile&v=3"
        ),
        note=(
            "Occupational monitoring across 26 biocidal foam and spray applications reported "
            "personal-air inhalation exposure with detailed task context, and direct "
            "spray-to-foam comparisons showed lower inhalation exposure for foam "
            "applications. Handheld BAC spray scenarios reported 9.06-61.7 ug/m3 active-"
            "substance concentrations for small-scale surface disinfection sprays. The study "
            "is a strong contextual anchor and now supports a narrow executable worker "
            "concentration band, but it does not provide a direct ART-equivalent determinant "
            "or dose-normalization dataset for the MCP execution kernel."
        ),
    ),
    ExternalValidationDataset(
        datasetId="diazinon_indoor_air_monitoring_home_use_2008",
        domain="inhalation_residual_air_reentry",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "measured indoor air diazinon concentrations during historical home-use contexts"
        ),
        targetMetrics=[
            "air_concentration_at_reentry_start_mg_per_m3",
            "average_air_concentration_mg_per_m3",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["indoor_surface_insecticide"],
        referenceTitle="Diazinon Technical Fact Sheet",
        referenceLocator="https://npic.orst.edu/factsheets/archive/diazinontech.html",
        note=(
            "The technical fact sheet reports indoor air diazinon concentrations up to "
            "13 ug/m3 when diazinon was registered for residential home use. This is useful "
            "as an integration-level plausibility anchor for Diazinon workflows, but it is "
            "not sufficiently scenario-resolved to serve as an executable benchmark band."
        ),
    ),
    ExternalValidationDataset(
        datasetId="chlorpyrifos_broadcast_residential_air_1990",
        domain="inhalation_residual_air_reentry",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "post-application indoor air concentrations after broadcast residential surface "
            "treatment"
        ),
        targetMetrics=[
            "air_concentration_at_reentry_start_mg_per_m3",
            "average_air_concentration_mg_per_m3",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["indoor_surface_insecticide"],
        referenceTitle=(
            "Potential exposure and health risks of infants following indoor residential "
            "pesticide applications"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/1693041/",
        note=(
            "A 0.5% Dursban broadcast application for fleas produced peak infant-breathing-zone "
            "chlorpyrifos air concentrations of 61-94 ug/m3 at 3-7 hours post-application and "
            "about 30 ug/m3 at 24 hours. This is a strong analogue for indoor-surface "
            "insecticide residual-air plausibility, but it mixes broadcast application, "
            "ventilation effects, and delayed post-application decay that the current trigger-"
            "spray screening kernel does not model explicitly."
        ),
    ),
    ExternalValidationDataset(
        datasetId="diazinon_office_postapplication_air_1990",
        domain="inhalation_residual_air_reentry",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "post-application indoor air concentrations after commercial office surface treatment"
        ),
        targetMetrics=[
            "air_concentration_at_reentry_start_mg_per_m3",
            "average_air_concentration_mg_per_m3",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["indoor_surface_insecticide"],
        referenceTitle=(
            "Concentrations of diazinon, chlorpyrifos, and bendiocarb after application in offices"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/1689096/",
        note=(
            "Office monitoring after application of a 1% aqueous diazinon solution reported "
            "air concentrations of 163 and 158 ug/m3 in empty offices and 27 ug/m3 in a "
            "furnished office at 4 hours, with persistence over multiple days. This supports "
            "indoor-surface insecticide plausibility and highlights the importance of treated-"
            "surface re-emission, furnishing effects, and reentry timing that are outside the "
            "current Tier 0 spray-cloud screening semantics."
        ),
    ),
    ExternalValidationDataset(
        datasetId="skin_protection_cream_dose_per_area_2012",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="applied product mass per hand surface area in workplace use",
        targetMetrics=["use_amount_per_event", "surface_loading_mg_per_cm2_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["personal_care"],
        referenceTitle=(
            "How much skin protection cream is actually applied in the workplace? "
            "Determination of dose per skin surface area in nurses"
        ),
        referenceLocator="https://pubmed.ncbi.nlm.nih.gov/22709142/",
        note=(
            "Observed mean skin-protection-cream dose was 0.97 ± 0.6 mg/cm² across 31 nurses "
            "over five workdays. This is useful for direct-application amount realism and "
            "supports a narrow executable loading check when a hand-scale exposed area is "
            "supplied, but it does not validate the MCP transfer or retention factors."
        ),
    ),
    ExternalValidationDataset(
        datasetId="rivm_wet_cloth_dermal_contact_loading_2018",
        domain="dermal_secondary_transfer",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="product mass subject to dermal exposure from touching a wet cloth",
        targetMetrics=["product_contact_mass_g_per_event"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["household_cleaner"],
        referenceTitle="Cleaning Products Fact Sheet",
        referenceLocator="https://www.rivm.nl/bibliotheek/rapporten/2016-0179.pdf",
        note=(
            "RIVM cleaning-product scenarios derive wet-cloth dermal contact amounts of "
            "0.31 g for an all-purpose cleaner spray rinsing case and 0.62 g for a floor "
            "cleaner liquid case. These support an executable secondary-contact realism "
            "check for household-cleaner wipe scenarios, but not a calibrated transfer model."
        ),
    ),
    ExternalValidationDataset(
        datasetId="worker_biocidal_spray_foam_dermal_2023",
        domain="worker_dermal_absorbed_dose_screening",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "patch- and glove-based dermal exposure during occupational biocidal spray and "
            "foam applications"
        ),
        targetMetrics=[
            "externalSkinMassMgPerDay",
            "protectedExternalSkinMassMgPerDay",
            "absorbedMassMgPerDay",
        ],
        applicableTierClaims=[TierLevel.TIER_2],
        productFamilies=["disinfectant", "pest_control"],
        referenceTitle=(
            "Inhalation and dermal exposure to biocidal products during foam and spray applications"
        ),
        referenceLocator=(
            "https://www.baua.de/EN/Service/Publications/Essays/article3676.pdf"
            "?__blob=publicationFile&v=3"
        ),
        note=(
            "Occupational monitoring across 26 biocidal foam and spray applications also "
            "reported dermal contamination using glove dosimeters and body patches. This is a "
            "useful contextual anchor for worker dermal contact during disinfectant or "
            "pest-control spray tasks, and the handheld BAC spray subset supports a narrow "
            "executable 12.8-13.6 mg/day external skin-mass band for study-like small-scale "
            "surface disinfection tasks. It is still not a direct absorbed-dose or glove-"
            "breakthrough validation dataset for the MCP dermal execution kernel."
        ),
    ),
    ExternalValidationDataset(
        datasetId="vigabatrin_ready_to_use_dosing_accuracy_2025",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable="delivered oral dose relative to a target dose during caregiver use",
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["medicinal_liquid"],
        referenceTitle=(
            "Liquid Medication Dosing Errors: Comparison of a Ready-to-Use Vigabatrin "
            "Solution to Reconstituted Solutions of Vigabatrin Powder for Oral Solution"
        ),
        referenceLocator="https://doi.org/10.1007/s12325-024-03089-0",
        note=(
            "Thirty lay users delivered single oral doses to a collection bottle against a "
            "1125 mg target; the ready-to-use solution stayed within ±5%, while the "
            "reconstituted product stayed within ±10% for 23 of 30 users. This is useful "
            "for delivered-dose realism, but it is not a general medication-use calibration set."
        ),
    ),
    ExternalValidationDataset(
        datasetId="ema_valerian_root_oral_posology_2015",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "regulated single-dose and daily-dose oral posology for solid-dose valerian "
            "root dry-extract medicinal products"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_medicinal_product"],
        referenceTitle="European Union herbal monograph on Valeriana officinalis L., radix",
        referenceLocator=(
            "https://www.ema.europa.eu/en/documents/herbal-monograph/"
            "draft-european-union-herbal-monograph-valeriana-officinalis-l-radix_en.pdf"
        ),
        note=(
            "The EMA HMPC monograph states a 450-600 mg dry-extract single dose for oral "
            "solid dosage forms, up to 3 times daily for mild nervous tension. This is a "
            "narrow regulated posology anchor for herbal medicinal oral direct-use "
            "screening, not an observed adherence or dispensing-variability dataset."
        ),
    ),
    ExternalValidationDataset(
        datasetId="ema_valerian_root_infusion_posology_2015",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "regulated single-dose and daily-dose oral posology for valerian herbal-tea "
            "or infusion-style medicinal use"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_medicinal_product"],
        referenceTitle="European Union herbal monograph on Valeriana officinalis L., radix",
        referenceLocator=(
            "https://www.ema.europa.eu/en/documents/herbal-monograph/"
            "draft-european-union-herbal-monograph-valeriana-officinalis-l-radix_en.pdf"
        ),
        note=(
            "The EMA HMPC monograph states a 0.3-3.0 g single dose of comminuted herbal "
            "substance as herbal tea in 150 ml boiling water, up to 3 times daily. This "
            "is a medicinal infusion/decoction-style oral direct-use posology anchor, not "
            "an ordinary dietary tea intake dataset."
        ),
    ),
    ExternalValidationDataset(
        datasetId="ema_traditional_herbal_medicinal_oral_context_2026",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "regulated medicinal oral-product context for traditional herbal medicinal products"
        ),
        targetMetrics=[
            "application_method",
            "intended_use_family",
            "oral_exposure_context",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_medicinal_product"],
        referenceTitle=(
            "Non-clinical documentation in applications for marketing authorisation / "
            "registration of well-established and traditional herbal medicinal products"
        ),
        referenceLocator=(
            "https://www.ema.europa.eu/en/non-clinical-documentation-applications-"
            "marketing-authorisation-registration-well-established-and-traditional-"
            "herbal-medicinal-products-scientific-guideline"
        ),
        note=(
            "This EMA guideline does not provide a quantitative direct-use dosing "
            "distribution, but it is a strong medicinal-product anchor for keeping TCM and "
            "related herbal oral regimens on the Direct-Use side of the boundary when the "
            "workflow is explicitly product-centric and medicinal."
        ),
    ),
    ExternalValidationDataset(
        datasetId="ec_food_supplement_capsule_context_2026",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "regulated dose-form context for food supplements when a capsule or pill is "
            "being assessed as a labeled product regimen"
        ),
        targetMetrics=[
            "application_method",
            "intended_use_family",
            "oral_exposure_context",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["botanical_supplement"],
        referenceTitle="Food supplements",
        referenceLocator=(
            "https://food.ec.europa.eu/food-safety/labelling-and-nutrition/food-supplements_en"
        ),
        note=(
            "The European Commission overview does not provide quantitative supplement-dose "
            "distributions, but it is a useful source-backed anchor for distinguishing a "
            "product-centric supplement capsule workflow from broader food-mediated dietary "
            "intake."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_sideral_iron_capsule_label_2025",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official serving-size and daily elemental-iron mass for a labeled oral "
            "dietary supplement capsule regimen"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["dietary_supplement"],
        referenceTitle="DailyMed - SIDERAL- iron capsule, gelatin coated",
        referenceLocator=(
            "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?"
            "setid=b6fadf1a-fbe5-4537-87d9-179ca4aefdc6&version=1"
        ),
        note=(
            "The official DailyMed label states one 100 mg capsule per day and 30 mg "
            "elemental iron per serving. This is a narrow official-label anchor for "
            "product-centric direct-use supplement dosing, not a dietary supplement "
            "population-intake dataset."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_melatonin_gummy_label_2026",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official serving-size and daily active mass for a labeled oral dietary "
            "supplement gummy regimen"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["dietary_supplement"],
        referenceTitle="DailyMed - Melatonin Gummy",
        referenceLocator="https://dailymed.nlm.nih.gov/dailymed/",
        note=(
            "The typical official label states 2 gummies per day delivering 5 mg melatonin. "
            "This is a narrow official-label anchor for product-centric supplement gummy dosing."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_echinacea_tincture_label_2026",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official serving-size and daily active mass for a labeled oral botanical "
            "supplement tincture"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["botanical_supplement"],
        referenceTitle="DailyMed - Echinacea Liquid Extract",
        referenceLocator="https://dailymed.nlm.nih.gov/dailymed/",
        note=(
            "The typical official label states 1 mL per day delivering 250 mg extract. "
            "This is a narrow official-label anchor for product-centric botanical liquid dosing."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_vitaminc_effervescent_label_2026",
        domain="oral_direct_intake",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official serving-size and daily active mass for a labeled oral dietary "
            "supplement effervescent tablet"
        ),
        targetMetrics=["chemical_mass_mg_per_event", "external_mass_mg_per_day"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["dietary_supplement"],
        referenceTitle="DailyMed - Vitamin C Effervescent",
        referenceLocator="https://dailymed.nlm.nih.gov/dailymed/",
        note=(
            "The typical official label states 1 tablet per day delivering 1000 mg Vitamin C. "
            "This is a narrow official-label anchor for product-centric effervescent tablet dosing."
        ),
    ),
    ExternalValidationDataset(
        datasetId="who_traditional_medicine_topical_context_2026",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "direct-use topical traditional-medicine product context for leave-on balms, "
            "liniments, and related herbal skin preparations"
        ),
        targetMetrics=[
            "application_method",
            "retention_type",
            "transfer_efficiency",
        ],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_topical_product"],
        referenceTitle="Traditional medicine",
        referenceLocator="https://www.who.int/news-room/questions-and-answers/item/traditional-medicine",
        note=(
            "The WHO traditional-medicine overview is not a quantitative dermal loading "
            "dataset, but it is a defendable context anchor for treating topical TCM and "
            "related herbal balms as explicit direct-use dermal products rather than as an "
            "undefined special category."
        ),
    ),
    ExternalValidationDataset(
        datasetId="ema_arnica_topical_application_geometry_2014",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable=(
            "quantitative strip-length topical application guidance for arnica gel and "
            "ointment family products"
        ),
        targetMetrics=["application_strip_length_cm", "application_coverage_context"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_topical_product"],
        referenceTitle=(
            "Overview of comments received on Community herbal monograph on Arnica montana L., flos"
        ),
        referenceLocator=(
            "https://www.ema.europa.eu/en/documents/herbal-comments/"
            "overview-comments-received-community-herbal-monograph-arnica-montana-l-flos_en.pdf"
        ),
        note=(
            "The EMA comment overview records marketed topical arnica products with explicit "
            "application geometry such as 2-10 cm to the affected area 2-4 times daily and "
            "3 cm for a palm-sized area or 8 cm for a lower leg. This is a useful "
            "quantitative analogue anchor for topical herbal application semantics, but it "
            "does not provide a direct mass-per-application calibration set."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_ahealon_topical_spray_label_2026",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official delivered amount per application for a product-centric topical "
            "herbal spray regimen"
        ),
        targetMetrics=["use_amount_per_event"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_topical_product"],
        referenceTitle="DailyMed - AHEALON topical spray label",
        referenceLocator=(
            "https://dailymed.nlm.nih.gov/dailymed/getFile.cfm?"
            "setid=6720fab5-6ef0-e922-0c2c-2fe5280838ab&type=pdf"
        ),
        note=(
            "The official DailyMed AHEALON label states approximately 0.15 mL per spray "
            "and 4-6 sprays per topical administration. This provides a narrow product-"
            "centric delivered-amount anchor of 0.6-0.9 mL per event for herbal topical "
            "spray direct-use workflows."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_activmend_patch_label_2025",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official per-application unit mass for a product-centric herbal recovery patch regimen"
        ),
        targetMetrics=["use_amount_per_event"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["herbal_topical_product"],
        referenceTitle="DailyMed - ActivMend topical patch label",
        referenceLocator=(
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=baefc5d4-a7e4-4ba2-e053-2995a90a4b86"
        ),
        note=(
            "The official DailyMed ActivMend label states 14 g in 1 patch and directions "
            "to wear one patch up to 24 hours. This provides a narrow official-label "
            "unit-mass anchor for product-centric herbal recovery patch direct-use "
            "workflows."
        ),
    ),
    ExternalValidationDataset(
        datasetId="nlm_dailymed_upup_capsicum_patch_label_2025",
        domain="dermal_direct_application",
        status=ExternalValidationDatasetStatus.PARTIAL,
        observable=(
            "official per-application unit mass and active amount for a product-centric "
            "capsicum hydrogel patch regimen"
        ),
        targetMetrics=["use_amount_per_event", "chemical_mass_mg_per_event"],
        applicableTierClaims=[TierLevel.TIER_0],
        productFamilies=["botanical_topical_patch"],
        referenceTitle="DailyMed - UP UP capsicum hydrogel patch label",
        referenceLocator=(
            "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
            "setid=44128b70-3172-ee37-e063-6294a90a705f"
        ),
        note=(
            "The official DailyMed UP UP capsicum hydrogel patch label states 1000 mg in "
            "1 patch and 22 mg capsicum extract per patch. This provides a narrow "
            "official-label unit-mass anchor for product-centric botanical patch direct-"
            "use workflows."
        ),
    ),
    ExternalValidationDataset(
        datasetId="aggregate_external_proxy_candidate",
        domain="aggregate_cross_route_screening",
        status=ExternalValidationDatasetStatus.CANDIDATE_ONLY,
        observable="environmental or biomonitoring proxy comparison",
        targetMetrics=["normalized_total_external_dose"],
        applicableTierClaims=[TierLevel.TIER_0, TierLevel.TIER_1],
        productFamilies=["mixed_use"],
        note=(
            "Candidate family for future cross-route aggregate validation once a population "
            "engine exists."
        ),
    ),
]


def _heuristic_source_ids(registry: DefaultsRegistry) -> list[str]:
    report = build_defaults_curation_report(registry)
    return sorted(
        {
            entry.source_id
            for entry in report.entries
            if entry.curation_status == DefaultsCurationStatus.HEURISTIC
        }
    )


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _open_validation_gaps(registry: DefaultsRegistry) -> list[ValidationGap]:
    heuristic_source_ids = _heuristic_source_ids(registry)
    gaps = [
        ValidationGap(
            gapId="tier1_nf_ff_external_validation_partial_only",
            title="Tier 1 NF/FF external validation is still narrow despite executable support",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["inhalation_near_field_far_field"],
            relatedSourceIds=["benchmark_tier1_nf_ff_parameter_pack_v1"],
            note=(
                "Tier 1 NF/FF spray screening now has benchmark coverage plus a cited "
                "consumer-spray inhalation study and a narrow executable disinfectant "
                "trigger-spray dose anchor, but the dossier still lacks raw time-series "
                "datasets and broader acceptance bands that can be executed against the "
                "NF/FF solver."
            ),
            recommendation=(
                "Add chamber or breathing-zone datasets with raw time-series coverage and "
                "scenario metadata for near-field and far-field concentrations in "
                "personal-care and cleaner spray contexts."
            ),
        ),
        ValidationGap(
            gapId="tier0_spray_external_validation_partial_only",
            title="Tier 0 spray validation is partial and still not executable",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["inhalation_well_mixed_spray"],
            relatedSourceIds=[
                "peer_reviewed_cleaning_trigger_spray_airborne_fraction_2019",
                "rivm_cleaning_sprays_airborne_fraction_2018",
                "rivm_cosmetics_sprays_airborne_fraction_defaults_2025",
                "heuristic_residual_spray_airborne_fraction_defaults_v1",
            ],
            note=(
                "Tier 0 spray screening is benchmark-regressed and now tied to a real "
                "cleaning-spray study for trigger sprays plus an RIVM fact-sheet default for "
                "household-cleaner surface sprays and RIVM cosmetics defaults for personal-care "
                "pump and aerosol sprays. A sparse air-space insecticide aerosol decay series "
                "is now executable, but residual spray product families still rely on "
                "heuristic airborne-fraction defaults and no broad chamber validation family is "
                "wired in beyond a narrow trigger-spray aerosol half-life anchor."
            ),
            recommendation=(
                "Add raw chamber or room-concentration datasets before promoting spray "
                "screening defaults beyond partial reference support."
            ),
        ),
        ValidationGap(
            gapId="residual_air_reentry_validation_narrow_anchor_only",
            title="Residual-air reentry validation is narrowly anchored only",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["inhalation_residual_air_reentry"],
            relatedSourceIds=[
                "chlorpyrifos_broadcast_residential_air_1990",
                "diazinon_office_postapplication_air_1990",
                "diazinon_indoor_air_monitoring_home_use_2008",
            ],
            note=(
                "Residual-air reentry now has a dedicated chlorpyrifos benchmark fixture, "
                "a narrow executable reference check against published post-application indoor "
                "air concentrations at reentry start, and a sparse 4-hour to 24-hour "
                "chlorpyrifos room-air reference pack. The underlying treated-surface "
                "emission, furnishing uptake, and room-decay dynamics are still not externally "
                "validated across indoor-surface insecticide scenarios."
            ),
            recommendation=(
                "Add richer time-resolved post-application room-air datasets with treatment "
                "method, surface loading, ventilation, and furnishing metadata so the "
                "reentry model can be validated beyond the current sparse chlorpyrifos "
                "screening pack."
            ),
        ),
        ValidationGap(
            gapId="dermal_validation_partial_only",
            title="Dermal validation is partial for direct application and thin for transfer",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["dermal_direct_application", "dermal_secondary_transfer"],
            relatedSourceIds=[
                "rivm_cosmetics_hand_cream_direct_application_defaults_2025",
                "rivm_cleaning_surface_contact_retention_defaults_2018",
                "rivm_cleaning_wet_cloth_transfer_defaults_2018",
                "screening_route_semantics_defaults_v1",
                "heuristic_retention_defaults_v1",
                "heuristic_transfer_efficiency_defaults_v1",
            ],
            note=(
                "Dermal direct-application amount realism is now linked to a real workplace "
                "cream-application study, personal-care hand-application and household-cleaner "
                "wet-cloth transfer defaults plus the common household-cleaner surface-contact "
                "retention factor now have curated RIVM anchors, residual surface-contact "
                "retention in other domains still remains a screening default, and only narrow "
                "executable reference checks are wired in for the current secondary-transfer "
                "path."
            ),
            recommendation=(
                "Replace the remaining transfer and retention heuristics with curated packs "
                "tied to product family and external recovery datasets, especially beyond "
                "hand cream and household-cleaner wipe contexts."
            ),
        ),
        ValidationGap(
            gapId="oral_regimen_validation_partial_only",
            title="Direct-oral regimen validation is reference-linked but narrow",
            severity=ValidationGapSeverity.MEDIUM,
            appliesToDomains=["oral_direct_intake"],
            relatedSourceIds=[
                "screening_route_semantics_defaults_v1",
                "heuristic_density_defaults_v1",
                "heuristic_incidental_oral_defaults_v1",
            ],
            note=(
                "Direct-oral screening is benchmarked internally across generic direct-oral, "
                "medicinal-liquid, medicinal tablet, and product-centric supplement capsule "
                "cases, and it now has a narrow executable medicinal-liquid delivered-dose "
                "check plus source-backed medicinal and supplement family context anchors, "
                "but quantitative external validation evidence still comes from a single "
                "medication family rather than a broad oral-product calibration set."
            ),
            recommendation=(
                "Add broader observed dosing or dispensed-amount datasets before broadening "
                "the direct-oral evidence posture beyond medicinal-liquid workflows."
            ),
        ),
        ValidationGap(
            gapId="worker_inhalation_external_validation_partial_only",
            title=(
                "Worker inhalation surrogate execution is benchmarked but not externally validated"
            ),
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["worker_inhalation_control_aware_screening"],
            relatedSourceIds=[
                "worker_art_execution_surrogate_v1",
                "worker_biocidal_spray_foam_inhalation_2023",
            ],
            note=(
                "Worker inhalation execution now has a governed benchmark case for a "
                "janitorial trigger-spray task, a narrow handheld BAC spray concentration "
                "benchmark band, and a source-backed occupational biocidal spray/foam study "
                "anchor, but it remains a surrogate layered on top of screening kernels "
                "rather than an externally validated ART execution."
            ),
            recommendation=(
                "Add reviewed workplace monitoring datasets and determinant mappings for "
                "cleaning-spray worker tasks before claiming external validation maturity."
            ),
        ),
        ValidationGap(
            gapId="worker_dermal_external_validation_partial_only",
            title=("Worker dermal absorbed-dose execution has only narrow external support"),
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["worker_dermal_absorbed_dose_screening"],
            relatedSourceIds=[
                "worker_dermal_absorbed_dose_execution_v1",
                "worker_biocidal_spray_foam_dermal_2023",
            ],
            note=(
                "Worker dermal execution now has a governed benchmark case for gloved wet-wipe "
                "contact plus a source-backed occupational biocidal spray/foam dermal study "
                "anchor and a narrow handheld BAC spray dermal-mass benchmark, but it "
                "remains a generic PPE-aware absorbed-dose screening kernel."
            ),
            recommendation=(
                "Add reviewed dermal loading, glove penetration, and absorbed-dose datasets "
                "for worker wipe and handling tasks before treating the kernel as externally "
                "validated."
            ),
        ),
        ValidationGap(
            gapId="heuristic_defaults_active",
            title="Heuristic defaults remain active in the screening registry",
            severity=ValidationGapSeverity.HIGH,
            appliesToDomains=["global"],
            relatedSourceIds=heuristic_source_ids,
            note=(
                "Some published screening branches still resolve from heuristic bridge defaults "
                "rather than direct curated subtype packs."
            ),
            recommendation=(
                "Prioritize curated replacements for the remaining pest-control trigger-spray "
                "airborne-fraction bridge and subtype-specific aerosol density bridge."
            ),
        ),
    ]
    return gaps


def infer_route_mechanism(scenario: ExposureScenario) -> str:
    profile = scenario.product_use_profile
    if scenario.route == Route.DERMAL:
        if profile.application_method == "wipe":
            return "dermal_secondary_transfer"
        return "dermal_direct_application"
    if scenario.route == Route.ORAL:
        if profile.application_method == "incidental_oral":
            return "oral_incidental_transfer"
        return "oral_direct_intake"
    if profile.application_method == "residual_air_reentry":
        return "inhalation_residual_air_reentry"
    if scenario.tier_semantics.tier_claimed.value == "tier_1":
        return "inhalation_near_field_far_field"
    if profile.application_method in {"trigger_spray", "pump_spray", "aerosol_spray"}:
        return "inhalation_well_mixed_spray"
    return "inhalation_room_average"


def build_validation_dossier_report(
    registry: DefaultsRegistry | None = None,
) -> ValidationDossierReport:
    active_registry = registry or DefaultsRegistry.load()
    fixture = load_benchmark_manifest()
    benchmark_domains: dict[str, list[str]] = {}
    for case in fixture.get("cases", []):
        domain = BENCHMARK_CASE_DOMAINS.get(case["id"], "unclassified")
        benchmark_domains.setdefault(domain, []).append(case["id"])
    domains = [
        ValidationBenchmarkDomain(
            domain=domain,
            caseIds=sorted(case_ids),
            validationStatus=ValidationStatus.BENCHMARK_REGRESSION,
            highestSupportedUncertaintyTier=(
                UncertaintyTier.TIER_C
                if domain == "inhalation_near_field_far_field"
                else UncertaintyTier.TIER_B
            ),
            notes=BENCHMARK_DOMAIN_NOTES.get(domain, []),
        )
        for domain, case_ids in sorted(benchmark_domains.items())
    ]
    return ValidationDossierReport(
        policyVersion="2026.03.25.v4",
        benchmarkDomains=domains,
        externalDatasets=EXTERNAL_VALIDATION_DATASETS,
        heuristicSourceIds=_heuristic_source_ids(active_registry),
        openGaps=_open_validation_gaps(active_registry),
        notes=[
            (
                "Current validation posture is benchmark regression plus verification, "
                "with typed external validation references, benchmark domains, and open "
                "gap tracking."
            ),
            (
                "Reference-linked validation targets are published for inhalation, dermal, "
                "and direct-oral screening, and selected inhalation and dermal scenarios now "
                "support narrow executable reference checks and sparse time-series packs."
            ),
            (
                "Selected dermal scenarios now support narrow executable reference checks "
                "through validationSummary.executedValidationChecks."
            ),
            (
                "Tier 1 inhalation NF/FF screening is implemented for spray scenarios, but "
                "external validation remains a governed future capability rather than an "
                "active pass gate."
            ),
            (
                "Probabilistic tiers remain gated until dependency handling and "
                "external validation mature."
            ),
        ],
    )


def validation_manifest() -> dict:
    return build_validation_dossier_report().model_dump(mode="json", by_alias=True)


def validation_reference_band_manifest() -> dict:
    return ValidationReferenceBandRegistry.load().manifest().model_dump(mode="json", by_alias=True)


def validation_time_series_reference_manifest() -> dict:
    return (
        ValidationTimeSeriesReferenceRegistry.load()
        .manifest()
        .model_dump(
            mode="json",
            by_alias=True,
        )
    )


def _coverage_level(
    *,
    benchmark_case_ids: list[str],
    executable_reference_band_ids: list[str],
    time_series_pack_ids: list[str],
    external_dataset_ids: list[str],
) -> str:
    if benchmark_case_ids and time_series_pack_ids:
        return "benchmark_time_resolved"
    if benchmark_case_ids and executable_reference_band_ids:
        return "benchmark_plus_executable_references"
    if benchmark_case_ids:
        return "benchmark_only"
    if external_dataset_ids:
        return "source_backed_only"
    return "verification_only"


def build_validation_coverage_report() -> ValidationCoverageReport:
    dossier = build_validation_dossier_report()
    benchmark_fixture = load_benchmark_manifest()
    goldset = load_goldset_manifest()
    reference_manifest = ValidationReferenceBandRegistry.load().manifest()
    time_series_manifest = ValidationTimeSeriesReferenceRegistry.load().manifest()

    benchmark_domains = {item.domain: item for item in dossier.benchmark_domains}
    benchmark_case_ids_by_domain: dict[str, list[str]] = {}
    for case in benchmark_fixture.get("cases", []):
        domain = BENCHMARK_CASE_DOMAINS.get(str(case["id"]))
        if domain is None:
            continue
        benchmark_case_ids_by_domain.setdefault(domain, []).append(str(case["id"]))

    goldset_coverage_counts: dict[str, int] = {}
    goldset_case_ids_by_domain: dict[str, set[str]] = {}
    unmapped_goldset_case_ids: list[str] = []
    for case in goldset.get("cases", []):
        coverage_status = str(case.get("coverage_status", "unknown"))
        goldset_coverage_counts[coverage_status] = (
            goldset_coverage_counts.get(coverage_status, 0) + 1
        )
        linked_domains = {
            BENCHMARK_CASE_DOMAINS[item]
            for item in case.get("benchmark_case_ids", [])
            if item in BENCHMARK_CASE_DOMAINS
        }
        if not linked_domains:
            unmapped_goldset_case_ids.append(str(case["id"]))
            continue
        for domain in linked_domains:
            goldset_case_ids_by_domain.setdefault(domain, set()).add(str(case["id"]))

    external_dataset_ids_by_domain: dict[str, list[str]] = {}
    for item in dossier.external_datasets:
        external_dataset_ids_by_domain.setdefault(item.domain, []).append(item.dataset_id)

    reference_band_ids_by_domain: dict[str, list[str]] = {}
    for item in reference_manifest.bands:
        reference_band_ids_by_domain.setdefault(item.domain, []).append(item.check_id)

    time_series_pack_ids_by_domain: dict[str, list[str]] = {}
    for item in time_series_manifest.packs:
        time_series_pack_ids_by_domain.setdefault(item.domain, []).append(item.reference_pack_id)

    open_gap_ids_by_domain: dict[str, list[str]] = {}
    global_gap_ids: list[str] = []
    for item in dossier.open_gaps:
        applied = False
        for domain in item.applies_to_domains:
            if domain == "global":
                global_gap_ids.append(item.gap_id)
                continue
            open_gap_ids_by_domain.setdefault(domain, []).append(item.gap_id)
            applied = True
        if not item.applies_to_domains or not applied:
            global_gap_ids.append(item.gap_id)

    all_domains = sorted(
        {
            *benchmark_domains.keys(),
            *external_dataset_ids_by_domain.keys(),
            *reference_band_ids_by_domain.keys(),
            *time_series_pack_ids_by_domain.keys(),
            *open_gap_ids_by_domain.keys(),
        }
    )

    domain_summaries: list[ValidationCoverageDomainSummary] = []
    for domain in all_domains:
        benchmark_case_ids = sorted(benchmark_case_ids_by_domain.get(domain, []))
        goldset_case_ids = sorted(goldset_case_ids_by_domain.get(domain, set()))
        external_dataset_ids = sorted(external_dataset_ids_by_domain.get(domain, []))
        reference_band_ids = sorted(reference_band_ids_by_domain.get(domain, []))
        time_series_pack_ids = sorted(time_series_pack_ids_by_domain.get(domain, []))
        open_gap_ids = sorted(open_gap_ids_by_domain.get(domain, []))
        benchmark_domain = benchmark_domains.get(domain)
        highest_tier = (
            benchmark_domain.highest_supported_uncertainty_tier
            if benchmark_domain is not None
            else UncertaintyTier.TIER_A
        )
        coverage_level = _coverage_level(
            benchmark_case_ids=benchmark_case_ids,
            executable_reference_band_ids=reference_band_ids,
            time_series_pack_ids=time_series_pack_ids,
            external_dataset_ids=external_dataset_ids,
        )
        summary_parts = [
            f"{len(benchmark_case_ids)} benchmark case(s)",
            f"{len(external_dataset_ids)} external dataset(s)",
            f"{len(reference_band_ids)} executable reference band(s)",
            f"{len(time_series_pack_ids)} time-series pack(s)",
            f"{len(open_gap_ids)} open gap(s)",
        ]
        domain_summaries.append(
            ValidationCoverageDomainSummary(
                domain=domain,
                coverageLevel=coverage_level,
                highestSupportedUncertaintyTier=highest_tier,
                benchmarkCaseCount=len(benchmark_case_ids),
                benchmarkCaseIds=benchmark_case_ids,
                goldsetCaseCount=len(goldset_case_ids),
                goldsetCaseIds=goldset_case_ids,
                externalDatasetCount=len(external_dataset_ids),
                externalDatasetIds=external_dataset_ids,
                executableReferenceBandCount=len(reference_band_ids),
                executableReferenceBandIds=reference_band_ids,
                timeSeriesPackCount=len(time_series_pack_ids),
                timeSeriesPackIds=time_series_pack_ids,
                openGapCount=len(open_gap_ids),
                openGapIds=open_gap_ids,
                summary=", ".join(summary_parts) + ".",
            )
        )

    notes = [
        (
            "Coverage is derived from the governed benchmark corpus, showcase goldset, "
            "validation dossier, executable reference-band manifest, and executable "
            "time-series manifest."
        ),
        (
            "Coverage levels describe current trust posture by domain; they do not "
            "imply full scientific validation or regulatory acceptance."
        ),
    ]
    if global_gap_ids:
        notes.append(
            "Global validation gaps still active across the stack: "
            + ", ".join(f"`{item}`" for item in sorted(set(global_gap_ids)))
            + "."
        )
    if unmapped_goldset_case_ids:
        notes.append(
            (
                "Some goldset cases remain integration-only or challenge-only and "
                "therefore do not map to a benchmark domain summary: "
            )
            + ", ".join(f"`{item}`" for item in sorted(unmapped_goldset_case_ids))
            + "."
        )

    return ValidationCoverageReport(
        policyVersion=dossier.policy_version,
        benchmarkDefaultsVersion=str(benchmark_fixture.get("defaults_version", "unknown")),
        referenceBandVersion=reference_manifest.reference_version,
        timeSeriesReferenceVersion=time_series_manifest.reference_version,
        goldsetVersion=str(goldset.get("goldset_version", "unknown")),
        domainCount=len(domain_summaries),
        benchmarkCaseCount=len(benchmark_fixture.get("cases", [])),
        externalDatasetCount=len(dossier.external_datasets),
        referenceBandCount=reference_manifest.band_count,
        timeSeriesPackCount=time_series_manifest.pack_count,
        goldsetCaseCount=len(goldset.get("cases", [])),
        goldsetCoverageCounts=goldset_coverage_counts,
        unmappedGoldsetCaseIds=sorted(unmapped_goldset_case_ids),
        domainSummaries=domain_summaries,
        overallNotes=notes,
    )


def _evidence_readiness(
    benchmark_case_ids: list[str],
    datasets: list[ExternalValidationDataset],
) -> ValidationEvidenceReadiness:
    statuses = {item.status for item in datasets}
    if ExternalValidationDatasetStatus.ACCEPTED_REFERENCE in statuses:
        return ValidationEvidenceReadiness.CALIBRATED
    if ExternalValidationDatasetStatus.PARTIAL in statuses:
        return ValidationEvidenceReadiness.EXTERNAL_PARTIAL
    if benchmark_case_ids and datasets:
        return ValidationEvidenceReadiness.BENCHMARK_PLUS_EXTERNAL_CANDIDATES
    if datasets:
        return ValidationEvidenceReadiness.EXTERNAL_CANDIDATES_ONLY
    return ValidationEvidenceReadiness.BENCHMARK_ONLY


def _scenario_validation_gap_ids(
    scenario: ExposureScenario,
    route_mechanism: str,
    *,
    heuristic_assumption_names: list[str],
    dossier: ValidationDossierReport,
) -> list[str]:
    gap_ids: list[str] = []
    for gap in dossier.open_gaps:
        if gap.gap_id == "heuristic_defaults_active" and not heuristic_assumption_names:
            continue
        if "global" in gap.applies_to_domains or route_mechanism in gap.applies_to_domains:
            gap_ids.append(gap.gap_id)
    return gap_ids


def _assumption_value(scenario: ExposureScenario, name: str) -> float | None:
    for item in scenario.assumptions:
        if item.name == name and isinstance(item.value, int | float):
            return float(item.value)
    return None


def _dataset_matches_scenario(
    scenario: ExposureScenario, dataset: ExternalValidationDataset
) -> bool:
    if dataset.domain != infer_route_mechanism(scenario):
        return False

    families = set(dataset.product_families)
    if not families or "mixed_use" in families:
        return True

    profile = scenario.product_use_profile
    scenario_families = {
        profile.product_category,
        profile.product_category.lower(),
    }
    if profile.product_subtype is not None:
        scenario_families.add(profile.product_subtype)
        scenario_families.add(profile.product_subtype.lower())
    return any(item in scenario_families for item in families)


def _selector_matches_scenario(
    scenario: ExposureScenario,
    *,
    key: str,
    expected_value: ScalarValue,
) -> bool:
    if expected_value is None:
        return True
    profile = scenario.product_use_profile
    if key == "product_category":
        return _normalized_text(profile.product_category) == _normalized_text(str(expected_value))
    if key == "product_subtype":
        return _normalized_text(profile.product_subtype) == _normalized_text(str(expected_value))
    if key == "physical_form":
        return _normalized_text(profile.physical_form) == _normalized_text(str(expected_value))
    if key == "application_method":
        return _normalized_text(profile.application_method) == _normalized_text(str(expected_value))
    if key == "retention_type":
        return _normalized_text(profile.retention_type) == _normalized_text(str(expected_value))
    if key == "intended_use_family":
        return _normalized_text(
            profile.intended_use_family.value if profile.intended_use_family else None
        ) == _normalized_text(str(expected_value))
    if key == "oral_exposure_context":
        return _normalized_text(
            profile.oral_exposure_context.value if profile.oral_exposure_context else None
        ) == _normalized_text(str(expected_value))
    if key == "application_coverage_context":
        return _normalized_text(profile.application_coverage_context) == _normalized_text(
            str(expected_value)
        )
    if key == "chemical_id":
        return _normalized_text(scenario.chemical_id) == _normalized_text(str(expected_value))
    if key == "chemical_name":
        return _normalized_text(scenario.chemical_name) == _normalized_text(str(expected_value))
    if key == "region":
        return _normalized_text(scenario.population_profile.region) == _normalized_text(
            str(expected_value)
        )
    if key == "population_group":
        return _normalized_text(scenario.population_profile.population_group) == _normalized_text(
            str(expected_value)
        )
    if key == "demographic_tag":
        return _normalized_text(str(expected_value)) in {
            _normalized_text(item) for item in scenario.population_profile.demographic_tags
        }
    if key == "reentry_mode":
        return _normalized_text(
            str(scenario.route_metrics.get("reentry_mode"))
        ) == _normalized_text(str(expected_value))
    return True


def _selectors_match_scenario(
    scenario: ExposureScenario,
    selectors: dict[str, ScalarValue],
) -> bool:
    return all(
        _selector_matches_scenario(scenario, key=key, expected_value=value)
        for key, value in selectors.items()
    )


def _scenario_time_coordinate_hours(
    scenario: ExposureScenario,
    *,
    metric_key: str,
) -> float | None:
    route_mechanism = infer_route_mechanism(scenario)
    if route_mechanism == "inhalation_well_mixed_spray":
        if metric_key != "air_concentration_at_event_end_mg_per_m3":
            return None
        exposure_duration_hours = _assumption_value(scenario, "exposure_duration_hours")
        if exposure_duration_hours is None:
            raw_duration = scenario.route_metrics.get("exposure_duration_hours")
            if isinstance(raw_duration, int | float):
                exposure_duration_hours = float(raw_duration)
        if exposure_duration_hours is None:
            exposure_duration_hours = scenario.product_use_profile.exposure_duration_hours
        return exposure_duration_hours

    if route_mechanism != "inhalation_residual_air_reentry":
        return None
    post_application_delay_hours = _assumption_value(scenario, "post_application_delay_hours")
    if post_application_delay_hours is None:
        raw_delay = scenario.route_metrics.get("post_application_delay_hours")
        if isinstance(raw_delay, int | float):
            post_application_delay_hours = float(raw_delay)
    if post_application_delay_hours is None:
        return None
    if metric_key == "air_concentration_at_reentry_start_mg_per_m3":
        return post_application_delay_hours
    if metric_key == "air_concentration_at_reentry_end_mg_per_m3":
        exposure_duration_hours = _assumption_value(scenario, "exposure_duration_hours")
        if exposure_duration_hours is None:
            raw_duration = scenario.route_metrics.get("exposure_duration_hours")
            if isinstance(raw_duration, int | float):
                exposure_duration_hours = float(raw_duration)
        if exposure_duration_hours is None:
            exposure_duration_hours = scenario.product_use_profile.exposure_duration_hours
        if exposure_duration_hours is None:
            return None
        return post_application_delay_hours + exposure_duration_hours
    return None


def _executed_time_series_checks(
    scenario: ExposureScenario,
    *,
    existing_check_ids: set[str],
) -> list[ExecutedValidationCheck]:
    if infer_route_mechanism(scenario) not in {
        "inhalation_residual_air_reentry",
        "inhalation_well_mixed_spray",
    }:
        return []
    checks: list[ExecutedValidationCheck] = []
    manifest = ValidationTimeSeriesReferenceRegistry.load().manifest()
    for pack in manifest.packs:
        if pack.domain != infer_route_mechanism(scenario):
            continue
        if not _selectors_match_scenario(scenario, pack.applicable_selectors):
            continue
        for point in pack.points:
            if point.check_id in existing_check_ids:
                continue
            time_coordinate_hours = _scenario_time_coordinate_hours(
                scenario,
                metric_key=point.scenario_metric_key,
            )
            if time_coordinate_hours is None or not math.isclose(
                time_coordinate_hours,
                point.time_coordinate_hours,
                abs_tol=0.5,
            ):
                continue
            observed_value = scenario.route_metrics.get(point.scenario_metric_key)
            if not isinstance(observed_value, int | float):
                continue
            status = (
                ValidationCheckStatus.PASS
                if point.reference_lower <= float(observed_value) <= point.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId=point.check_id,
                    title=point.title,
                    referenceDatasetId=pack.reference_dataset_id,
                    status=status,
                    comparedMetric=point.scenario_metric_key,
                    observedValue=round(float(observed_value), 8),
                    referenceLower=point.reference_lower,
                    referenceUpper=point.reference_upper,
                    unit=point.unit,
                    note=point.note,
                )
            )
    return checks


def _executed_validation_checks(scenario: ExposureScenario) -> list[ExecutedValidationCheck]:
    profile = scenario.product_use_profile
    checks: list[ExecutedValidationCheck] = []
    reference_registry = ValidationReferenceBandRegistry.load()

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "personal_care"
        and profile.physical_form == "cream"
        and profile.application_method == "hand_application"
        and profile.retention_type == "leave_on"
    ):
        exposed_area = _assumption_value(scenario, "exposed_surface_area_cm2")
        product_mass_g_event = _assumption_value(scenario, "product_mass_g_per_event")
        if (
            exposed_area is not None
            and product_mass_g_event is not None
            and 700.0 <= exposed_area <= 1200.0
        ):
            reference_band = reference_registry.band_for_check(
                "hand_cream_application_loading_2012"
            )
            observed = (product_mass_g_event * 1000.0) / exposed_area
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower <= observed <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="hand_cream_application_loading_2012",
                    title="Hand cream application loading vs nurse workplace study",
                    referenceDatasetId="skin_protection_cream_dose_per_area_2012",
                    status=status,
                    comparedMetric="product_loading_mg_per_cm2_per_event",
                    observedValue=round(observed, 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed hand-cream application loading is compared against the "
                        "reported mean ± SD band from Schliemann et al. when the supplied "
                        "exposed area is hand-scale."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "herbal_topical_product"
        and profile.application_method == "hand_application"
        and profile.retention_type == "leave_on"
        and profile.application_coverage_context == "palm_sized_area"
    ):
        strip_length = scenario.route_metrics.get("application_strip_length_cm")
        if isinstance(strip_length, int | float):
            reference_band = reference_registry.band_for_check(
                "herbal_topical_application_strip_length_2014"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(strip_length)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="herbal_topical_application_strip_length_2014",
                    title="Topical herbal strip length vs EMA palm-area arnica application anchor",
                    referenceDatasetId="ema_arnica_topical_application_geometry_2014",
                    status=status,
                    comparedMetric="application_strip_length_cm",
                    observedValue=round(float(strip_length), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed topical strip length is compared against a narrow "
                        "palm-sized-area herbal topical analogue anchor centered on the 3 cm "
                        "application instruction captured in the EMA arnica comment overview. "
                        "This is an application-geometry realism check, not a mass-per-use "
                        "calibration set."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "herbal_topical_product"
        and profile.physical_form == "ointment"
        and profile.application_method == "hand_application"
        and profile.retention_type == "leave_on"
        and profile.intended_use_family == "medicinal"
    ):
        observed = scenario.route_metrics.get("product_loading_mg_per_cm2_per_event")
        if isinstance(observed, int | float):
            reference_band = reference_registry.band_for_check(
                "ema_hmpc_topical_ointment_loading_default"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(observed)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="ema_hmpc_topical_ointment_loading_default",
                    title="Topical herbal ointment loading vs EMA HMPC safety default",
                    referenceDatasetId="ema_hmpc_herbal_medicinal_safety_default_2024",
                    status=status,
                    comparedMetric="product_loading_mg_per_cm2_per_event",
                    observedValue=round(float(observed), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed product loading is compared against the standard 1-2 mg/cm2 "
                        "EMA HMPC safety-assessment default frequently used in HMPC "
                        "assessment reports for systemic exposure calculations."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "personal_care"
        and profile.physical_form == "balm"
        and profile.application_method == "hand_application"
        and profile.retention_type == "leave_on"
    ):
        observed = scenario.route_metrics.get("product_loading_mg_per_cm2_per_event")
        if isinstance(observed, int | float):
            reference_band = reference_registry.band_for_check(
                "sccs_cosmetic_balm_loading_category"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(observed)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="sccs_cosmetic_balm_loading_category",
                    title="Cosmetic balm loading vs SCCS category-default anchor",
                    referenceDatasetId="sccs_notes_of_guidance_12th_revision_2022",
                    status=status,
                    comparedMetric="product_loading_mg_per_cm2_per_event",
                    observedValue=round(float(observed), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed product loading is compared against the derived 2.5-2.7 mg/cm2 "
                        "SCCS category-specific loading anchor for face and hand balms."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.application_method == "hand_application"
        and profile.application_coverage_context == "two_hand_prints_area"
    ):
        observed = scenario.route_metrics.get("product_loading_mg_per_cm2_per_event")
        if isinstance(observed, int | float):
            reference_band = reference_registry.band_for_check(
                "dermatology_fingertip_unit_loading_anchor"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(observed)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="dermatology_fingertip_unit_loading_anchor",
                    title="Topical loading vs dermatology Fingertip Unit (FTU) anchor",
                    referenceDatasetId="clinical_dermatology_ftu_standard_method_1991",
                    status=status,
                    comparedMetric="product_loading_mg_per_cm2_per_event",
                    observedValue=round(float(observed), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed product loading is compared against the clinical dermatology "
                        "Fingertip Unit (FTU) loading anchor of approximately 1.67 mg/cm2."
                    ),
                )
            )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "herbal_topical_product"
        and profile.product_subtype == "herbal_topical_spray"
        and profile.application_method == "pump_spray"
        and profile.retention_type == "leave_on"
        and profile.use_amount_unit == ProductAmountUnit.ML
    ):
        observed = float(profile.use_amount_per_event)
        reference_band = reference_registry.band_for_check("herbal_topical_spray_label_amount_2026")
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="herbal_topical_spray_label_amount_2026",
                title="Topical herbal spray delivered amount vs DailyMed label",
                referenceDatasetId="nlm_dailymed_ahealon_topical_spray_label_2026",
                status=status,
                comparedMetric="use_amount_per_event",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed use_amount_per_event is compared against the official "
                    "DailyMed AHEALON topical-spray instruction of approximately 0.15 mL "
                    "per spray and 4-6 sprays per application, giving a 0.6-0.9 mL/event "
                    "delivered-amount anchor."
                ),
            )
        )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "herbal_topical_product"
        and profile.product_subtype == "herbal_recovery_patch"
        and profile.application_method == "patch_application"
        and profile.retention_type == "leave_on"
        and profile.use_amount_unit == ProductAmountUnit.G
    ):
        observed = float(profile.use_amount_per_event)
        reference_band = reference_registry.band_for_check(
            "herbal_recovery_patch_label_amount_2025"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="herbal_recovery_patch_label_amount_2025",
                title="Herbal recovery patch unit mass vs DailyMed label",
                referenceDatasetId="nlm_dailymed_activmend_patch_label_2025",
                status=status,
                comparedMetric="use_amount_per_event",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed use_amount_per_event is compared against the official "
                    "DailyMed ActivMend label stating 14 g in 1 patch with one patch worn "
                    "up to 24 hours, giving a narrow herbal recovery patch unit-mass anchor."
                ),
            )
        )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "botanical_topical_patch"
        and profile.product_subtype == "capsicum_hydrogel_patch"
        and profile.application_method == "patch_application"
        and profile.retention_type == "leave_on"
        and profile.use_amount_unit == ProductAmountUnit.G
    ):
        observed = float(profile.use_amount_per_event)
        reference_band = reference_registry.band_for_check(
            "capsicum_hydrogel_patch_label_amount_2025"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="capsicum_hydrogel_patch_label_amount_2025",
                title="Capsicum hydrogel patch unit mass vs DailyMed label",
                referenceDatasetId="nlm_dailymed_upup_capsicum_patch_label_2025",
                status=status,
                comparedMetric="use_amount_per_event",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed use_amount_per_event is compared against the official "
                    "DailyMed UP UP capsicum hydrogel patch label stating 1000 mg in 1 "
                    "patch, giving a narrow botanical patch unit-mass anchor."
                ),
            )
        )

    if (
        scenario.route == Route.DERMAL
        and profile.product_category == "household_cleaner"
        and profile.application_method == "wipe"
        and profile.retention_type == "surface_contact"
        and profile.concentration_fraction > 0.0
        and profile.use_events_per_day > 0.0
    ):
        reference_band = reference_registry.band_for_check("wet_cloth_contact_mass_2018")
        external_mass_mg_day = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        observed = external_mass_mg_day / (
            1000.0 * profile.concentration_fraction * profile.use_events_per_day
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="wet_cloth_contact_mass_2018",
                title="Wet-cloth cleaner contact mass vs RIVM cleaning-product scenarios",
                referenceDatasetId="rivm_wet_cloth_dermal_contact_loading_2018",
                status=status,
                comparedMetric="product_contact_mass_g_per_event",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed product mass at the skin boundary is compared against RIVM "
                    "wet-cloth contact amounts derived for household cleaning scenarios."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "medicinal_liquid"
        and profile.physical_form == "liquid"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "medicinal_liquid_direct_oral_delivered_mass_2025"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="medicinal_liquid_direct_oral_delivered_mass_2025",
                title="Medicinal-liquid delivered dose vs ready-to-use vigabatrin study",
                referenceDatasetId="vigabatrin_ready_to_use_dosing_accuracy_2025",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the 1125 mg target "
                    "dose with a +/-5% band, matching the delivered-dose accuracy envelope "
                    "reported for the ready-to-use vigabatrin solution."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "herbal_medicinal_product"
        and profile.product_subtype == "valerian_root_extract"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "herbal_medicinal_valerian_oral_daily_mass_2015"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="herbal_medicinal_valerian_oral_daily_mass_2015",
                title="Herbal medicinal oral daily mass vs EMA valerian monograph posology",
                referenceDatasetId="ema_valerian_root_oral_posology_2015",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the EMA HMPC "
                    "valerian dry-extract oral posology envelope of 450-600 mg per dose "
                    "up to 3 times daily, giving a 1350-1800 mg/day narrow direct-use "
                    "herbal medicinal benchmark band."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "herbal_medicinal_product"
        and profile.product_subtype == "valerian_root_infusion"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "herbal_medicinal_valerian_infusion_daily_mass_2015"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="herbal_medicinal_valerian_infusion_daily_mass_2015",
                title="Herbal medicinal infusion daily mass vs EMA valerian monograph posology",
                referenceDatasetId="ema_valerian_root_infusion_posology_2015",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the EMA HMPC "
                    "valerian herbal-tea oral posology envelope of 0.3-3.0 g comminuted "
                    "herbal substance per dose up to 3 times daily, giving a 900-9000 "
                    "mg/day medicinal infusion/decoction benchmark band."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "dietary_supplement"
        and profile.product_subtype == "iron_capsule"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "dietary_supplement_iron_capsule_daily_mass_2025"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="dietary_supplement_iron_capsule_daily_mass_2025",
                title="Dietary supplement capsule daily mass vs official DailyMed label",
                referenceDatasetId="nlm_dailymed_sideral_iron_capsule_label_2025",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the official "
                    "DailyMed SIDERAL label stating one 100 mg capsule per day "
                    "delivering 30 mg elemental iron, giving a narrow 30 mg/day "
                    "product-centric supplement benchmark anchor."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "dietary_supplement"
        and profile.product_subtype == "melatonin_gummy"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "dietary_supplement_melatonin_gummy_daily_mass_2026"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="dietary_supplement_melatonin_gummy_daily_mass_2026",
                title="Dietary supplement gummy daily mass vs official DailyMed label",
                referenceDatasetId="nlm_dailymed_melatonin_gummy_label_2026",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the official "
                    "DailyMed label stating 2 gummies per day delivering 5 mg melatonin, "
                    "giving a narrow 5 mg/day product-centric supplement benchmark anchor."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "botanical_supplement"
        and profile.product_subtype == "echinacea_tincture"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "botanical_supplement_echinacea_tincture_daily_mass_2026"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="botanical_supplement_echinacea_tincture_daily_mass_2026",
                title="Botanical supplement tincture daily mass vs official DailyMed label",
                referenceDatasetId="nlm_dailymed_echinacea_tincture_label_2026",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the official "
                    "DailyMed label stating 1 mL per day delivering 250 mg extract, "
                    "giving a narrow 250 mg/day product-centric supplement benchmark anchor."
                ),
            )
        )

    if (
        scenario.route == Route.ORAL
        and profile.product_category == "dietary_supplement"
        and profile.product_subtype == "vitamin_c_effervescent"
        and profile.application_method == "direct_oral"
    ):
        observed = float(scenario.route_metrics.get("external_mass_mg_per_day", 0.0))
        reference_band = reference_registry.band_for_check(
            "dietary_supplement_effervescent_vitaminc_daily_mass_2026"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="dietary_supplement_effervescent_vitaminc_daily_mass_2026",
                title="Dietary supplement effervescent daily mass vs official DailyMed label",
                referenceDatasetId="nlm_dailymed_vitaminc_effervescent_label_2026",
                status=status,
                comparedMetric="external_mass_mg_per_day",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed external_mass_mg_per_day is compared against the official "
                    "DailyMed label stating 1 tablet per day delivering 1000 mg Vitamin C, "
                    "giving a narrow 1000 mg/day product-centric supplement benchmark anchor."
                ),
            )
        )

    if (
        scenario.route == Route.INHALATION
        and profile.product_category == "household_cleaner"
        and profile.physical_form == "spray"
        and profile.application_method == "trigger_spray"
    ):
        observed = _assumption_value(scenario, "aerosolized_fraction")
        if observed is not None:
            reference_band = reference_registry.band_for_check(
                "cleaning_trigger_spray_airborne_fraction_2019"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower <= observed <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="cleaning_trigger_spray_airborne_fraction_2019",
                    title=(
                        "Trigger-spray cleaner airborne fraction vs ready-to-use cleaning "
                        "spray study"
                    ),
                    referenceDatasetId="cleaning_trigger_spray_airborne_mass_fraction_2019",
                    status=status,
                    comparedMetric="aerosolized_fraction",
                    observedValue=round(observed, 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed aerosolized_fraction is compared against the reported "
                        "2.7%-32.2% airborne-mass range for ready-to-use trigger cleaning "
                        "sprays."
                    ),
                )
            )

        half_life = scenario.route_metrics.get("room_air_decay_half_life_hours")
        if isinstance(half_life, int | float):
            reference_band = reference_registry.band_for_check(
                "trigger_spray_aerosol_decay_half_life_2023"
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower
                <= float(half_life)
                <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="trigger_spray_aerosol_decay_half_life_2023",
                    title=("Trigger-spray aerosol decay half-life vs climate-chamber spray study"),
                    referenceDatasetId="spray_cleaning_disinfection_decay_half_life_2023",
                    status=status,
                    comparedMetric="room_air_decay_half_life_hours",
                    observedValue=round(float(half_life), 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed room-air decay half-life is compared against a screening "
                        "band centered on the reported 0.25 h average trigger-spray aerosol "
                        "half-life from the 2023 cleaning and disinfection spray chamber study."
                    ),
                )
            )

    if infer_route_mechanism(scenario) == "inhalation_near_field_far_field":
        reference_band = reference_registry.band_for_check(
            "consumer_disinfectant_trigger_spray_inhaled_dose_2015"
        )
        if _selectors_match_scenario(scenario, reference_band.applicable_selectors):
            observed = float(scenario.external_dose.value)
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower <= observed <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId="consumer_disinfectant_trigger_spray_inhaled_dose_2015",
                    title=("Tier 1 disinfectant trigger-spray dose vs consumer inhalation study"),
                    referenceDatasetId="consumer_disinfectant_trigger_spray_inhalation_2015",
                    status=status,
                    comparedMetric="normalized_external_dose",
                    observedValue=round(observed, 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=(
                        "Observed normalized external dose is compared against the "
                        "supplementary disinfectant trigger-spray inhalation exposure band "
                        "reported in the 2015 consumer spray study, converted from "
                        "ng/kg bw/application to mg/kg-day for a one-event screening case."
                    ),
                )
            )

    if (
        scenario.route == Route.INHALATION
        and profile.product_subtype == "air_space_insecticide"
        and profile.application_method == "aerosol_spray"
        and profile.product_category in {"pesticide", "pest_control"}
        and math.isclose(float(profile.exposure_duration_hours or 0.0), 4.0, abs_tol=1e-9)
    ):
        observed = float(scenario.route_metrics.get("average_air_concentration_mg_per_m3", 0.0))
        reference_band = reference_registry.band_for_check(
            "air_space_insecticide_aerosol_concentration_2001"
        )
        status = (
            ValidationCheckStatus.PASS
            if reference_band.reference_lower <= observed <= reference_band.reference_upper
            else ValidationCheckStatus.WARNING
        )
        checks.append(
            ExecutedValidationCheck(
                checkId="air_space_insecticide_aerosol_concentration_2001",
                title=(
                    "Air-space insecticide aerosol concentration vs household mosquito "
                    "aerosol study"
                ),
                referenceDatasetId="household_mosquito_aerosol_indoor_air_2001",
                status=status,
                comparedMetric="average_air_concentration_mg_per_m3",
                observedValue=round(observed, 8),
                referenceLower=reference_band.reference_lower,
                referenceUpper=reference_band.reference_upper,
                unit=reference_band.unit,
                note=(
                    "Observed room-average air concentration is compared against a narrow "
                    "4-hour screening proxy derived from reported indoor prallethrin aerosol "
                    "room-air measurements in a closed-room household mosquito aerosol study."
                ),
            )
        )

    if (
        scenario.route == Route.INHALATION
        and profile.product_subtype == "indoor_surface_insecticide"
        and profile.application_method == "residual_air_reentry"
        and profile.product_category in {"pesticide", "pest_control"}
    ):
        for check_id, title, dataset_id, note in (
            (
                "chlorpyrifos_residual_air_reentry_start_concentration_1990",
                (
                    "Residual-air reentry start concentration vs chlorpyrifos residential "
                    "broadcast study"
                ),
                "chlorpyrifos_broadcast_residential_air_1990",
                (
                    "Observed reentry-start room-air concentration is compared against the "
                    "reported 61-94 ug/m3 chlorpyrifos band from the residential broadcast "
                    "study, converted to mg/m3. This is a narrow anchor for the dedicated "
                    "residual-air reentry path, not a full treated-surface emission validation."
                ),
            ),
            (
                "diazinon_home_use_residual_air_concentration_2008",
                "Residual-air reentry start concentration vs diazinon home-use indoor-air anchor",
                "diazinon_indoor_air_monitoring_home_use_2008",
                (
                    "Observed reentry-start room-air concentration is compared against a "
                    "narrow 13 ug/m3 home-use diazinon indoor-air anchor derived from the "
                    "NPIC technical fact sheet. This is a bounded consumer home-use screening "
                    "anchor, not a chamber-resolved trigger-spray benchmark."
                ),
            ),
        ):
            reference_band = reference_registry.band_for_check(check_id)
            if not _selectors_match_scenario(scenario, reference_band.applicable_selectors):
                continue
            observed = float(
                scenario.route_metrics.get("air_concentration_at_reentry_start_mg_per_m3", 0.0)
            )
            status = (
                ValidationCheckStatus.PASS
                if reference_band.reference_lower <= observed <= reference_band.reference_upper
                else ValidationCheckStatus.WARNING
            )
            checks.append(
                ExecutedValidationCheck(
                    checkId=check_id,
                    title=title,
                    referenceDatasetId=dataset_id,
                    status=status,
                    comparedMetric="air_concentration_at_reentry_start_mg_per_m3",
                    observedValue=round(observed, 8),
                    referenceLower=reference_band.reference_lower,
                    referenceUpper=reference_band.reference_upper,
                    unit=reference_band.unit,
                    note=note,
                )
            )

    checks.extend(
        _executed_time_series_checks(
            scenario,
            existing_check_ids={item.check_id for item in checks},
        )
    )

    return checks


def build_validation_summary(scenario: ExposureScenario) -> ValidationSummary:
    route_mechanism = infer_route_mechanism(scenario)
    dossier = build_validation_dossier_report()
    benchmark_case_ids: list[str] = []
    highest_supported_tier = UncertaintyTier.TIER_B
    for item in dossier.benchmark_domains:
        if item.domain == route_mechanism:
            benchmark_case_ids = list(item.case_ids)
            highest_supported_tier = item.highest_supported_uncertainty_tier
            break
    matched_datasets = [
        item for item in dossier.external_datasets if _dataset_matches_scenario(scenario, item)
    ]
    external_dataset_ids = [item.dataset_id for item in matched_datasets]
    heuristic_assumption_names = sorted(
        item.name
        for item in scenario.assumptions
        if is_warning_heuristic_source_id(item.source.source_id)
    )
    executed_validation_checks = _executed_validation_checks(scenario)
    validation_status = (
        ValidationStatus.BENCHMARK_REGRESSION
        if benchmark_case_ids
        else ValidationStatus.VERIFICATION_ONLY
    )
    return ValidationSummary(
        validation_status=validation_status,
        route_mechanism=route_mechanism,
        benchmark_case_ids=benchmark_case_ids,
        external_dataset_ids=external_dataset_ids,
        evidence_readiness=_evidence_readiness(benchmark_case_ids, matched_datasets),
        heuristic_assumption_names=heuristic_assumption_names,
        validation_gap_ids=_scenario_validation_gap_ids(
            scenario,
            route_mechanism,
            heuristic_assumption_names=heuristic_assumption_names,
            dossier=dossier,
        ),
        executed_validation_checks=executed_validation_checks,
        highest_supported_uncertainty_tier=highest_supported_tier,
        probabilistic_enablement="blocked",
        notes=[
            "Deterministic verification and benchmark regression are available for this domain.",
            (
                "External validation remains a documented future capability rather than "
                "an active gate."
            ),
            (
                "Heuristic assumption names are emitted explicitly so evidence gaps stay "
                "attached to the scenario rather than hidden in source packs."
            ),
            (
                "Probabilistic outputs stay disabled until dependencies and validation "
                "evidence mature."
            ),
        ]
        + (
            [
                (
                    "Executable validation checks were run because the scenario matched one "
                    "or more published reference patterns."
                )
            ]
            if executed_validation_checks
            else []
        ),
    )
