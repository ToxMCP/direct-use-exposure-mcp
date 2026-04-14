# Red-Team Review Memo

This memo captures hostile-review arguments that a skeptical toxicologist, exposure physicist,
or regulator could use to attack Direct-Use Exposure MCP, then evaluates which criticisms are
substantive, which are overstated, and what the repo should do next.

It is not a marketing defense. It is a structured adversarial review artifact intended to keep
the MCP scientifically honest.

## Review Position

The strongest current risk is not that the MCP is opaque. It is that a highly governed system
could be mistaken for high-certainty science when some branches are still bounded screening
approximations. The memo therefore focuses on:

- where criticism is valid
- what the repo already does to mitigate it
- what still remains weak
- what concrete fixes would harden the system

## Attack Matrix

### 1. Transparency by Exhaustion

- Criticism:
  Huge provenance bundles can overwhelm human reviewers and create practical rather than true
  auditability.
- Validity:
  Partly valid.
- Current mitigation:
  The repo publishes machine-readable provenance, assumptions, limitations, validation, release,
  and verification artifacts so nothing is hidden.
- Remaining gap:
  Human review still takes too much manual triage because the most important assumptions are not
  always compressed into a short first-page summary.
- Recommended fix:
  Publish a layered audit view:
  - one-page human review digest
  - route-level assumption summary
  - expandable full provenance bundle beneath it

### 2. Automated Ignorance / Default Trap

- Criticism:
  Defaults can make it too easy to generate a polished-looking result from heuristic inputs.
- Validity:
  Valid.
- Current mitigation:
  Defaults are versioned, source-tagged, surfaced in provenance, and carried through quality flags,
  limitations, and validation posture.
- Remaining gap:
  Some default-heavy scenarios are still too easy to run without a strong enough downgrade in
  fit-for-purpose language.
- Recommended fix:
  Make heavy default use more adversarial:
  - stronger fit-for-purpose penalties
  - unavoidable warning language
  - explicit human sign-off requirement for low-evidence scenarios

### 3. Scientific Anachronism

- Criticism:
  Older empirical models can be made to look more modern than they really are.
- Validity:
  Partly valid.
- Current mitigation:
  The repo explicitly labels bounded worker and dermal branches as screening or surrogate logic,
  not full molecular or high-tier physics.
- Remaining gap:
  Some users may still overread “mechanistic” language when the engine is using bounded empirical
  constructs rather than high-tier mechanistic simulation.
- Recommended fix:
  Keep model-family naming explicit and conservative:
  - identify empirical regressions by name
  - state main break conditions
  - avoid implying molecular or CFD-grade realism

### 4. Systemic Risk / Monoculture

- Criticism:
  A unified engine can become a single point of failure if a defect propagates across many dossiers.
- Validity:
  Strongly valid.
- Current mitigation:
  The repo already has:
  - benchmark regression
  - goldset linkage
  - defaults versioning
  - release metadata
  - executable validation checks
  - explicit readiness and security/provenance posture
- Remaining gap:
  The strongest remaining defense is social and operational, not just technical:
  independent comparison against other tools and external review cadence.
- Recommended fix:
  Treat this as a governance requirement:
  - cross-tool comparison sets
  - version-pinned dossier outputs
  - explicit migration/drift notes between defaults versions
  - periodic external red-team review

### 5. Expertise Erasure

- Criticism:
  A structured engine can be mistaken for an automated final decision-maker.
- Validity:
  Only if the system is presented badly.
- Current mitigation:
  The repo is explicit that it does not own PBPK execution, BER, WoE, PoD, or final risk
  conclusions.
- Remaining gap:
  Users can still operationally misuse a well-typed engine if downstream process discipline is weak.
- Recommended fix:
  Make expert-review boundaries impossible to miss in operator-facing outputs and workflow docs.

### 6. Aerosol Pseudoscience / Precision without Accuracy

- Criticism:
  Fixed aerosol interpretation factors can look more precise than the underlying evidence deserves.
- Validity:
  Valid.
- Current mitigation:
  The repo now applies bounded aerosol semantics with explicit assumptions, subtype/family logic,
  and quality flags rather than hiding them in one constant.
- Remaining gap:
  Some bounded aerosol branches still risk overstating precision when the underlying determinant is
  heuristic.
- Recommended fix:
  Reduce false precision in heuristic branches:
  - round proxy-driven outputs more conservatively
  - label them as screening-resolution outputs
  - keep family-specific anchors growing where official label or validation evidence exists

## Overall Assessment

- The memo does **not** support stopping development.
- It does support continuing with stricter communication and stronger evidence penalties.
- The repo’s strongest defense is not that it is perfect. It is that it is explicit about what is
  benchmarked, heuristic, bounded, externally anchored, and still human-review-dependent.

## Best Next Hardening Steps

1. Add a human-first audit digest resource.
2. Increase fit-for-purpose penalties for default-heavy scenarios.
3. Reduce false precision on heuristic-only branches.
4. Keep expanding external executable anchors before broadening scope.
5. Maintain periodic adversarial review as a first-class governance artifact.

## Bottom Line

The right answer to hostile criticism is not to deny uncertainty. It is to show that uncertainty,
defaults, model limits, and validation posture are already first-class and to keep making the
human-review surface more usable.
