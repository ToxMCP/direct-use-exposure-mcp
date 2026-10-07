# Reproducible exposure review worksheets

This repository workflow helps a reviewer inspect exposure calculations and decide what evidence to review next. It produces an accounted worksheet subtotal only when compatible deterministic inputs permit arithmetic. Material correspondence, complete aggregate exposure and scientific approval remain unresolved. Every result reports `assessmentStopAuthorized: false`.

Use Python 3.12 or later with the repository's pinned SDK2 environment. Configure an explicit local source checkout and its Python interpreter; active app registrations are not used. This command runs one worksheet and refuses an existing output directory, including an empty one:

```sh
uv sync --extra dev --locked
uv run python -m scripts.run_exposure_review \
  --worksheet examples/exposure-review/tea-tree-oil.v1.json \
  --servers /path/to/servers.local.json \
  --sources /path/to/sources.local.json \
  --output /path/to/new-review-run
```

Copy `examples/exposure-review/servers.example.v1.json` and `sources.example.v1.json` into local configuration files, then replace the placeholder paths. Paths are relative to their configuration file unless absolute. The interpreter must contain MCP SDK2 and match `expected_version`; it must import Exposure from the configured checkout. Optional `expected_commit` additionally requires that exact commit and a clean checkout. Without it, the runner records the observed commit, dirty state and hashes of the server's Python source files. Preserve virtual-environment interpreter paths, including their symlinks.

Source configuration maps the pinned catalogue identifiers to your retained public PDFs. Only exact hashes are accepted. The runner records missing, unreadable, mismatched and unreviewed identifiers. Supply a missing record and verify its passage before relying on a source-dependent conclusion. No download or literature search occurs during execution. PDFs remain local; configuration and reports may contain private paths and should be reviewed before sharing.

## Four example reviews

| Worksheet | What it demonstrates | What remains unresolved |
| --- | --- | --- |
| `tea-tree-oil.v1.json` | Four published product rows reconstructed with native producer external doses and separate product-specific absorption arithmetic | Actual material binding, event inventory and complete exposure outside the defended rows |
| `ehmc.v1.json` | Accepted SCCS selection: 0.28% mean + 0.17% one SD = 0.45%, fraction 0.0045 | Transfer to the explicitly hypothetical cream; no absorbed subtotal is produced |
| `basic-blue-99.v1.json` | Rejected absorption study; the opinion's 50% fallback remains an attributed source finding | Batch/method correspondence and separate genotoxicity concerns; no automatic fallback or absorbed subtotal |
| `cannabidiol.v1.json` | Source/routing review of multiproduct skin-sensitisation coverage | Local endpoint-specific exposure; no fabricated systemic mg/kg-day request |

Run the command once per example with distinct output directories. The primary links, hashes, RegLens evidence IDs, adoption/corrigendum dates and printed-page locators are retained in `tests/fixtures/regulatory_exposure_review_cases.v1.json`. The earlier historical kojic-acid and age-specific methyl-salicylate entries remain intact. Published conclusions are attributed SCCS findings, not this workflow's approval or claims of current legal adoption. RegLens extraction labels are checked against primary passages; EHMC absorption is not a hazard point of departure.

Tea tree oil reconstructs **0.014309516 mg/kg-day** before row rounding. The displayed rounded rows sum to **0.0144**, correcting the applicant's printed **0.144**. The worksheet's 60-kg normalization is an explicit algebraic device to reproduce the published normalized rows, not a recovered original population or product-use record. Its product amounts already represent the retained product-exposure inputs: retention and transfer are explicitly one, avoiding a second retention adjustment. Product-specific 20.41% and 12.84% absorption selections remain separate. The captured native aggregate contains external doses only; it does not contain the absorption-adjusted worksheet subtotal.

## Inputs and interpretation

The independently versioned repository format `exposureReviewWorksheet.v1` contains a common scope and a source/event inventory. Match chemical/material representation, population, region, body-weight basis, period, duration, endpoint and dose basis before combining contributions. Chemical-ID agreement does not authenticate structures, batch composition or unknown constituents. Preserve historical periods instead of relabelling them current.

Each component supplies the native producer tool and inputs, its source identifiers, nature, dose statistic and event relationship. Choose `additive`, `alternative`, `already_counted` or `unknown`; explicit overlap excludes the component. Multiple contributions require an independence rationale. Documented, illustrative and hypothetical components require separate worksheets. These deterministic scenarios are not probability distributions or safety allowances. Marginal P95s and means are excluded from this deterministic subtotal; a joint exposure method needs separate review.

Absorption selections record original percent/fraction units, statistic and source-backed applicability. `published_reconstruction` is restricted to reproducing the source rows and grants no transfer. `unknown` and `rejected` selections block absorbed arithmetic. A caller's `reviewed` label alone is insufficient: record tested/assessed material and formulation, concentration, contact conditions, study model and quality appraisal. Even a populated appraisal is not authenticated scientific approval. P95 or unknown absorption statistics cannot silently become mean-plus-SD or aggregate P95 inputs.

For non-detects, supply the documented **positive** concentration upper bound and use that same value in the producer input. Zero, missing or mismatched bounds are refused. Non-detection does not guarantee future-lot compliance. Omitted-source bounds remain `null` when unknown; supplied finite nonnegative bounds are recorded but never automatically promoted into complete coverage.

External dermal loading, absorbed systemic dose, local skin CEL and local respiratory concentration remain different quantities. Unsupported per-application or area-based units need a documented derivation before conversion. Use Dietary for food-mediated exposure; this workflow covers supported direct-use Exposure builders. It does not create TTC evidence descriptors, signatures or new producer adapters.

## Outputs and next decisions

`REPORT.md` explains published findings, native doses, worksheet arithmetic and reopening conditions. `report.json` retains the complete review; `semantic-results.json` supports comparison while excluding generated IDs, timestamps and machine paths. `sdk-exchanges.jsonl` records application-level SDK method arguments, responses and errors; it is not a claim of raw JSON-RPC wire capture. Native inputs and responses, discovered tools/resources, actual defaults/release resources, source copies, server preflight and diagnostics are retained separately. `SHA256SUMS.json` hashes every output file except itself. Original worksheet/configuration/PDF bytes are copied unchanged. A mismatched PDF is named using the expected pin but its actual hash and mismatch status are recorded; never treat its filename as verification.

A failed run preserves inputs, failure details and the manifest. Correct the problem and choose a fresh directory. Unknown producer findings and their original codes/messages remain visible; they cannot be cleared by this workflow. The PBPK export option captures existing compatibility/readiness output without executing a kinetic model. A contradictory population profile must preserve the original calculation denominator and lose readiness.

| Decision question | First action | Reopening condition |
| --- | --- | --- |
| Source record missing/mismatched | Documentary retrieval and passage verification | Correct pinned file and verified locator |
| Material/formulation transfer unknown or rejected | Appraise existing specification, batch and study evidence | Reasoned material/use correspondence and study-quality judgment |
| Event overlap, alternatives or omitted sources | Inventory/exposure appraisal | Defensible independence and quantified omissions where supported |
| Population, period, units or dose basis differ | Rebuild compatible components or keep separate reports | Documented derivation and matching scope |
| Non-detect bound lost | Analytical record appraisal or targeted measurement if needed | Positive original bound and corresponding sample/material |
| Producer/PBPK context contradicts the calculation | Review retained inputs and denominator | Coherent original context, with unresolved errors cleared by evidence |

No new assay is automatically required. Existing records should be appraised first; exposure/material measurement or kinetics becomes useful only for an identified decision-relevant uncertainty. Issuer authentication is separate from scientific sufficiency. No field in this worksheet supplies an approval or signature.

## Method anchors and verification

This preparation pins [SCCS/1647/22, Notes of Guidance revision 12, corrigendum 2](https://health.ec.europa.eu/document/download/32a999f7-d820-496a-b659-d8c296cc99c1_en?filename=sccs_o_273_final.pdf), originally adopted 15 May 2023 with corrigendum 2 dated 21 December 2023, and [OECD TG 428](https://www.oecd.org/content/dam/oecd/en/publications/reports/2004/11/test-no-428-skin-absorption-in-vitro-method_g1gh4b52/9789264071087-en.pdf), adopted 13 April 2004. TG 428 paragraphs 14 and 18–22 support representative test preparations, exposure/removal, recovery/analysis and reporting. They anchor documentary applicability appraisal rather than requiring a new experiment. Draft revisions or workshop discussions do not replace an adopted method by themselves.

```sh
uv run pytest tests/test_exposure_review_workflow.py tests/test_regulatory_exposure_review_cases.py
uv run ruff check scripts/run_exposure_review.py scripts/exposure_review_models.py
uv run mypy scripts/run_exposure_review.py scripts/exposure_review_models.py
```

Ten independently keyed usability questions are prepared in `evals/exposure_review_questions.v1.md`; expected answers are stored separately in `evals/exposure_review_workflow.v1.xml`. For a future blind exercise, provide the guide, questions, sources, configurations and isolated SDK2 access, and withhold keys and prior transcripts. Retain actual calls and errors. A prepared key or passing tests is not a completed blind-agent score.
