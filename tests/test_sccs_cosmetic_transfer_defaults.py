"""SCCS-anchored transfer-efficiency defaults for cosmetic application methods.

Reference: SCCS Notes of Guidance 12th revision (SCCS/1647/22, corrigendum 2 of
21 December 2023).

- Section 3-3.4.2.1: the tabulated daily amounts qx (Tables 3A/3B) are amounts applied to
  the skin and Eproduct = qx x fret, with no separate transfer term, so the personal_care
  transfer efficiency for these application methods is 1.0.
- Section 3-3.4.3, Table 5: 17 product categories aggregate to 17.4 g/d and 269 mg/kg bw/d
  of product. Oral-care Eproduct is treated there as dermal (mucosal) exposure, so every
  component below is built on the dermal route.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest

from exposure_scenario_mcp.defaults import DefaultsRegistry, build_defaults_curation_report
from exposure_scenario_mcp.errors import ExposureScenarioError
from exposure_scenario_mcp.integrations import (
    SccsCosmeticsEvidenceRecord,
    build_product_use_evidence_from_sccs,
    reconcile_product_use_evidence,
)
from exposure_scenario_mcp.models import (
    BuildAggregateExposureScenarioInput,
    DefaultsCurationStatus,
    DefaultVisibility,
    EvidenceBasis,
    EvidenceGrade,
    ExposureAssumptionRecord,
    ExposureScenario,
    ExposureScenarioRequest,
    PopulationProfile,
    ProductUseProfile,
    Route,
    ScenarioClass,
    SourceKind,
)
from exposure_scenario_mcp.runtime import ScenarioEngine, aggregate_scenarios
from exposure_scenario_mcp.server_runtime import build_server_runtime_state

SCCS_TRANSFER_SOURCE_ID = "sccs_cosmetics_applied_amount_transfer_defaults_2023"
RIVM_HAND_APPLICATION_SOURCE_ID = "rivm_cosmetics_hand_cream_direct_application_defaults_2025"
SCCS_COSMETIC_METHODS = (
    "direct_application",
    "applicator",
    "pad_application",
    "brushing",
    "oral_rinse",
)
SCCS_DEFAULT_BODY_WEIGHT_KG = 60.0
PRODUCT_EXPOSURE_ID = "sccs-nog12-table5-product"
# SCCS fret for the leave-on and rinse-off classes, which the defaults pack resolves from
# retention_type; product-specific fret values are supplied explicitly per row.
SCCS_CLASS_FRET = {"leave_on": 1.0, "rinse_off": 0.01}


class SccsTable5Row(NamedTuple):
    product: str
    physical_form: str
    application_method: str
    retention_type: str
    explicit_fret: float | None
    qx_g_per_day: float
    qx_per_bw_mg_per_kg_day: float | None
    table5_g_per_day: float
    table5_mg_per_kg_bw_day: float

    @property
    def fret(self) -> float:
        if self.explicit_fret is not None:
            return self.explicit_fret
        return SCCS_CLASS_FRET[self.retention_type]


# Columns: product, physical form, application method, retention type, explicit fret (None =
# retention_type default), qx (g/d), qx/bw (mg/kg bw/d; None where SCCS used the 60 kg default
# body weight), Table 5 Eproduct (g/d), Table 5 Eproduct/bw (mg/kg bw/d).
SCCS_TABLE_5 = (
    # Rinse-off skin and hair cleansing products
    SccsTable5Row(
        "Shower gel", "gel", "hand_application", "rinse_off", None, 18.67, 279.20, 0.19, 2.79
    ),
    # Hand wash soap is listed only in Table 5: qx = Eproduct 0.20 g/d / rinse-off fret 0.01.
    SccsTable5Row(
        "Hand wash soap", "liquid", "hand_application", "rinse_off", None, 20.0, None, 0.20, 3.33
    ),
    SccsTable5Row(
        "Shampoo", "liquid", "hand_application", "rinse_off", None, 10.46, 150.49, 0.11, 1.51
    ),
    SccsTable5Row(
        "Hair conditioner", "cream", "hand_application", "rinse_off", None, 3.92, None, 0.04, 0.67
    ),
    # Leave-on skin and hair care products
    SccsTable5Row(
        "Body lotion", "lotion", "hand_application", "leave_on", None, 7.82, 123.2, 7.82, 123.20
    ),
    SccsTable5Row(
        "Face cream", "cream", "hand_application", "leave_on", None, 1.54, 24.14, 1.54, 24.14
    ),
    SccsTable5Row(
        "Hand cream", "cream", "hand_application", "leave_on", None, 2.16, 32.70, 2.16, 32.70
    ),
    SccsTable5Row(
        "Deodorant non-spray",
        "stick",
        "direct_application",
        "leave_on",
        None,
        1.50,
        22.08,
        1.50,
        22.08,
    ),
    SccsTable5Row(
        "Hair styling", "gel", "hand_application", "leave_on", 0.10, 4.00, 57.4, 0.40, 5.74
    ),
    # Make-up products
    SccsTable5Row(
        "Liquid foundation", "liquid", "hand_application", "leave_on", None, 0.51, 7.90, 0.51, 7.90
    ),
    SccsTable5Row(
        "Make-up remover", "liquid", "pad_application", "rinse_off", 0.10, 5.00, None, 0.50, 8.33
    ),
    SccsTable5Row(
        "Lipstick", "stick", "direct_application", "leave_on", None, 0.057, 0.90, 0.06, 0.90
    ),
    SccsTable5Row("Eye make-up", "powder", "applicator", "leave_on", None, 0.02, None, 0.02, 0.33),
    SccsTable5Row("Mascara", "liquid", "applicator", "leave_on", None, 0.025, None, 0.025, 0.42),
    SccsTable5Row("Eyeliner", "liquid", "applicator", "leave_on", None, 0.005, None, 0.005, 0.08),
    # Oral care products (dermal/mucosal exposure in Table 5)
    SccsTable5Row("Toothpaste", "paste", "brushing", "rinse_off", 0.05, 2.75, 43.29, 0.14, 2.16),
    SccsTable5Row(
        "Mouthwash", "liquid", "oral_rinse", "rinse_off", 0.10, 21.62, 325.40, 2.16, 32.54
    ),
)
SCCS_TABLE_5_AGGREGATE_G_PER_DAY = 17.4
SCCS_TABLE_5_AGGREGATE_MG_PER_KG_BW_DAY = 269.0
# Table 5 prints two decimals and is not fully self-consistent at that precision: SCCS divides
# the displayed hair-conditioner Eproduct (0.04 g/d) rather than 3.92 g/d x 0.01 by 60 kg, and
# prints shampoo as 0.11 g/d and 1.51 mg/kg bw/d where qx x fret gives 0.1046 and 1.5049.
TABLE_5_ROW_TOLERANCE_MG_PER_KG_BW_DAY = 0.02
TABLE_5_ROW_TOLERANCE_G_PER_DAY = 0.01


@pytest.fixture(scope="module")
def engine() -> ScenarioEngine:
    return build_server_runtime_state().engine


def _cosmetic_request(
    *,
    application_method: str,
    product_category: str = "personal_care",
    route: Route = Route.DERMAL,
    retention_type: str = "leave_on",
    transfer_efficiency: float | None = None,
) -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id=PRODUCT_EXPOSURE_ID,
        route=route,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_category=product_category,
            physical_form="liquid",
            application_method=application_method,
            retention_type=retention_type,
            concentration_fraction=1.0,
            use_amount_per_event=1.0,
            use_amount_unit="g",
            use_events_per_day=1.0,
            transfer_efficiency=transfer_efficiency,
        ),
        population_profile=PopulationProfile(
            population_group="adult", body_weight_kg=SCCS_DEFAULT_BODY_WEIGHT_KG
        ),
    )


def _table5_request(row: SccsTable5Row, *, use_amount_g: float) -> ExposureScenarioRequest:
    return ExposureScenarioRequest(
        chemical_id=PRODUCT_EXPOSURE_ID,
        chemical_name="Finished cosmetic product (C = 100%)",
        route=Route.DERMAL,
        scenario_class=ScenarioClass.SCREENING,
        product_use_profile=ProductUseProfile(
            product_name=row.product,
            product_category="personal_care",
            physical_form=row.physical_form,
            application_method=row.application_method,
            retention_type=row.retention_type,
            retention_factor=row.explicit_fret,
            concentration_fraction=1.0,
            use_amount_per_event=use_amount_g,
            use_amount_unit="g",
            use_events_per_day=1.0,
        ),
        population_profile=PopulationProfile(
            population_group="adult", body_weight_kg=SCCS_DEFAULT_BODY_WEIGHT_KG
        ),
    )


def _assumption(scenario: ExposureScenario, name: str) -> ExposureAssumptionRecord:
    return next(item for item in scenario.assumptions if item.name == name)


def _assert_sccs_arithmetic_defaults(scenario: ExposureScenario, row: SccsTable5Row) -> None:
    transfer = _assumption(scenario, "transfer_efficiency")
    assert transfer.source_kind == SourceKind.DEFAULT_REGISTRY, row.product
    assert transfer.value == pytest.approx(1.0), row.product
    expected_source = (
        RIVM_HAND_APPLICATION_SOURCE_ID
        if row.application_method == "hand_application"
        else SCCS_TRANSFER_SOURCE_ID
    )
    assert transfer.source.source_id == expected_source, row.product

    retention = _assumption(scenario, "retention_factor")
    assert retention.value == pytest.approx(row.fret), row.product
    expected_kind = (
        SourceKind.DEFAULT_REGISTRY if row.explicit_fret is None else SourceKind.USER_INPUT
    )
    assert retention.source_kind == expected_kind, row.product


@pytest.mark.parametrize("application_method", SCCS_COSMETIC_METHODS)
def test_personal_care_cosmetic_methods_resolve_sccs_transfer_default(
    application_method: str,
) -> None:
    registry = DefaultsRegistry.load()

    value, source = registry.transfer_efficiency(application_method, "personal_care")

    assert value == 1.0
    assert source.source_id == SCCS_TRANSFER_SOURCE_ID
    assert "SCCS/1647/22" in source.version
    assert source.locator.startswith("https://health.ec.europa.eu/")
    assert source.hash_sha256 == registry.sha256


def test_defaults_curation_report_publishes_sccs_cosmetic_transfer_branches() -> None:
    report = build_defaults_curation_report()
    entries = {entry.path_id: entry for entry in report.entries}

    for application_method in SCCS_COSMETIC_METHODS:
        path_id = (
            f"transfer_efficiency:application_method={application_method},"
            "product_category=personal_care"
        )
        entry = entries[path_id]
        assert entry.value == 1.0
        assert entry.unit == "fraction"
        assert entry.source_id == SCCS_TRANSFER_SOURCE_ID
        assert entry.curation_status == DefaultsCurationStatus.CURATED
        # The branches are category-scoped: no global fallback is published for them.
        assert f"transfer_efficiency:application_method={application_method}" not in entries


@pytest.mark.parametrize("application_method", SCCS_COSMETIC_METHODS)
def test_screening_build_defaults_transfer_for_cosmetic_methods(
    engine: ScenarioEngine,
    application_method: str,
) -> None:
    scenario = engine.build(_cosmetic_request(application_method=application_method))

    transfer = _assumption(scenario, "transfer_efficiency")
    assert transfer.source_kind == SourceKind.DEFAULT_REGISTRY
    assert transfer.default_applied is True
    assert transfer.value == 1.0
    assert transfer.source.source_id == SCCS_TRANSFER_SOURCE_ID
    assert transfer.governance.evidence_basis == EvidenceBasis.CURATED_DEFAULT
    assert transfer.governance.evidence_grade == EvidenceGrade.GRADE_4
    assert transfer.governance.default_visibility == DefaultVisibility.SILENT_TRACEABLE
    assert transfer.governance.applicability_domain["application_method"] == application_method
    assert not any(flag.code == "heuristic_default_source" for flag in scenario.quality_flags)
    # 1 g/day of product x leave-on retention 1.0 x transfer 1.0 / 60 kg.
    assert scenario.external_dose.value == pytest.approx(1000.0 / SCCS_DEFAULT_BODY_WEIGHT_KG)


def test_explicit_transfer_efficiency_still_overrides_sccs_default(
    engine: ScenarioEngine,
) -> None:
    scenario = engine.build(
        _cosmetic_request(application_method="brushing", transfer_efficiency=0.5)
    )

    transfer = _assumption(scenario, "transfer_efficiency")
    assert transfer.source_kind == SourceKind.USER_INPUT
    assert transfer.default_applied is False
    assert transfer.value == 0.5
    assert scenario.external_dose.value == pytest.approx(500.0 / SCCS_DEFAULT_BODY_WEIGHT_KG)


def test_cosmetic_method_labels_stay_fail_closed_outside_personal_care(
    engine: ScenarioEngine,
) -> None:
    # Paint brushing hands only a fraction of the product to the skin, so the SCCS
    # applied-amount semantics must not leak into other product categories.
    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(
            _cosmetic_request(application_method="brushing", product_category="paint_coating")
        )

    error = exc_info.value
    assert error.code == "application_method_unsupported"
    assert "paint_coating" in error.message
    assert error.details["scoped_product_categories"] == ["personal_care"]
    assert "brushing" not in error.details["supported_application_methods"]
    assert error.suggestion is not None
    assert "product_use_profile.transfer_efficiency" in error.suggestion


def test_unknown_cosmetic_method_stays_fail_closed(engine: ScenarioEngine) -> None:
    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(_cosmetic_request(application_method="airbrush"))

    error = exc_info.value
    assert error.code == "application_method_unsupported"
    assert error.details["scoped_product_categories"] == []
    assert {*SCCS_COSMETIC_METHODS, "hand_application"} <= set(
        error.details["supported_application_methods"]
    )


@pytest.mark.parametrize("application_method", ["brushing", "oral_rinse"])
def test_oral_route_does_not_inherit_oral_care_mucosal_semantics(
    engine: ScenarioEngine,
    application_method: str,
) -> None:
    # SCCS: swallowed oral exposure from oral-care products must be calculated separately.
    with pytest.raises(ExposureScenarioError) as exc_info:
        engine.build(
            _cosmetic_request(
                application_method=application_method,
                route=Route.ORAL,
                retention_type="rinse_off",
            )
        )

    assert exc_info.value.code == "ingestion_method_unsupported"


def test_sccs_table5_product_set_covers_17_categories() -> None:
    assert len(SCCS_TABLE_5) == 17
    assert len({row.product for row in SCCS_TABLE_5}) == 17
    assert {row.application_method for row in SCCS_TABLE_5} == {
        "hand_application",
        *SCCS_COSMETIC_METHODS,
    }
    assert sum(row.table5_mg_per_kg_bw_day for row in SCCS_TABLE_5) == pytest.approx(
        268.82, abs=1e-9
    )
    assert sum(row.table5_g_per_day for row in SCCS_TABLE_5) == pytest.approx(17.38, abs=1e-9)


def test_sccs_table5_aggregate_reproduces_269_mg_per_kg_bw_day(engine: ScenarioEngine) -> None:
    # Table 3A relative amounts use each study subject's body weight, not qx / 60 kg (Table 3A
    # footnote 1), so each row enters as the 60 kg equivalent of its qx/bw. Rows without qx/bw
    # were normalized by SCCS with the 60 kg default and enter as qx directly.
    components = []
    for row in SCCS_TABLE_5:
        use_amount_g = (
            row.qx_per_bw_mg_per_kg_day * SCCS_DEFAULT_BODY_WEIGHT_KG / 1000.0
            if row.qx_per_bw_mg_per_kg_day is not None
            else row.qx_g_per_day
        )
        scenario = engine.build(_table5_request(row, use_amount_g=use_amount_g))
        _assert_sccs_arithmetic_defaults(scenario, row)

        expected_mg_per_kg_bw_day = (
            row.qx_per_bw_mg_per_kg_day * row.fret
            if row.qx_per_bw_mg_per_kg_day is not None
            else row.qx_g_per_day * 1000.0 * row.fret / SCCS_DEFAULT_BODY_WEIGHT_KG
        )
        assert scenario.external_dose.value == pytest.approx(expected_mg_per_kg_bw_day, rel=1e-6), (
            row.product
        )
        assert scenario.external_dose.value == pytest.approx(
            row.table5_mg_per_kg_bw_day, abs=TABLE_5_ROW_TOLERANCE_MG_PER_KG_BW_DAY
        ), row.product
        components.append(scenario)

    aggregate = aggregate_scenarios(
        BuildAggregateExposureScenarioInput(
            chemical_id=PRODUCT_EXPOSURE_ID,
            label="SCCS NoG 12th revision Table 5 aggregate cosmetic product exposure",
            component_scenarios=components,
        ),
        DefaultsRegistry.load(),
    )

    assert aggregate.normalized_total_external_dose is not None
    total = aggregate.normalized_total_external_dose.value
    assert round(total) == SCCS_TABLE_5_AGGREGATE_MG_PER_KG_BW_DAY
    assert total == pytest.approx(SCCS_TABLE_5_AGGREGATE_MG_PER_KG_BW_DAY, abs=0.5)
    assert total == pytest.approx(
        sum(row.table5_mg_per_kg_bw_day for row in SCCS_TABLE_5), abs=0.05
    )
    assert len(aggregate.component_scenarios) == 17
    assert [item.route for item in aggregate.per_route_totals] == [Route.DERMAL]
    assert aggregate.per_route_totals[0].total_dose.value == pytest.approx(total)
    assert not any(item.code == "cross_route_aggregate" for item in aggregate.limitations)
    dominant = aggregate.dominant_contributors[0]
    assert dominant.scenario_id == components[4].scenario_id  # body lotion
    assert dominant.dose_value == pytest.approx(123.2)


def test_sccs_table5_daily_amounts_reproduce_17_4_g_per_day(engine: ScenarioEngine) -> None:
    daily_exposures_g = []
    for row in SCCS_TABLE_5:
        scenario = engine.build(_table5_request(row, use_amount_g=row.qx_g_per_day))
        _assert_sccs_arithmetic_defaults(scenario, row)

        exposure_g_per_day = scenario.route_metrics["external_mass_mg_per_day"] / 1000.0
        assert exposure_g_per_day == pytest.approx(row.qx_g_per_day * row.fret, rel=1e-6)
        assert exposure_g_per_day == pytest.approx(
            row.table5_g_per_day, abs=TABLE_5_ROW_TOLERANCE_G_PER_DAY
        ), row.product
        daily_exposures_g.append(exposure_g_per_day)

    assert round(sum(daily_exposures_g), 1) == SCCS_TABLE_5_AGGREGATE_G_PER_DAY


def test_sccs_evidence_fit_treats_sccs_anchored_methods_as_standard() -> None:
    request = _cosmetic_request(application_method="applicator")
    evidence = build_product_use_evidence_from_sccs(
        SccsCosmeticsEvidenceRecord(
            chemical_id=PRODUCT_EXPOSURE_ID,
            guidanceId="sccs_nog_12th_revision_mascara_2023",
            guidanceTitle="SCCS Notes of Guidance, 12th revision",
            guidanceVersion="SCCS/1647/22, corrigendum 2",
            guidanceLocator="https://health.ec.europa.eu/",
            cosmeticProductType="Mascara",
            productFamily="make_up",
            tableReferences=["Table 3B", "Table 5"],
            supportedRoutes=[Route.DERMAL],
            physical_forms=["liquid"],
            application_methods=["applicator"],
            retention_types=["leave_on"],
        )
    )

    report = reconcile_product_use_evidence(request, [evidence])

    assert report.recommended_source_kind == "sccs"
    assert not any("strongest for standard cosmetic" in item for item in report.rationale)
    assert any("no obvious physics mismatch" in item for item in report.rationale)
