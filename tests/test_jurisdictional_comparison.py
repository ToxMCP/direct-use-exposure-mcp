"""Tests for cross-jurisdictional comparison system."""

import pytest

from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.models import (
    CompareJurisdictionalScenariosInput,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
)
from exposure_scenario_mcp.runtime import compare_jurisdictional_scenarios


def _build_request(region: str = "global") -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="TCM-COMPARE-001",
        route=Route.ORAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="herbal_medicinal_product",
            physical_form="solid",
            application_method="direct_oral",
            retention_type="leave_on",
            concentration_fraction=0.05,
            use_amount_per_event=0.5,
            use_amount_unit="g",
            use_events_per_day=2,
        ),
        population_profile=PopulationProfile(population_group="adult", region=region),
    )


def _build_dermal_request(region: str = "global") -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="TCM-COMPARE-DERMAL-001",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category="personal_care",
            physical_form="cream",
            application_method="hand_application",
            retention_type="leave_on",
            concentration_fraction=0.02,
            use_amount_per_event=1.5,
            use_amount_unit="g",
            use_events_per_day=3,
        ),
        population_profile=PopulationProfile(population_group="adult", region=region),
    )


def test_compare_global_and_china() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "china"],
    )
    result = compare_jurisdictional_scenarios(input_data)

    assert len(result.external_dose_by_jurisdiction) == 2
    assert "global" in result.external_dose_by_jurisdiction
    assert "china" in result.external_dose_by_jurisdiction

    global_dose = result.external_dose_by_jurisdiction["global"].value
    china_dose = result.external_dose_by_jurisdiction["china"].value
    assert china_dose > global_dose

    # Dose range
    assert result.dose_range.minimum_value == pytest.approx(global_dose, rel=1e-6)
    assert result.dose_range.maximum_value == pytest.approx(china_dose, rel=1e-6)
    assert result.dose_range.minimum_jurisdiction == "global"
    assert result.dose_range.maximum_jurisdiction == "china"

    # Variance drivers should include body_weight_kg
    driver_names = {d.assumption_name for d in result.variance_drivers}
    assert "body_weight_kg" in driver_names

    # Harmonization opportunity should be present
    assert result.harmonization_opportunity is not None
    assert "body_weight_kg" in result.harmonization_opportunity

    assert result.provenance.algorithm_id == "scenario.compare_jurisdictional.v1"
    assert result.fit_for_purpose.label == "jurisdictional_comparison_screening"
    assert "jurisdictional_comparison_screening" in {item.code for item in result.limitations}

    # Uncertainty register
    assert len(result.uncertainty_register) == 1
    assert result.uncertainty_register[0].entry_id == "inter-jurisdictional-population-variance"

    flag_codes = {item.code for item in result.quality_flags}
    assert "china_regional_population_override_active" in flag_codes
    assert "jurisdictional_variance_detected" in flag_codes


def test_compare_three_jurisdictions() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "eu", "china"],
    )
    result = compare_jurisdictional_scenarios(input_data)

    assert len(result.external_dose_by_jurisdiction) == 3
    # China (63 kg) > EU (room defaults only, population falls back to global 80 kg)
    # Actually EU doesn't have population overrides, so EU adult = global adult = 80 kg
    # But EU room defaults differ. For oral, room defaults don't affect dose.
    # So global and EU should have the same dose, China should be higher.
    global_dose = result.external_dose_by_jurisdiction["global"].value
    eu_dose = result.external_dose_by_jurisdiction["eu"].value
    china_dose = result.external_dose_by_jurisdiction["china"].value
    assert global_dose == pytest.approx(eu_dose, rel=1e-6)
    assert china_dose > global_dose


def test_unsupported_jurisdiction_raises_error() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["mars"],
    )
    with pytest.raises(ExposureScenarioError) as exc_info:
        compare_jurisdictional_scenarios(input_data)
    assert exc_info.value.code == "jurisdiction_not_supported"


def test_mixed_supported_and_unsupported_jurisdiction_raises_error() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "china", "chnia"],
    )
    with pytest.raises(ExposureScenarioError) as exc_info:
        compare_jurisdictional_scenarios(input_data)
    assert exc_info.value.code == "jurisdiction_not_supported"


def test_duplicate_jurisdiction_raises_error() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "china", "global"],
    )
    with pytest.raises(ExposureScenarioError) as exc_info:
        compare_jurisdictional_scenarios(input_data)
    assert exc_info.value.code == "jurisdiction_duplicate_requested"


def test_variance_driver_ranking_is_deterministic_and_excludes_derived_values() -> None:
    request = _build_dermal_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "china"],
    )
    result = compare_jurisdictional_scenarios(input_data)

    driver_names = [driver.assumption_name for driver in result.variance_drivers]
    assert "chemical_loading_mg_per_cm2_per_event" not in driver_names
    assert driver_names[0] == "exposed_surface_area_cm2"
    assert result.harmonization_opportunity is not None
    assert "exposed_surface_area_cm2" in result.harmonization_opportunity


def test_comparison_id_is_present() -> None:
    request = _build_request()
    input_data = CompareJurisdictionalScenariosInput(
        request=request,
        jurisdictions=["global", "china"],
    )
    result = compare_jurisdictional_scenarios(input_data)
    assert result.comparison_id.startswith("jurisdictional-comparison-")
