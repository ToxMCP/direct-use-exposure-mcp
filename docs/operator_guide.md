# Operator Guide

## Runtime Modes

- Use `stdio` for local agent-to-server execution. This is the safest default.
- Use `streamable-http` only when you can configure boundary controls intentionally.
- For remote HTTP, prefer shared bearer-token auth, an explicit origin allow-list, and a request
  size limit even before you add gateway TLS or rate limiting.
- For remote HTTP, enable the built-in JSONL audit sink, request timeout, and concurrency ceiling
  before relying on gateway-only observability.
- Prefer deterministic screening tools for route-specific scenario construction and use export tools only after the scenario is auditable.

## Standard Validation

Run these commands before changing defaults, schemas, or plugins:

```bash
uv run ruff check .
uv run pytest
uv run generate-exposure-contracts
```

## Interpretation Guardrails

- Treat every output as external-exposure context only.
- Do not reinterpret screening outputs as internal dose, BER, PoD, or final risk conclusions.
- Review `qualityFlags`, `limitations`, and `provenance` before using any scenario downstream.

## Operational Checklist

- Confirm the defaults manifest version and SHA256 before benchmark or release runs.
- Regenerate contracts whenever public schemas, examples, tools, or resources change.
- If `streamable-http` is exposed, configure `EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN`, set
  `EXPOSURE_SCENARIO_MCP_HTTP_ALLOWED_ORIGINS` for browser clients, and keep the default request
  size limit unless you have a reviewed reason to widen it.
- Set `EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH`, keep the default request timeout unless a
  reviewed workload needs longer execution, and only widen concurrency deliberately.
- Follow `docs/release_runbook.md` for releases and `docs/maintainer_operating_model.md` for the
  monthly triage and release-buddy cadence.
- Use `python scripts/summarize_http_audit.py <path>` for fleet-level counts and
  `python scripts/replay_http_audit.py <path> --request-id <id>` for request-level debugging.
- Keep `docs://http-audit-operations-guide` available to operators who need to trace a result
  back to a defaults manifest and release metadata snapshot.
- Keep downstream orchestration-layer and PBPK handoffs explicit; do not add hidden transformation logic in clients.
