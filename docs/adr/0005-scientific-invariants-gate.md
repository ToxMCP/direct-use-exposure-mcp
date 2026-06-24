# ADR 0005 — Track-B scientific-invariants gate (vendored schema-spine engine)

Status: accepted
Date: 2026-06-25

## Context

direct-use-exposure-mcp emits a released scientific object,
`aggregateExposureSummary.v1` (`docs/contracts/schemas/aggregateExposureSummary.v1.json`),
that summarizes summed EXTERNAL direct-use/consumer exposure across co-use component
scenarios. It feeds downstream weight-of-evidence work (a
`direct-use-exposure-woe-roundtrip` golden exists in WoE-NGRA). An external aggregate
exposure estimate is **not** a risk/regulatory conclusion and **not** an internal
dose — over-representing it as either is a governance-relevant overclaim.

The ToxMCP / NGRA.ai schema-spine ships a policy engine that enforces exactly these
invariants for external exposure records. This ADR records the decision to vendor a
digest-pinned copy of that engine and run it, fail-closed, over the released summary
as a **regression tripwire** (Track-B). The server is deterministic and non-LLM and
already enforces these invariants natively, so on the pristine corpus the gate is
GREEN; its job is to BLOCK if a future change ever lets one of the regressions below
leak into a released object.

## Decision

Add a `governance/` layer under `src/exposure_scenario_mcp/` plus a
`scripts/scientific_invariants_gate.py` entrypoint and a `scientific-invariants` CI
job:

1. **Vendored, digest-pinned engine.** `vendor/schema-spine/**` is a byte-authentic
   copy of `ToxMCP/toxmcp-schema-spine` at gitSha
   `e0a6a0581efd8dfd5b10c2de14435d87769c5944`. `scripts/vendor_verify.py`
   (`vendor:verify`) recomputes the sha256 of every vendored file against
   `VENDORED_FROM.json` and hard-fails on tamper / untracked / missing. The bridge
   ALSO re-checks digests at runtime and blocks on `VENDOR_DIGEST_MISMATCH`, so a
   tampered engine never runs even when CI is advisory.

2. **Fail-closed Node bridge** (`governance/spine_bridge.py`). Every failure mode —
   missing node, non-zero exit, empty/unparseable stdout, timeout, an unrecognized
   `schemaId` (the engine returns `valid:true` for unknown ids — a silent no-op this
   closes) — becomes a BLOCKING synthetic finding, never a skip/pass.

3. **Source-contract guard FIRST** (`governance/source_contract.py`). Before any
   projection, each raw source packet is validated against the producer's STRICT
   emission contract — a dependency-free Draft-07 SUBSET `additionalProperties:false`
   schema (`governance/aggregate_exposure_summary.strict.schema.json`) that mirrors
   the pydantic `StrictModel` (`extra='forbid'`) serializer and was authored from the
   REAL producer emission (`examples.build_examples`), NOT the laxer published docs
   schema (whose `required` omits the always-stamped `schema_version` /
   `scenario_class` / `aggregationMode` / `uncertaintyTier` and the default-factory
   lists). A violation — including any undeclared / schema-forbidden field — is a
   `SOURCE_CONTRACT_VIOLATION` that BLOCKS and is NEVER projected. This closes the
   producer-emission-contract dead-arm class.

4. **Total projection from declared fields only** (`governance/project_to_spine.py`).
   The summary is projected onto two recognized spine shapes — `RouteDoseEstimate`
   (anti-overclaim + uncertainty-ceiling core) and one `ExposureScenarioContext` per
   declared component scenario — using POSITIVE STRUCTURED EVIDENCE derived only from
   declared fields. Identifiers are NFKD-normalized (combining-mark / format-char
   strip) so a forged/zero-width ref cannot masquerade as substantive. A missing
   required field raises `PROJECTION_INCOMPLETE` (block) rather than safe-defaulting.

## Advertised codes (advertised == producer-contract-valid-reachable)

Each advertised code was re-proven to bite on a producer-emittable, strict-contract-
VALID (Ajv-2020 valid against BOTH the published and the strict schema) declared-field
fault, and to revert to green when the fault is removed:

| code | declared field(s) | producer-valid fault that bites |
| --- | --- | --- |
| `EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE` | `aggregationMode` + `internalEquivalentTotalDose` | an `external_summary` carrying a populated `internalEquivalentTotalDose` (both declared & nullable) → projected `internal_dose_estimate` downstream-use token |
| `EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED` | `uncertaintyRegister` (+ `uncertaintyTier` / `validationSummary`) | an emitted summary that drops its `uncertaintyRegister` (list, no `minItems`) → no substantive uncertainty refs |
| `EXPOSURE_SCENARIO_CONTEXT_REQUIRED` | `component_scenarios[].route` + `uncertaintyRegister` | a component scenario projected with no explicit uncertainty references |

A COHERENT `internal_equivalent` summary is a legitimate external→internal-equivalent
dosimetry step (the spine treats `exposure → internal_dose` as a permitted transition,
not an escalation) and passes — it is mapped to a non-blocking
`internal_equivalent_dosimetry` token.

## Deterministic — NO AI-provenance arm (N/A)

The released summary carries NO AI / model-use / LLM / provenance-of-generation field
(verified against the real producer emission; the server is deterministic and
non-LLM). Therefore NO `AssessmentRun` is projected and NO spine AI-provenance code
(`AI_MODEL_IDENTITY_REQUIRED`, `AI_UNKNOWN_WITH_PUBLIC_RELEASE`,
`AI_USE_NONE_WITH_MODEL_TRACE`, `HUMAN_REVIEW_REQUIRED_FOR_PUBLIC_AI_ASSESSMENT`,
`USABLE_HUMAN_REVIEW_REQUIRED`, `AI_RECORD_FREE_TEXT_OVERCLAIM`,
`MODEL_IDENTITY_IS_NOT_VALIDATION`, `AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW`) is
advertised — advertising one would be a DEAD ARM (no real source fault could make the
engine dispatch it; it could only "fire" by mutating the PROJECTED object).
Re-introduction path: if a future release adds a real AI/model-use field to the
emitted summary, project an `AssessmentRun` from it and advertise the matching AI
codes.

## Honest-drops (N/A for this packet)

Spine codes the released summary cannot express are NOT advertised: claim-class
escalation codes (`CLAIM_TRANSITION_*`) — the summary carries no claim-transition
record; comparability codes (`COMPARABILITY_*`) — no comparability qualification is
emitted; bioactivity/PoD codes — out of domain for an external exposure estimate.

## Consequences

- The gate is ADVISORY on the free-plan repo (no required-status-checks on the
  current plan). The bridge is fail-closed at runtime regardless. PROMOTE-TO-BLOCKING:
  mark the `scientific-invariants` CI job a required status check when the repo moves
  to a plan with branch protection / rulesets — the gate already exits non-zero on any
  blocking code, so no script change is needed.
- The golden corpus (`tests/fixtures/governance/*.json`) is a byte-faithful capture of
  the real producer emission; regenerate via
  `scripts/build_scientific_invariants_corpus.py` after any intentional producer
  change.
- Do NOT hand-edit vendored files; re-vendor and re-run `vendor:verify --write`.
