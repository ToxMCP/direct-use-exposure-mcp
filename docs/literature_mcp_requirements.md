# Literature MCP Requirements

## Status

Proposed design note. This document defines what a separate `Literature MCP` would need to do
for the ToxMCP suite. It does not imply that the service should be built now.

## Recommendation

Do **not** build a standalone Literature MCP yet unless the suite needs repeatable,
multi-consumer evidence curation beyond what the current repo-local defaults packs and validation
dossier can support.

Near term, the lower-risk path is:

- keep deterministic exposure math in Direct-Use Exposure MCP
- keep WoE/report orchestration in a future orchestration/reporting layer
- continue curating evidence-linked defaults and validation datasets in versioned data packs
- define the future Literature MCP interface now so later extraction/curation work has a clean
  landing zone

## Why a Separate Service Might Exist

Direct-Use Exposure MCP already does three things well:

- resolve screening inputs into external-dose scenarios
- publish provenance, uncertainty, and validation posture
- export deterministic handoff objects for PBPK MCP and the future orchestration/reporting layer

It should **not** become the primary home for document ingestion, citation normalization,
parameter extraction, or evidence review workflow. Those concerns have a different lifecycle,
different quality controls, and different failure modes than dose calculation.

A future Literature MCP would exist to own the evidence-curation layer that feeds multiple
consumers, including Direct-Use Exposure MCP.

## When Not to Build It

Do not split this into a standalone MCP if the suite only needs:

- a small number of manually curated defaults packs
- a small number of manually curated external validation records
- human-reviewed literature notes that are not reused outside exposure work

In that case, a versioned evidence registry inside the existing repos is simpler and safer.

## Required Boundary

If built, Literature MCP should own:

- document discovery and citation normalization
- document metadata, deduplication, and provenance
- parameter extraction candidates from literature or guidance
- applicability-domain tagging
- evidence-strength proposal workflows
- validation-dataset registry curation
- review decisions for whether a source is usable for defaults, validation, or contextual notes

It should not own:

- deterministic exposure math
- defaults resolution at runtime
- scenario construction
- PBPK execution or interpretation
- WoE scoring or final NGRA decisions
- silent promotion of extracted values into active defaults

## Minimum Required Outputs

The service would need to produce structured, reviewable objects rather than free-text summaries.
At minimum:

1. `citationRecord`
   - normalized title, authors, year, source type, DOI/URL, publisher, document hash
2. `evidenceRecord`
   - canonical evidence identifier, citation link, review status, provenance chain
3. `parameterEvidenceCandidate`
   - parameter name, extracted value or range, units, route, product family, population context,
     scenario context, extraction rationale, confidence, and quoted source location
4. `applicabilityAssessment`
   - domain labels, inclusion/exclusion conditions, blocking caveats, and mismatch reasons
5. `validationDatasetRecord`
   - measured endpoint, comparator semantics, usable range/band, study context, and benchmark fit
6. `reviewDecision`
   - accepted, rejected, needs_review, or superseded, with reviewer note and effective date

## Required Tool Surface

If this becomes an MCP, the tool surface should be read-mostly at first.

### Read-only evidence discovery

- `literature_search_sources`
  - Search a curated evidence registry by parameter, route, product family, study type, or source
    identifier.
- `literature_get_source`
  - Return a normalized citation record plus provenance metadata and extracted snippets.
- `literature_list_parameter_candidates`
  - Return candidate parameter records for a named factor such as `transfer_efficiency`,
    `retention_factor`, or `air_exchange_rate_per_hour`.
- `literature_list_validation_datasets`
  - Return candidate external validation datasets with comparator semantics and applicability tags.

### Review-support workflows

- `literature_compare_parameter_candidates`
  - Compare multiple candidate records for the same parameter and show conflicts, overlap, and
    applicability differences.
- `literature_build_evidence_pack`
  - Package reviewed parameter candidates into a deterministic, versionable evidence pack for
    downstream use.
- `literature_build_validation_pack`
  - Package reviewed validation datasets into a deterministic registry for executable checks or
    dossier references.

### Optional write/curation workflows

These should only exist if the review process becomes operationally mature:

- `literature_save_review_decision`
- `literature_supersede_evidence_record`
- `literature_attach_extraction_note`

## Required Resource Surface

The resource layer matters more than chatty tools. At minimum:

- `literature://manifest`
- `literature://source/{source_id}`
- `literature://parameter/{parameter_name}`
- `literature://validation/{dataset_id}`
- `literature://pack/{pack_id}`
- `docs://literature-evidence-policy`
- `docs://literature-applicability-taxonomy`
- `docs://literature-review-workflow`

## Required Contract Families

The core contract set should be narrow and stable:

- `citationRecord.v1`
- `evidenceRecord.v1`
- `parameterEvidenceCandidate.v1`
- `parameterEvidencePack.v1`
- `applicabilityAssessment.v1`
- `validationDatasetRecord.v1`
- `validationDatasetPack.v1`
- `reviewDecision.v1`

Each contract should preserve:

- deterministic identifiers
- source locator granularity down to page/table/figure/section where possible
- units and value semantics
- extraction method and review state
- applicability domain and exclusion conditions
- uncertainty type, if the source explicitly supports it

## What Direct-Use Exposure MCP Would Need From It

Direct-Use Exposure MCP does not need a generic literature chatbot. It needs reviewed, machine-safe
inputs. The minimum import-ready payloads are:

### Defaults-pack feed

For defaults curation, each parameter candidate needs:

- `parameter_name`
- `value` or `range`
- `units`
- `route`
- `application_method`
- `product_category`
- `physical_form`
- `population_context`
- `region`
- `source_id`
- `reference_title`
- `reference_locator`
- `evidence_grade_proposal`
- `applicability_assessment`
- `review_decision`

### Validation-dossier feed

For executable or cited validation support, each dataset record needs:

- measured quantity and comparator semantics
- accepted operating band or reference range
- route and product/use context
- study population and scenario assumptions
- dataset quality and reuse constraints
- exact citation and locator metadata
- review status and supersession chain

## What A Future Orchestration Layer Would Need From It

A future orchestration/reporting layer would consume Literature MCP differently from Direct-Use Exposure MCP.
Likely needs:

- source summaries for problem formulation
- evidence envelopes with stable source IDs
- applicability explanations for why a candidate source was or was not used
- review-state awareness so draft extractions are not treated as accepted evidence

## What PBPK MCP Would Need From It

PBPK MCP should not depend on Literature MCP directly for exposure defaults. At most, it may need:

- normalized source metadata for model-parameter justification
- validation-dataset descriptors for PBPK calibration dossiers

That dependency should stay optional.

## Quality Bar

A standalone Literature MCP should not exist unless it can meet these conditions:

- deterministic source identifiers and content hashes
- explicit distinction between extracted candidate and accepted pack content
- machine-readable applicability domains
- versioned evidence packs suitable for downstream pinning
- review-state gating so unreviewed candidates cannot silently activate in Exposure MCP
- auditable supersession when a source or value is replaced

## Recommended Delivery Path

If the suite eventually needs this service, build it in phases:

1. `Phase 0: No MCP`
   - Keep curated evidence packs in-repo and define stable schemas only.
2. `Phase 1: Read-only registry MCP`
   - Publish normalized citations, parameter candidates, and validation records.
3. `Phase 2: Pack builder`
   - Add deterministic pack-export tools for reviewed defaults and validation datasets.
4. `Phase 3: Review workflow`
   - Add explicit review-decision mutation tools only after governance is mature.

## Practical Recommendation for ToxMCP Now

The suite should define Literature MCP as a future adjacent service, but continue shipping
scientifically curated defaults and validation improvements directly through Direct-Use Exposure MCP
until at least one of these becomes true:

- multiple repos need the same reviewed evidence registry
- parameter extraction volume becomes too large for manual curation alone
- validation datasets need a shared review/supersession workflow across teams

Until then, the interface defined here is enough. The architecture stays clean without introducing
an extra service boundary too early.
