from __future__ import annotations

from exposure_scenario_mcp.benchmarks import load_benchmark_manifest, load_goldset_manifest


def test_goldset_manifest_is_source_backed_and_links_to_real_benchmarks() -> None:
    goldset = load_goldset_manifest()
    benchmark_ids = {case["id"] for case in load_benchmark_manifest()["cases"]}

    assert goldset["schema_version"] == "benchmarkGoldsetManifest.v1"
    assert goldset["goldset_version"] == "2026.04.13.v22"
    assert len(goldset["cases"]) >= 6

    coverage_statuses = {case["coverage_status"] for case in goldset["cases"]}
    assert {
        "benchmark_regressed_showcase",
        "integration_showcase",
        "challenge_case",
    } <= coverage_statuses

    for case in goldset["cases"]:
        assert case["external_sources"], case["id"]
        assert case["challenge_tags"], case["id"]
        assert case["why_it_matters"], case["id"]
        assert case["showcase_story"], case["id"]
        for source in case["external_sources"]:
            assert source["source_id"], case["id"]
            assert source["title"], case["id"]
            assert source["locator"].startswith("http"), case["id"]
        for benchmark_id in case.get("benchmark_case_ids", []):
            assert benchmark_id in benchmark_ids, (case["id"], benchmark_id)

    benchmark_regressed = [
        case
        for case in goldset["cases"]
        if case["coverage_status"] == "benchmark_regressed_showcase"
    ]
    assert benchmark_regressed
    assert all(case["benchmark_case_ids"] for case in benchmark_regressed)
    chlorpyrifos_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "chlorpyrifos_indoor_surface_insecticide_reentry"
    )
    assert {
        "inhalation_residual_air_reentry_chlorpyrifos_screening",
        "inhalation_residual_air_reentry_chlorpyrifos_time_series_1990",
    } <= set(chlorpyrifos_case["benchmark_case_ids"])
    diazinon_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "diazinon_office_postapplication_reentry"
    )
    assert diazinon_case["benchmark_case_ids"] == [
        "inhalation_residual_air_reentry_diazinon_time_series_1990"
    ]
    diazinon_workflow_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "eu_diazinon_indoor_surface_insecticide"
    )
    assert set(diazinon_workflow_case["benchmark_case_ids"]) == {
        "inhalation_residual_air_reentry_diazinon_home_use_native_screening",
        "inhalation_residual_air_reentry_diazinon_time_series_1990",
        "inhalation_residual_air_reentry_native_treated_surface_screening",
    }
    handheld_worker_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "worker_handheld_biocidal_trigger_spray_monitoring"
    )
    assert handheld_worker_case["benchmark_case_ids"] == [
        "worker_inhalation_handheld_biocidal_trigger_spray_execution"
    ]
    disinfectant_consumer_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "consumer_disinfectant_trigger_spray_tier1_monitoring"
    )
    assert disinfectant_consumer_case["benchmark_case_ids"] == [
        "inhalation_tier1_disinfectant_trigger_spray_external_2015"
    ]
    dermal_worker_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "worker_biocidal_spray_dermal_contact"
    )
    assert dermal_worker_case["benchmark_case_ids"] == [
        "worker_dermal_handheld_biocidal_trigger_spray_execution"
    ]
    face_cream_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "consumer_face_cream_sccs_guidance_alignment"
    )
    assert face_cream_case["benchmark_case_ids"] == ["dermal_face_cream_sccs_screening"]
    tcm_oral_case = next(
        case for case in goldset["cases"] if case["id"] == "tcm_medicinal_oral_regimen"
    )
    assert tcm_oral_case["benchmark_case_ids"] == [
        "oral_tcm_medicinal_direct_use_screening"
    ]
    supplement_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "botanical_supplement_direct_use_capsule"
    )
    assert supplement_case["benchmark_case_ids"] == [
        "oral_botanical_supplement_direct_use_screening"
    ]
    label_supplement_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "dietary_supplement_capsule_label_alignment"
    )
    assert label_supplement_case["benchmark_case_ids"] == [
        "oral_dietary_supplement_iron_capsule_label_screening"
    ]
    valerian_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "eu_herbal_medicinal_oral_posology_alignment"
    )
    assert valerian_case["benchmark_case_ids"] == [
        "oral_herbal_medicinal_valerian_posology_screening"
    ]
    valerian_infusion_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "eu_herbal_medicinal_infusion_posology_alignment"
    )
    assert valerian_infusion_case["benchmark_case_ids"] == [
        "oral_herbal_medicinal_valerian_infusion_posology_screening"
    ]
    tcm_balm_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "tcm_topical_balm_direct_application"
    )
    assert tcm_balm_case["benchmark_case_ids"] == ["dermal_tcm_topical_balm_screening"]
    topical_spray_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "herbal_topical_spray_label_amount_alignment"
    )
    assert topical_spray_case["benchmark_case_ids"] == [
        "dermal_herbal_topical_spray_label_amount_screening"
    ]
    herbal_patch_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "herbal_recovery_patch_label_amount_alignment"
    )
    assert herbal_patch_case["benchmark_case_ids"] == [
        "dermal_herbal_recovery_patch_label_amount_screening"
    ]
    capsicum_patch_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "capsicum_hydrogel_patch_label_amount_alignment"
    )
    assert capsicum_patch_case["benchmark_case_ids"] == [
        "dermal_capsicum_hydrogel_patch_label_amount_screening"
    ]
    aerosol_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "consumer_mosquito_aerosol_room_air_validation"
    )
    assert set(aerosol_case["benchmark_case_ids"]) >= {
        "inhalation_air_space_insecticide_aerosol_screening",
        "inhalation_air_space_insecticide_aerosol_time_series_0p75h_2001",
        "inhalation_air_space_insecticide_aerosol_time_series_6h_2001",
    }
    aerosol_challenge_case = next(
        case
        for case in goldset["cases"]
        if case["id"] == "consumer_air_space_insecticide_aerosol"
    )
    assert set(aerosol_challenge_case["benchmark_case_ids"]) >= {
        "inhalation_air_space_insecticide_aerosol_screening",
        "inhalation_air_space_insecticide_aerosol_time_series_0p75h_2001",
        "inhalation_air_space_insecticide_aerosol_time_series_6h_2001",
    }

    challenge_cases = [
        case for case in goldset["cases"] if case["coverage_status"] == "challenge_case"
    ]
    assert challenge_cases
    assert all(case["evidence_gaps"] for case in challenge_cases)
