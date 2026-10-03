"""Population-profile plausibility screening: bands, scenario flags, and downstream surfacing."""

from __future__ import annotations

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry, defaults_evidence_map
from exposure_scenario_mcp.guidance import provenance_policy, troubleshooting_guide
from exposure_scenario_mcp.integrations import check_pbpk_compatibility
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    CompareJurisdictionalScenariosInput,
    ExportPbpkScenarioInputRequest,
    ExposureScenario,
    ExposureScenarioRequest,
    InhalationScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    QualityFlag,
    Route,
    ScenarioClass,
    Severity,
    TierLevel,
)
from exposure_scenario_mcp.plugins import InhalationScreeningPlugin, ScreeningScenarioPlugin
from exposure_scenario_mcp.population_plausibility import (
    FIELD_UNITS,
    GENERIC_BAND_SCOPE,
    POPULATION_PLAUSIBILITY_VERSION,
    PopulationPlausibilityBand,
    evaluate_population_value,
    plausibility_band,
    population_plausibility_bands,
)
from exposure_scenario_mcp.provenance import AssumptionTracker
from exposure_scenario_mcp.runtime import (
    PluginRegistry,
    ScenarioEngine,
    aggregate_scenarios,
    compare_jurisdictional_scenarios,
    export_pbpk_input,
)

REPORTED_BODY_WEIGHT_KG = 6691.76


def build_engine() -> ScenarioEngine:
    registry = PluginRegistry()
    registry.register(ScreeningScenarioPlugin())
    registry.register(InhalationScreeningPlugin())
    return ScenarioEngine(registry=registry, defaults_registry=DefaultsRegistry.load())


def oral_request(
    body_weight_kg: float | None, *, population_group: str = "adult"
) -> ExposureScenarioRequest:
    # Every factor is explicit, so a plausible build carries no quality flags at all --
    # the shape of the reported case that silently returned `quality_flags: []`.
    return ExposureScenarioRequest(
        chemical_id="TCM-PLAUSIBILITY-001",
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
            ingestion_fraction=1.0,
        ),
        population_profile=PopulationProfile(
            population_group=population_group,
            body_weight_kg=body_weight_kg,
            region="EU",
        ),
    )


def dermal_request(
    *,
    population_group: str = "adult",
    region: str = "global",
    body_weight_kg: float | None = None,
    exposed_surface_area_cm2: float | None = None,
) -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id="TCM-PLAUSIBILITY-001",
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
        population_profile=PopulationProfile(
            population_group=population_group,
            body_weight_kg=body_weight_kg,
            exposed_surface_area_cm2=exposed_surface_area_cm2,
            region=region,
        ),
    )


def flag_codes(scenario, severity: Severity) -> set[str]:
    return {flag.code for flag in scenario.quality_flags if flag.severity == severity}


def population_codes(items) -> set[str]:
    return {item.code for item in items if item.code.startswith("population_")}


def test_every_shipped_population_default_sits_inside_its_typical_band() -> None:
    populations = DefaultsRegistry.load().payload["population_defaults"]
    regions = {"global": populations["global"], **populations["regional_overrides"]}

    checked = 0
    for region, groups in regions.items():
        for population_group, entry in groups.items():
            for field_name in FIELD_UNITS:
                band = plausibility_band(field_name, population_group)
                assert band is not None
                assert band.band_scope == population_group, (region, population_group)
                finding = evaluate_population_value(
                    field_name, float(entry[field_name]), population_group
                )
                assert finding is None, (region, population_group, field_name)
                checked += 1

    assert checked == len(FIELD_UNITS) * sum(len(groups) for groups in regions.values())


@pytest.mark.parametrize(
    "band",
    population_plausibility_bands(),
    ids=lambda band: f"{band.field_name}-{band.band_scope}",
)
def test_typical_bands_nest_inside_physiological_envelopes(
    band: PopulationPlausibilityBand,
) -> None:
    if band.typical_lower is not None:
        assert band.physiological_lower is not None
        assert band.physiological_lower < band.typical_lower
    if band.typical_upper is not None:
        assert band.typical_upper < band.physiological_upper


@pytest.mark.parametrize("field_name", sorted(FIELD_UNITS))
def test_generic_envelope_never_screens_tighter_than_a_registered_group(field_name: str) -> None:
    generic = plausibility_band(field_name, "astronaut")
    assert generic is not None
    assert generic.band_scope == GENERIC_BAND_SCOPE
    assert generic.typical_lower is None
    assert generic.typical_upper is None
    for band in population_plausibility_bands():
        if band.field_name != field_name or band.band_scope == GENERIC_BAND_SCOPE:
            continue
        assert band.physiological_upper <= generic.physiological_upper
        if band.physiological_lower is not None:
            assert generic.physiological_lower is not None
            assert generic.physiological_lower <= band.physiological_lower


@pytest.mark.parametrize(
    ("value", "expected_code"),
    [
        (35.0, None),
        (150.0, None),
        (34.9, "population_body_weight_atypical"),
        (150.1, "population_body_weight_atypical"),
        (20.0, "population_body_weight_atypical"),
        (250.0, "population_body_weight_atypical"),
        (19.9, "population_body_weight_implausible"),
        (250.1, "population_body_weight_implausible"),
        (REPORTED_BODY_WEIGHT_KG, "population_body_weight_implausible"),
    ],
)
def test_adult_body_weight_band_edges_are_inclusive(
    value: float, expected_code: str | None
) -> None:
    finding = evaluate_population_value("body_weight_kg", value, "adult")

    if expected_code is None:
        assert finding is None
        return
    assert finding is not None
    assert finding.code == expected_code
    expected_severity = (
        Severity.ERROR if expected_code.endswith("implausible") else Severity.WARNING
    )
    assert finding.severity == expected_severity


@pytest.mark.parametrize(
    ("field_name", "value", "population_group", "expected_code"),
    [
        # Adult weight entered for a child, and a decimal shift of the 15 kg child default.
        ("body_weight_kg", 70.0, "child", "population_body_weight_atypical"),
        ("body_weight_kg", 150.0, "child", "population_body_weight_implausible"),
        # Toddler weight entered for an infant; adult weight entered for an infant.
        ("body_weight_kg", 15.0, "infant", "population_body_weight_atypical"),
        ("body_weight_kg", 75.0, "infant", "population_body_weight_implausible"),
        ("body_weight_kg", 0.2, "infant", "population_body_weight_implausible"),
        # Exposed skin area against the whole-body maximum (mm2 entered as cm2).
        ("exposed_surface_area_cm2", 30000.0, "adult", "population_exposed_surface_area_atypical"),
        (
            "exposed_surface_area_cm2",
            570000.0,
            "adult",
            "population_exposed_surface_area_implausible",
        ),
        (
            "exposed_surface_area_cm2",
            9000.0,
            "infant",
            "population_exposed_surface_area_implausible",
        ),
        # Daily volume (m3/day) and per-minute rate (m3/min) entered as hourly rates.
        ("inhalation_rate_m3_per_hour", 16.0, "adult", "population_inhalation_rate_implausible"),
        ("inhalation_rate_m3_per_hour", 6.0, "adult", "population_inhalation_rate_atypical"),
        ("inhalation_rate_m3_per_hour", 0.012, "adult", "population_inhalation_rate_implausible"),
        # Unregistered groups are still held to the generic human envelope.
        ("body_weight_kg", REPORTED_BODY_WEIGHT_KG, "worker", "population_body_weight_implausible"),
    ],
)
def test_population_values_outside_their_group_band_are_classified(
    field_name: str, value: float, population_group: str, expected_code: str
) -> None:
    finding = evaluate_population_value(field_name, value, population_group)

    assert finding is not None
    assert finding.code == expected_code
    assert f"{field_name}={value:g}" in finding.message
    assert f"'{population_group}'" in finding.message


def test_band_lookup_normalizes_group_and_leaves_small_exposed_areas_unbounded() -> None:
    finding = evaluate_population_value("body_weight_kg", REPORTED_BODY_WEIGHT_KG, " Adult ")

    assert finding is not None
    assert finding.band.band_scope == "adult"
    # A spot application on a few square centimetres is legitimate: no lower area bound.
    assert evaluate_population_value("exposed_surface_area_cm2", 1.0, "infant") is None
    # Generic envelope has no typical tier, so unregistered groups get no warnings.
    assert evaluate_population_value("body_weight_kg", 180.0, "worker") is None


def test_reported_adult_body_weight_raises_error_flag_limitation_and_failed_checks() -> None:
    engine = build_engine()
    plausible = engine.build(oral_request(70.0))
    reported = engine.build(oral_request(REPORTED_BODY_WEIGHT_KG))

    assert plausible.quality_flags == []
    assert plausible.tier_semantics.assumption_checks_passed is True

    # The build is not blocked and the arithmetic is unchanged ...
    assert reported.external_dose.value == pytest.approx(
        plausible.external_dose.value * 70.0 / REPORTED_BODY_WEIGHT_KG, rel=1e-6
    )
    # ... but the scenario can no longer look clean.
    assert flag_codes(reported, Severity.ERROR) == {"population_body_weight_implausible"}
    flag = next(
        item for item in reported.quality_flags if item.code == "population_body_weight_implausible"
    )
    assert "6691.76 kg (user-supplied)" in flag.message
    assert "20-250 kg" in flag.message
    assert [(item.code, item.severity) for item in reported.limitations] == [
        ("population_body_weight_implausible", Severity.ERROR)
    ]
    assert reported.tier_semantics.assumption_checks_passed is False
    assert any(
        "population_body_weight_implausible" in caveat
        for caveat in reported.tier_semantics.required_caveats
    )
    assert reported.validation_summary is not None
    assert any(
        "`population_body_weight_implausible`" in note for note in reported.validation_summary.notes
    )
    register = {entry.entry_id: entry for entry in reported.uncertainty_register}
    entry = register["limitation-population_body_weight_implausible"]
    assert entry.impact_level == "high"


def test_atypical_adult_body_weight_warns_without_failing_checks() -> None:
    scenario = build_engine().build(oral_request(180.0))

    assert flag_codes(scenario, Severity.WARNING) == {"population_body_weight_atypical"}
    assert flag_codes(scenario, Severity.ERROR) == set()
    assert scenario.limitations == []
    assert scenario.tier_semantics.assumption_checks_passed is True


@pytest.mark.parametrize("population_group", ["adult", "child", "infant"])
@pytest.mark.parametrize("region", ["global", "china"])
def test_defaulted_population_values_never_trip_plausibility_flags(
    population_group: str, region: str
) -> None:
    scenario = build_engine().build(
        dermal_request(population_group=population_group, region=region)
    )

    assert population_codes(scenario.quality_flags) == set()
    assert scenario.tier_semantics.assumption_checks_passed is True


def test_dermal_exposed_area_above_whole_body_maximum_is_flagged() -> None:
    scenario = build_engine().build(
        dermal_request(body_weight_kg=70.0, exposed_surface_area_cm2=570000.0)
    )

    assert flag_codes(scenario, Severity.ERROR) == {"population_exposed_surface_area_implausible"}
    assert population_codes(scenario.limitations) == {"population_exposed_surface_area_implausible"}
    assert scenario.tier_semantics.assumption_checks_passed is False


def test_inhalation_rate_entered_as_daily_volume_is_flagged() -> None:
    request = InhalationScenarioRequest(
        chemical_id="DTXSID123",
        route=Route.INHALATION,
        product_use_profile=ProductUseProfile(
            product_category="household_cleaner",
            physical_form="spray",
            application_method="trigger_spray",
            retention_type="surface_contact",
            concentration_fraction=0.05,
            use_amount_per_event=12,
            use_amount_unit="mL",
            use_events_per_day=1,
            room_volume_m3=25,
        ),
        population_profile=PopulationProfile(
            population_group="adult",
            body_weight_kg=68,
            inhalation_rate_m3_per_hour=16.0,
        ),
    )

    scenario = build_engine().build(request)

    assert flag_codes(scenario, Severity.ERROR) == {"population_inhalation_rate_implausible"}
    assert scenario.tier_semantics.assumption_checks_passed is False


def aggregate_of(*components: ExposureScenario):
    return aggregate_scenarios(
        BuildAggregateExposureScenarioInput(
            chemical_id="TCM-PLAUSIBILITY-001",
            label="Plausibility aggregate",
            component_scenarios=list(components),
        ),
        DefaultsRegistry.load(),
    )


def test_aggregate_surfaces_implausible_component_population() -> None:
    engine = build_engine()
    reported = engine.build(oral_request(REPORTED_BODY_WEIGHT_KG))
    plausible = engine.build(oral_request(70.0))

    aggregate = aggregate_of(reported, plausible)

    flags = [flag for flag in aggregate.quality_flags if flag.code.startswith("population_")]
    assert [(flag.code, flag.severity) for flag in flags] == [
        ("population_body_weight_implausible", Severity.ERROR)
    ]
    assert f"`{reported.scenario_id}`" in flags[0].message
    assert [(item.code, item.severity) for item in aggregate.limitations] == [
        ("aggregate_component_population_implausible", Severity.ERROR)
    ]
    register = {entry.entry_id: entry for entry in aggregate.uncertainty_register}
    assert register["aggregate-component-population-implausible"].related_assumptions == [
        "body_weight_kg"
    ]
    assert aggregate.validation_summary is not None
    assert any(reported.scenario_id in note for note in aggregate.validation_summary.notes)


def test_aggregate_rescreens_components_whose_flags_were_dropped() -> None:
    reported = build_engine().build(oral_request(REPORTED_BODY_WEIGHT_KG))
    stripped = reported.model_copy(update={"quality_flags": [], "limitations": []})

    aggregate = aggregate_of(stripped)

    assert population_codes(aggregate.quality_flags) == {"population_body_weight_implausible"}
    assert {item.code for item in aggregate.limitations} == {
        "aggregate_component_population_implausible"
    }


def test_aggregate_of_plausible_components_is_unchanged() -> None:
    engine = build_engine()
    aggregate = aggregate_of(engine.build(oral_request(70.0)), engine.build(dermal_request()))

    assert population_codes(aggregate.quality_flags) == set()
    assert "aggregate_component_population_implausible" not in {
        item.code for item in aggregate.limitations
    }
    assert [entry.entry_id for entry in aggregate.uncertainty_register] == [
        "aggregate-screening-summary"
    ]


def test_aggregate_carries_atypical_component_as_warning_only() -> None:
    aggregate = aggregate_of(build_engine().build(oral_request(180.0)))

    assert [
        (flag.code, flag.severity)
        for flag in aggregate.quality_flags
        if flag.code.startswith("population_")
    ] == [("population_body_weight_atypical", Severity.WARNING)]
    assert aggregate.limitations == []


def test_pbpk_handoffs_refuse_implausible_population_context() -> None:
    engine = build_engine()
    reported = engine.build(oral_request(REPORTED_BODY_WEIGHT_KG))

    report = check_pbpk_compatibility(reported)
    assert report.compatible is False
    assert report.ready_for_external_pbpk_import is False
    assert "pbpk_population_context_implausible" in {
        issue.code for issue in report.issues if issue.severity == Severity.ERROR
    }

    pbpk_input = export_pbpk_input(
        ExportPbpkScenarioInputRequest(scenario=reported), DefaultsRegistry.load()
    )
    assert [(item.code, item.severity) for item in pbpk_input.limitations] == [
        ("pbpk_population_context_implausible", Severity.ERROR)
    ]

    plausible_report = check_pbpk_compatibility(engine.build(oral_request(70.0)))
    assert "pbpk_population_context_implausible" not in {
        issue.code for issue in plausible_report.issues
    }


def test_jurisdictional_comparison_keeps_the_error_flag_per_jurisdiction() -> None:
    result = compare_jurisdictional_scenarios(
        CompareJurisdictionalScenariosInput(
            request=oral_request(REPORTED_BODY_WEIGHT_KG),
            jurisdictions=["global", "china"],
        ),
        engine=build_engine(),
    )

    assert {flag.code for flag in result.quality_flags if flag.severity == Severity.ERROR} == {
        "global_population_body_weight_implausible",
        "china_population_body_weight_implausible",
    }


def test_bands_and_policy_are_published_through_docs_resources() -> None:
    evidence_map = defaults_evidence_map()

    assert f"`{POPULATION_PLAUSIBILITY_VERSION}`" in evidence_map
    for band in population_plausibility_bands():
        assert f"`{band.field_name}` / `{band.band_scope}`" in evidence_map
    assert "population_<field>_implausible" in provenance_policy()
    assert "pbpk_population_context_implausible" in troubleshooting_guide()


def test_tier_semantics_cannot_report_passed_checks_over_error_flags() -> None:
    tracker = AssumptionTracker(registry=DefaultsRegistry.load())
    tracker.quality_flags.append(
        QualityFlag(code="example_error", severity=Severity.ERROR, message="Example.")
    )

    semantics = tracker.tier_semantics(
        tier_claimed=TierLevel.TIER_0,
        tier_rationale="Example rationale.",
        required_caveats=["Existing caveat."],
        assumption_checks_passed=True,
    )

    assert semantics.assumption_checks_passed is False
    assert semantics.required_caveats[0] == "Existing caveat."
    assert "example_error" in semantics.required_caveats[-1]


def test_pbpk_rescreens_calculation_values_after_profile_and_flags_are_stripped() -> None:
    engine = build_engine()
    scenario = engine.build(oral_request(REPORTED_BODY_WEIGHT_KG))
    scenario = scenario.model_copy(
        update={
            "population_profile": scenario.population_profile.model_copy(
                update={"body_weight_kg": 70.0}
            ),
            "quality_flags": [],
            "limitations": [],
        }
    )
    compatibility = check_pbpk_compatibility(scenario)
    assert not compatibility.ready_for_external_pbpk_import
    assert any(item.code == "pbpk_population_context_implausible" for item in compatibility.issues)


def test_pbpk_rescreens_implausible_dermal_area() -> None:
    scenario = build_engine().build(dermal_request(exposed_surface_area_cm2=66917.6))
    compatibility = check_pbpk_compatibility(scenario)
    assert not compatibility.ready_for_external_pbpk_import
    assert any(item.code == "pbpk_population_context_implausible" for item in compatibility.issues)
