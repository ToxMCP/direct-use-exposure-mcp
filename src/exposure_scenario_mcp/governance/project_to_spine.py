"""Total, deterministic projection: AggregateExposureSummary -> ToxMCP spine objects.

The released object ``aggregateExposureSummary.v1`` is an EXTERNAL aggregate
exposure estimate (a screening summary of summed external doses across co-use
component scenarios). It is NOT a risk/regulatory conclusion and NOT an internal
dose. This module projects it onto the two canonical spine shapes whose policy the
vendored engine actually reasons about for external exposure:

  * RouteDoseEstimate  — the anti-overclaim + uncertainty-ceiling core. The engine
    enforces that an external route-dose record cannot authorize internal-dose /
    risk / regulatory downstream uses (EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE) and must
    carry uncertainty + confidence-ceiling references
    (EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED).
  * ExposureScenarioContext — one per declared component scenario; the engine
    enforces an assessed route + explicit uncertainty references
    (EXPOSURE_SCENARIO_CONTEXT_REQUIRED).

POSITIVE STRUCTURED EVIDENCE, FROM DECLARED FIELDS ONLY
-------------------------------------------------------
Every projected field is derived from a DECLARED field the strict producer contract
actually stamps — never a fabricated safe default. In particular:

  * ``allowedDownstreamUses`` is built from the declared ``aggregationMode`` and the
    declared ``internalEquivalentTotalDose`` / ``perRouteInternalEquivalentTotals``.
    A COHERENT ``external_summary`` (internalEquivalentTotalDose absent) authorizes
    only external-exposure prioritization/comparison — it passes. A COHERENT
    ``internal_equivalent`` summary is a legitimate external->internal-equivalent
    dosimetry step and is mapped to a NON-blocking internal-equivalent token (the
    spine treats exposure->internal_dose as a legitimate transition, not an
    escalation). The INCOHERENT case — an ``external_summary`` that nonetheless
    carries an ``internalEquivalentTotalDose`` (both fields are declared & nullable,
    so this is a real producer-emittable, strict-schema-VALID fault) — is the
    overclaim: it is mapped to an ``internal_dose_estimate`` downstream-use token so
    the engine's EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE invariant bites.

  * ``uncertaintyRefs`` are the declared ``uncertaintyRegister[].entryId`` values;
    ``confidenceCeilingRefs`` are derived from the declared ``uncertaintyTier`` and
    ``validationSummary`` posture. An emitted summary that drops its uncertainty
    register (a strict-schema-VALID fault: the field is a list with no minItems)
    therefore loses its substantive refs and the uncertainty/ceiling invariants
    bite.

DETERMINISTIC — NO AI ARM
-------------------------
direct-use-exposure-mcp is deterministic and non-LLM; the released summary carries
NO AI / model-use / LLM / provenance-of-generation field (confirmed against the real
producer emission). No AssessmentRun is projected and NO AI-provenance spine code is
advertised — advertising one would be a DEAD ARM (no real source fault could make it
dispatch). See ADR 0005.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from exposure_scenario_mcp.governance.errors import ProjectionIncompleteError

# Canonical spine schemaIds this projection emits (must be in the engine's
# RECOGNIZED_SCIENTIFIC_SCHEMA_IDS; the bridge re-checks recognized-ness).
ROUTE_DOSE_ESTIMATE_SCHEMA_ID = "https://schemas.ngra.ai/toxmcp/RouteDoseEstimate.v1.schema.json"
EXPOSURE_SCENARIO_CONTEXT_SCHEMA_ID = (
    "https://schemas.ngra.ai/toxmcp/ExposureScenarioContext.v1.schema.json"
)

_VALID_ROUTES = frozenset({"dermal", "oral", "inhalation"})


def _normalize_identifier(value: str) -> str:
    """NFKD-fold an identifier and strip combining marks + format/control chars.

    Closes the zero-width / combining-diacritic identifier-forgery class: two refs
    that LOOK distinct to a human but normalize to the same machine token cannot
    masquerade as substantive, and a forged ref full of invisible characters cannot
    pass as a real one. Whitespace is collapsed; the result is what the spine's
    substantive-ref check sees.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    kept = [
        ch for ch in decomposed if unicodedata.category(ch) not in {"Mn", "Mc", "Me", "Cf", "Cc"}
    ]
    return " ".join("".join(kept).split())


def _require(source: dict[str, Any], key: str, path: str) -> Any:
    if key not in source:
        raise ProjectionIncompleteError(
            f"Released summary is missing required field {key!r}.", path=path
        )
    return source[key]


def _uncertainty_refs(source: dict[str, Any]) -> list[str]:
    """Substantive uncertainty refs from the DECLARED uncertaintyRegister.

    Each register entry's normalized ``entryId`` becomes a ``uncertainty:<id>`` ref.
    An emitted summary that carries no register entries yields no refs, so the
    spine's uncertainty invariants bite (a real, strict-schema-valid fault — the
    register is a list with no minItems).
    """
    register = source.get("uncertaintyRegister", [])
    refs: list[str] = []
    if isinstance(register, list):
        for entry in register:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("entryId")
            if isinstance(entry_id, str):
                norm = _normalize_identifier(entry_id)
                if norm:
                    refs.append(f"uncertainty:{norm}")
    return refs


def _confidence_ceiling_refs(source: dict[str, Any]) -> list[str]:
    """Confidence-ceiling refs from the DECLARED uncertaintyTier + validationSummary.

    The governance-relevant ceiling is the declared uncertainty tier plus, when a
    validation summary is present, its declared ``probabilisticEnablement`` posture
    (``blocked`` is itself a ceiling: probabilistic interpretation is gated). Built
    only from declared fields.
    """
    refs: list[str] = []
    tier = source.get("uncertaintyTier")
    if isinstance(tier, str) and tier.strip():
        refs.append(f"ceiling:uncertainty_tier:{_normalize_identifier(tier)}")
    vs = source.get("validationSummary")
    if isinstance(vs, dict):
        enablement = vs.get("probabilisticEnablement")
        if isinstance(enablement, str) and enablement.strip():
            refs.append(f"ceiling:probabilistic_enablement:{_normalize_identifier(enablement)}")
        highest = vs.get("highestSupportedUncertaintyTier")
        if isinstance(highest, str) and highest.strip():
            refs.append(f"ceiling:highest_supported_tier:{_normalize_identifier(highest)}")
    return refs


def _allowed_downstream_uses(source: dict[str, Any]) -> list[str]:
    """Downstream-use authorization tokens, from DECLARED aggregation semantics.

    The released object is fundamentally an external aggregate exposure estimate, so
    the baseline authorization is external-exposure prioritization/comparison only.
    The aggregation mode + the presence of an internal-equivalent total decide the
    rest:

      * external_summary, NO internalEquivalentTotalDose  -> coherent external
        estimate; external tokens only (passes the anti-overclaim invariant).
      * internal_equivalent (with an internalEquivalentTotalDose) -> a legitimate
        external->internal-equivalent dosimetry step; a NON-blocking
        ``internal_equivalent_dosimetry`` token (exposure->internal_dose is a
        legitimate spine transition, not an escalation).
      * external_summary WITH a populated internalEquivalentTotalDose -> INCOHERENT
        overclaim (a strict-schema-VALID, producer-emittable fault, since both
        fields are declared & nullable): an external summary asserting an internal
        dose. Mapped to an ``internal_dose_estimate`` token so the engine's
        EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE invariant bites.
    """
    uses = ["aggregate_exposure_prioritization", "cross_route_external_comparison"]
    mode = source.get("aggregationMode")
    has_internal_total = source.get("internalEquivalentTotalDose") is not None
    if mode == "internal_equivalent":
        # Legitimate external->internal-equivalent dosimetry handoff.
        uses.append("internal_equivalent_dosimetry")
    elif mode == "external_summary" and has_internal_total:
        # Incoherent: an external summary carrying an internal-equivalent dose is
        # overclaiming an internal dose from an external aggregate.
        uses.append("internal_dose_estimate")
    return uses


def project_route_dose_estimate(source: dict[str, Any], *, summary_id: str) -> dict[str, Any]:
    """Project the released summary onto a spine RouteDoseEstimate (anti-overclaim).

    Total: every field is derived from a DECLARED source field; nothing is
    safe-defaulted.
    """
    _require(source, "schema_version", "$.schema_version")
    scenario_id = _require(source, "scenario_id", "$.scenario_id")
    chemical_id = _require(source, "chemical_id", "$.chemical_id")
    _require(source, "aggregationMode", "$.aggregationMode")

    return {
        "schemaId": ROUTE_DOSE_ESTIMATE_SCHEMA_ID,
        "routeDoseEstimateId": f"{summary_id}:{scenario_id}",
        "chemicalId": chemical_id,
        "allowedDownstreamUses": _allowed_downstream_uses(source),
        "uncertaintyRefs": _uncertainty_refs(source),
        "confidenceCeilingRefs": _confidence_ceiling_refs(source),
    }


def project_scenario_contexts(source: dict[str, Any], *, summary_id: str) -> list[dict[str, Any]]:
    """Project each DECLARED component scenario onto a spine ExposureScenarioContext.

    One context per ``component_scenarios[]`` entry, carrying its declared route and
    the summary's declared uncertainty refs. The engine requires an assessed route +
    explicit uncertainty references.
    """
    components = _require(source, "component_scenarios", "$.component_scenarios")
    if not isinstance(components, list) or not components:
        raise ProjectionIncompleteError(
            "Released summary has no component_scenarios to project.",
            path="$.component_scenarios",
        )
    refs = _uncertainty_refs(source)
    contexts: list[dict[str, Any]] = []
    for idx, comp in enumerate(components):
        if not isinstance(comp, dict):
            raise ProjectionIncompleteError(
                f"component_scenarios[{idx}] is not an object.",
                path=f"$.component_scenarios[{idx}]",
            )
        route = comp.get("route")
        if not isinstance(route, str) or route not in _VALID_ROUTES:
            # An unmapped / unassessed route is never silently defaulted to a safe
            # branch; project it through as not_assessed so the engine's
            # EXPOSURE_SCENARIO_CONTEXT_REQUIRED invariant decides (it blocks
            # not_assessed). The strict producer contract only permits the three
            # real routes, so a clean packet never lands here.
            route = "not_assessed"
        comp_scenario_id = comp.get("scenario_id")
        ctx_suffix = (
            _normalize_identifier(comp_scenario_id)
            if isinstance(comp_scenario_id, str)
            else f"component-{idx}"
        )
        contexts.append(
            {
                "schemaId": EXPOSURE_SCENARIO_CONTEXT_SCHEMA_ID,
                "exposureScenarioContextId": f"{summary_id}:{ctx_suffix}",
                "route": route,
                "uncertaintyRefs": list(refs),
            }
        )
    return contexts


def project_summary(source: dict[str, Any], *, summary_id: str) -> list[tuple[str, dict[str, Any]]]:
    """Project a released AggregateExposureSummary into all its spine objects.

    Returns (label, projected_object) pairs: one RouteDoseEstimate (the
    anti-overclaim + uncertainty-ceiling core) and one ExposureScenarioContext per
    declared component scenario.
    """
    out: list[tuple[str, dict[str, Any]]] = [
        (
            f"{summary_id}#routeDoseEstimate",
            project_route_dose_estimate(source, summary_id=summary_id),
        )
    ]
    for idx, ctx in enumerate(project_scenario_contexts(source, summary_id=summary_id)):
        out.append((f"{summary_id}#exposureScenarioContext[{idx}]", ctx))
    return out
