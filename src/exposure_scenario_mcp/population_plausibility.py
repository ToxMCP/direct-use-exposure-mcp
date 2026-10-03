"""Population-profile plausibility screening for scenario inputs.

Body weight, exposed skin surface area, and inhalation rate are screened against
per-population-group bands anchored to the population defaults the registry ships
(EPA Exposure Factors Handbook 2011 source families, plus the China regional
overrides). Every shipped default sits inside its group's typical band, so defaults
never trip a finding; only explicit inputs can.

Two tiers keep the check proportionate:

* outside the typical band -> ``population_<field>_atypical`` warning flag;
* outside the screening review envelope -> ``population_<field>_implausible`` error flag
  plus an error limitation, and ``tier_semantics.assumption_checks_passed`` becomes false.

Builds are never blocked: a flagged scenario stays auditable (sensitivity sweeps and
numeric-stability checks still need extreme values), but its normalized result must
not be interpreted until the input is corrected or explicitly justified. Downstream
aggregates and PBPK handoffs re-evaluate the resolved values instead of trusting the
component flags, so stripping ``quality_flags`` from a scenario cannot hide a finding.
"""

from __future__ import annotations

from dataclasses import dataclass

from exposure_scenario_mcp.models import ExposureScenario, Severity, SourceKind

POPULATION_PLAUSIBILITY_VERSION = "2026.10.03.v2"
GENERIC_BAND_SCOPE = "any_population_group"

FIELD_UNITS = {
    "body_weight_kg": "kg",
    "exposed_surface_area_cm2": "cm2",
    "inhalation_rate_m3_per_hour": "m3/h",
}
_FIELD_CODE_STEMS = {
    "body_weight_kg": "body_weight",
    "exposed_surface_area_cm2": "exposed_surface_area",
    "inhalation_rate_m3_per_hour": "inhalation_rate",
}
_ERROR_HINTS = {
    ("body_weight_kg", "above"): (
        "grams or pounds entered as kilograms, or a misplaced decimal point"
    ),
    ("body_weight_kg", "below"): (
        "a misplaced decimal point, or a body weight taken from a different population group"
    ),
    ("exposed_surface_area_cm2", "above"): (
        "square millimetres entered as square centimetres; exposed skin area cannot "
        "exceed total body surface area"
    ),
    ("inhalation_rate_m3_per_hour", "above"): (
        "a daily volume (m3/day) or litres per minute entered as an hourly rate"
    ),
    ("inhalation_rate_m3_per_hour", "below"): "a per-minute rate (m3/min) entered as m3/h",
}


@dataclass(frozen=True, slots=True)
class PopulationPlausibilityBand:
    """Screening band for one population-profile field and population group.

    Values outside ``typical_*`` are unusual for the group (warning); values outside
    ``physiological_*`` are require explicit review under this screening policy (error). A ``None``
    limit leaves that side unbounded.
    """

    field_name: str
    band_scope: str
    typical_lower: float | None
    typical_upper: float | None
    physiological_lower: float | None
    physiological_upper: float
    anchor: str

    @property
    def unit(self) -> str:
        return FIELD_UNITS[self.field_name]

    @property
    def is_whole_body_area(self) -> bool:
        return self.field_name == "exposed_surface_area_cm2"


_Limits = tuple[float | None, float | None]


def _field_bands(
    field_name: str, entries: dict[str, tuple[_Limits, tuple[float | None, float], str]]
) -> dict[str, PopulationPlausibilityBand]:
    return {
        band_scope: PopulationPlausibilityBand(
            field_name=field_name,
            band_scope=band_scope,
            typical_lower=typical[0],
            typical_upper=typical[1],
            physiological_lower=physiological[0],
            physiological_upper=physiological[1],
            anchor=anchor,
        )
        for band_scope, (typical, physiological, anchor) in entries.items()
    }


# (typical lower, typical upper), (physiological lower, physiological upper), anchor.
_BANDS: dict[str, dict[str, PopulationPlausibilityBand]] = {
    "body_weight_kg": _field_bands(
        "body_weight_kg",
        {
            "adult": (
                (35.0, 150.0),
                (20.0, 250.0),
                "EFH 2011 Table 8-3 adults (21+ y): 5th-95th percentiles span 46.9-122 kg; "
                "shipped adult defaults are 80 kg (global) and 63 kg (china).",
            ),
            "child": (
                (8.0, 55.0),
                (4.0, 120.0),
                "EFH 2011 Table 8-3: 5th percentile 8.9 kg at 1-<2 y to 95th percentile "
                "52.5 kg at 6-<11 y; shipped child defaults are 15 kg (global) and 21 kg "
                "(china).",
            ),
            "infant": (
                (2.5, 13.0),
                (0.3, 20.0),
                "EFH 2011 Table 8-3: 5th percentile 3.6 kg at birth-<1 month to 95th "
                "percentile 11.3 kg at 6-<12 months; shipped infant default is 7.5 kg.",
            ),
            GENERIC_BAND_SCOPE: (
                (None, None),
                (0.3, 250.0),
                "Union of the registered screening review envelopes (infant lower, adult upper).",
            ),
        },
    ),
    "exposed_surface_area_cm2": _field_bands(
        "exposed_surface_area_cm2",
        {
            "adult": (
                (None, 26000.0),
                (None, 40000.0),
                "EFH 2011 Table 7-1: adult total body surface area 95th percentiles reach "
                "2.56 m2; shipped adult exposed-area defaults are 5700 cm2 (global "
                "hands/forearms anchor) and 16500 cm2 (china).",
            ),
            "child": (
                (None, 15000.0),
                (None, 25000.0),
                "EFH 2011 Table 7-1: total body surface area 95th percentile 1.48 m2 at "
                "6-<11 y and 2.33 m2 at 16-<21 y; shipped child defaults are 2800 cm2 "
                "(global) and 7200 cm2 (china).",
            ),
            "infant": (
                (None, 5500.0),
                (None, 8000.0),
                "EFH 2011 Table 7-1: total body surface area 95th percentile 0.51 m2 at "
                "6-<12 months; shipped infant default is 1800 cm2.",
            ),
            GENERIC_BAND_SCOPE: (
                (None, None),
                (None, 40000.0),
                "Adult screening surface-area review limit applied to unregistered groups.",
            ),
        },
    ),
    "inhalation_rate_m3_per_hour": _field_bands(
        "inhalation_rate_m3_per_hour",
        {
            "adult": (
                (0.2, 5.0),
                (0.1, 10.0),
                "EFH 2011 Table 6-2 adults: sedentary/sleep means from 0.0042 m3/min "
                "(~0.25 m3/h) to high-intensity 95th percentile 0.078 m3/min (~4.7 m3/h); "
                "shipped adult defaults are 0.83 m3/h (global) and 0.67 m3/h (china).",
            ),
            "child": (
                (0.15, 4.0),
                (0.05, 7.0),
                "EFH 2011 Table 6-2, 1-<11 y: sleep means from 0.0043 m3/min (~0.26 m3/h) "
                "to high-intensity 95th percentile 0.059 m3/min (~3.5 m3/h); shipped child "
                "defaults are 0.5 m3/h (global) and 0.35 m3/h (china).",
            ),
            "infant": (
                (0.1, 2.5),
                (0.01, 5.0),
                "EFH 2011 Table 6-2, birth-<1 y: sleep mean 0.003 m3/min (~0.18 m3/h) to "
                "high-intensity 95th percentile 0.041 m3/min (~2.5 m3/h); shipped infant "
                "default is 0.25 m3/h.",
            ),
            GENERIC_BAND_SCOPE: (
                (None, None),
                (0.01, 10.0),
                "Union of the registered screening review envelopes (infant lower, adult upper).",
            ),
        },
    ),
}


def _fmt(value: float) -> str:
    return f"{value:g}"


def _range_text(lower: float | None, upper: float | None, unit: str) -> str:
    if lower is not None and upper is not None:
        return f"{_fmt(lower)}-{_fmt(upper)} {unit}"
    if upper is not None:
        return f"<= {_fmt(upper)} {unit}"
    if lower is not None:
        return f">= {_fmt(lower)} {unit}"
    return "unbounded"


@dataclass(frozen=True, slots=True)
class PopulationPlausibilityFinding:
    """One population-profile value that falls outside its plausibility band."""

    field_name: str
    value: float
    population_group: str
    band: PopulationPlausibilityBand
    severity: Severity
    direction: str
    value_source: str

    @property
    def code(self) -> str:
        tier = "implausible" if self.severity == Severity.ERROR else "atypical"
        return f"population_{_FIELD_CODE_STEMS[self.field_name]}_{tier}"

    def _group_text(self) -> str:
        if self.band.band_scope == GENERIC_BAND_SCOPE:
            return (
                f"population_group '{self.population_group}' (no registered band; generic "
                "human envelope applied)"
            )
        return f"population_group '{self.population_group}'"

    def _value_text(self) -> str:
        return f"{self.field_name}={_fmt(self.value)} {self.band.unit} ({self.value_source})"

    def _typical_text(self) -> str:
        band = self.band
        if band.is_whole_body_area and band.typical_upper is not None:
            return f"typical whole-body surface area of {_fmt(band.typical_upper)} {band.unit}"
        return f"typical band {_range_text(band.typical_lower, band.typical_upper, band.unit)}"

    def _physiological_text(self) -> str:
        band = self.band
        if band.is_whole_body_area:
            return f"surface-area review limit of {_fmt(band.physiological_upper)} {band.unit}"
        envelope = _range_text(band.physiological_lower, band.physiological_upper, band.unit)
        return f"screening review envelope {envelope}"

    def _crossing_text(self, limit_text: str) -> str:
        if self.band.is_whole_body_area:
            return f"exceeds the {limit_text}"
        return f"is {self.direction} the {limit_text}"

    @property
    def message(self) -> str:
        if self.severity == Severity.ERROR:
            has_typical_band = (
                self.band.typical_lower is not None or self.band.typical_upper is not None
            )
            context = f" ({self._typical_text()})" if has_typical_band else ""
            hint = _ERROR_HINTS.get((self.field_name, self.direction))
            return (
                f"{self._value_text()} {self._crossing_text(self._physiological_text())} for "
                f"{self._group_text()}{context}. The value requires review under this "
                "screening policy, "
                "so results normalized or scaled by it are not interpretable until it is "
                "corrected or explicitly justified." + (f" Check for {hint}." if hint else "")
            )
        within = "not" if self.band.is_whole_body_area else "within"
        return (
            f"{self._value_text()} {self._crossing_text(self._typical_text())} for "
            f"{self._group_text()} but {within} the {self._physiological_text()}. Confirm the "
            "value is intended for this population group."
        )

    @property
    def validation_note(self) -> str:
        tier = "implausible" if self.severity == Severity.ERROR else "atypical"
        return (
            f"Population plausibility screening ({POPULATION_PLAUSIBILITY_VERSION}) found "
            f"{self.field_name}={_fmt(self.value)} {self.band.unit} {tier} for population_group "
            f"'{self.population_group}'; see quality flag `{self.code}`."
        )


def normalize_population_group(population_group: str) -> str:
    return population_group.strip().casefold()


def plausibility_band(field_name: str, population_group: str) -> PopulationPlausibilityBand | None:
    """Return the band that screens ``field_name`` for ``population_group``, if any."""

    bands = _BANDS.get(field_name)
    if bands is None:
        return None
    return bands.get(normalize_population_group(population_group), bands[GENERIC_BAND_SCOPE])


def population_plausibility_bands() -> list[PopulationPlausibilityBand]:
    return [band for bands in _BANDS.values() for band in bands.values()]


def evaluate_population_value(
    field_name: str,
    value: float,
    population_group: str,
    *,
    value_source: str = "user-supplied",
) -> PopulationPlausibilityFinding | None:
    """Screen one resolved population value; ``None`` means it sits inside its band."""

    band = plausibility_band(field_name, population_group)
    if band is None:
        return None

    severity: Severity | None = None
    direction = ""
    if band.physiological_lower is not None and value < band.physiological_lower:
        severity, direction = Severity.ERROR, "below"
    elif value > band.physiological_upper:
        severity, direction = Severity.ERROR, "above"
    elif band.typical_lower is not None and value < band.typical_lower:
        severity, direction = Severity.WARNING, "below"
    elif band.typical_upper is not None and value > band.typical_upper:
        severity, direction = Severity.WARNING, "above"
    if severity is None:
        return None
    return PopulationPlausibilityFinding(
        field_name=field_name,
        value=value,
        population_group=population_group,
        band=band,
        severity=severity,
        direction=direction,
        value_source=value_source,
    )


def _value_source(source_kind: SourceKind) -> str:
    if source_kind == SourceKind.USER_INPUT:
        return "user-supplied"
    if source_kind == SourceKind.DEFAULT_REGISTRY:
        return "population-default"
    return source_kind.value


def evaluate_scenario_population(
    scenario: ExposureScenario,
) -> list[PopulationPlausibilityFinding]:
    """Re-screen the population values a scenario's calculation actually used.

    Assumption records carry the resolved values that entered the arithmetic, so they
    are authoritative. Body weight falls back to the population profile because every
    route normalizes by it and PBPK handoffs export it from there.
    """

    resolved: dict[str, tuple[float, str]] = {}
    for assumption in scenario.assumptions:
        value = assumption.value
        if assumption.name not in FIELD_UNITS or isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            resolved[assumption.name] = (float(value), _value_source(assumption.source_kind))
    profile_body_weight = scenario.population_profile.body_weight_kg
    if "body_weight_kg" not in resolved and profile_body_weight is not None:
        resolved["body_weight_kg"] = (float(profile_body_weight), "population-profile")

    findings: list[PopulationPlausibilityFinding] = []
    for field_name in FIELD_UNITS:
        if field_name not in resolved:
            continue
        value, value_source = resolved[field_name]
        finding = evaluate_population_value(
            field_name,
            value,
            scenario.population_profile.population_group,
            value_source=value_source,
        )
        if finding is not None:
            findings.append(finding)
    return findings


def pbpk_population_context_findings(
    population_group: str,
    *,
    body_weight_kg: float | None,
    inhalation_rate_m3_per_hour: float | None,
) -> list[PopulationPlausibilityFinding]:
    """Error-tier findings for the population context a PBPK handoff would carry."""

    findings: list[PopulationPlausibilityFinding] = []
    for field_name, value in (
        ("body_weight_kg", body_weight_kg),
        ("inhalation_rate_m3_per_hour", inhalation_rate_m3_per_hour),
    ):
        if value is None:
            continue
        finding = evaluate_population_value(
            field_name,
            float(value),
            population_group,
            value_source="PBPK population context",
        )
        if finding is not None and finding.severity == Severity.ERROR:
            findings.append(finding)
    return findings


def pbpk_population_context_message(findings: list[PopulationPlausibilityFinding]) -> str:
    values = ", ".join(
        f"{item.field_name}={_fmt(item.value)} {item.band.unit}" for item in findings
    )
    return (
        "The PBPK population context carries values outside the physiological plausibility "
        f"envelope for population_group '{findings[0].population_group}' ({values}). Do not "
        "parameterize a PBPK model with this context until the source scenario inputs are "
        "corrected or explicitly justified."
    )


def population_plausibility_markdown() -> list[str]:
    """Markdown lines documenting the active bands for the defaults evidence map."""

    lines = [
        "### Population Plausibility Bands",
        "",
        "- These are versioned input-review heuristics, not EPA-prescribed limits or",
        "  universal physiological maxima. A flagged value may be legitimate for a special",
        "  population; confirm the units and context before using normalized doses.",
        "- EPA 2011 tables provide reference context for the shipped defaults. The wider",
        "  review limits are operator policy choices, not measurements from those tables.",
        "- Reference: https://www.epa.gov/expobox/exposure-factors-handbook-2011-edition",
        "",
        f"- Band pack version: `{POPULATION_PLAUSIBILITY_VERSION}`.",
        "- Explicit and defaulted `body_weight_kg`, `exposed_surface_area_cm2`, and",
        "  `inhalation_rate_m3_per_hour` values are screened against the bands below. Every",
        "  shipped population default sits inside its group's typical band.",
        "- Typical bands sit just outside the EFH 2011 5th-95th percentile span for each",
        "  group; screening review envelopes sit far enough beyond them to catch unit,",
        "  decimal-place, and cross-group errors (for example adult body weight above 250 kg).",
        "- Outside the typical band: `population_<field>_atypical` warning quality flag.",
        "- Outside the screening review envelope (for exposed area: above the whole-body",
        "  maximum): `population_<field>_implausible` error quality flag and limitation,",
        "  and `tier_semantics.assumption_checks_passed=false`. The scenario is still built so",
        "  it stays auditable, but its normalized result must not be interpreted until the",
        "  input is corrected or justified.",
        "- Aggregates, PBPK compatibility checks, and PBPK scenario exports re-screen the",
        "  resolved component values rather than trusting component flags.",
        (
            "- Population groups without a registered band are screened only against the "
            f"`{GENERIC_BAND_SCOPE}` screening review envelope."
        ),
        "",
    ]
    for band in population_plausibility_bands():
        typical = _range_text(band.typical_lower, band.typical_upper, band.unit)
        physiological = _range_text(band.physiological_lower, band.physiological_upper, band.unit)
        lines.append(
            f"- `{band.field_name}` / `{band.band_scope}`: typical `{typical}`, "
            f"review `{physiological}`."
        )
        lines.append(f"  anchor: {band.anchor}")
    return lines
