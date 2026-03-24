# Operator Guide

## Runtime Modes

- Use `stdio` for local agent-to-server execution. This is the safest default.
- Use `streamable-http` only when the server is behind trusted network controls.
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
- Keep ToxClaw and PBPK handoffs explicit; do not add hidden transformation logic in clients.
