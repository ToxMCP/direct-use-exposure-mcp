# Guided Tutorial: Deterministic Regulatory Screening

This walkthrough uses checked-in examples so the tutorial stays reproducible and CI can detect drift.

## Goal

Build a direct-use dermal screening scenario, inspect the audit surface, and understand what can and cannot be handed downstream.

## Sample input

- Request JSON: [`schemas/examples/screening_dermal_request.json`](../../schemas/examples/screening_dermal_request.json)
- Result JSON: [`schemas/examples/screening_dermal_scenario.json`](../../schemas/examples/screening_dermal_scenario.json)

## What to inspect

1. Confirm the route, scenario class, and dose unit stay explicit in the request and result.
2. Review `qualityFlags`, `limitations`, and `provenance` before treating the result as a reusable exposure object.
3. Treat the scenario as external-dose screening context only. Do not reinterpret it as BER, PoD, or final risk output.

## Suggested prompts

- `exposure_refinement_playbook`
- `exposure_evidence_reconciliation_brief`
- `exposure_pbpk_handoff_checklist`

## Operator reminder

If you expose `streamable-http`, pair this walkthrough with `EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH` so request-level audit events survive beyond stdout logs.
