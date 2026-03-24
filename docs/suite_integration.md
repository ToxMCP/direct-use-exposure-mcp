# Suite Integration

Exposure Scenario MCP is intended to act as the external-dose engine inside the ToxMCP stack.

## Boundary

- Exposure Scenario MCP owns external dose construction and refinement only.
- PBPK MCP owns internal exposure, TK simulation, and downstream biological interpretation.
- ToxClaw owns orchestration, line-of-evidence handling, refinement choice, and final reporting.

## CompTox

- Use CompTox identity and supporting metadata to enrich requests when available.
- Keep enrichment additive and provenance-rich rather than making it mandatory.
- Preserve upstream identifiers in request metadata or evidence envelopes.

## ToxClaw

- Exposure outputs can be wrapped into evidence envelopes for lightweight orchestration.
- The MCP now exports deterministic ToxClaw-compatible evidence and report primitives:
  evidence record, report evidence reference, and claim-linked report section.
- `exposure_export_toxclaw_refinement_bundle` packages a preserved comparison ledger, an explicit
  `refine_exposure` signal for `exposure_context`, and workflow hooks for comparison,
  route-specific recalculation, aggregate variants, and PBPK export.
- Use refinement bundles to justify exposure refinement decisions without redoing the math inside
  ToxClaw.

## PBPK

- Export only dosing semantics, route, timing, duration, and population context.
- The MCP now exports an exact PBPK MCP `ingest_external_pbpk_bundle` request payload through
  `toolCall.arguments`, with additive exposure-side metadata kept separately for orchestrators
  such as ToxClaw.
- `ready_for_external_pbpk_import=true` means the upstream bundle is mechanically ready to send
  to PBPK MCP. It does not mean PBPK outputs, qualification, or internal-dose estimates already
  exist.
