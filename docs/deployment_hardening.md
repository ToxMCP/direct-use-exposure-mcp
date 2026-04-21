# Deployment Hardening Guide

This MCP is safest over `stdio`. If you expose `streamable-http`, enable the built-in boundary
controls first and then layer gateway controls on top.

## Minimum controls

- Shared bearer-token auth for every non-local client
- TLS termination
- Explicit origin allow-list
- Rate limiting
- Request logging and audit retention
- Network scoping so the service is not broadly exposed by default

## First-party server controls

- Set `EXPOSURE_SCENARIO_MCP_HTTP_BEARER_TOKEN` or pass `--http-bearer-token` for
  authenticated access.
- Set `EXPOSURE_SCENARIO_MCP_HTTP_ALLOWED_ORIGINS` or pass `--http-allowed-origin` for any
  browser-based client.
- Keep the default `EXPOSURE_SCENARIO_MCP_HTTP_MAX_REQUEST_BYTES=10485760` unless a reviewed
  workload genuinely needs larger request bodies.
- Set `EXPOSURE_SCENARIO_MCP_HTTP_AUDIT_LOG_PATH` or pass `--http-audit-log-path` to retain a
  request-level JSONL audit trail without persisting raw bodies.
- Keep the default request timeout and concurrency ceiling unless benchmark evidence shows a
  reviewed need to widen them.
- Rotate audit JSONL externally with `logrotate`, container log rotation, or explicit
  per-day/per-release file paths. The server intentionally appends and never truncates in-process.
- Retain enough JSONL history to cover incident review, release rollback, and benchmark drift
  analysis. A reviewed 30- to 90-day retention window is a reasonable default for remote HTTP.
- Treat `0` as an explicit opt-out of the in-process request-size limit, not the default.

## Recommended reverse-proxy posture

- Terminate TLS at a gateway or reverse proxy
- Keep upstream authentication in place even when the in-process bearer token is enabled
- Restrict allowed origins to trusted clients only, especially for browser-based sessions
- Keep request-size limits at the gateway as a second boundary (suggest ≤10 MB)
- Set gateway-level request timeouts (suggest 30–60 s for screening tools, 120 s for envelope or probability-bound builds)
- Capture structured access logs with timestamps and client identity

## Replay and forensic workflow

- Capture the `X-Exposure-Audit-Request-Id` response header from the calling client or access log.
- Use `python scripts/replay_http_audit.py /path/to/http-audit.jsonl --request-id <id>` to isolate
  a single exchange without storing the raw request body.
- Use `python scripts/replay_http_audit.py /path/to/http-audit.jsonl --input-digest <sha256>` to
  group logically identical JSON-RPC requests that differ only in key order or redacted secrets.
- Match the event defaults and release fingerprints against `defaults://manifest` and
  `release://metadata-report` before replaying a scenario downstream.

## Request and execution guardrails

- Input schemas enforce `max_length` on the highest-volume list fields (e.g. aggregate component scenarios, evidence reconciliation records).
- Very large payloads are rejected by the in-process request-size limit when it is enabled and
  should also be rejected at the gateway or reverse-proxy layer.
- Long-running calculations (Tier B envelopes, Tier C probability bounds, integrated workflows) are bounded but not internally timed-out. Set upstream timeouts based on your latency requirements.

## Operator expectations

- Prefer `127.0.0.1` binding for local development
- Treat unauthenticated public exposure as unsupported
- Re-run release verification after transport or deployment changes
- Keep release posture and warning-level findings visible to downstream users

## Non-goals

This MCP now ships:

- bearer-token auth, origin allow-list enforcement, request-size limits, request timeouts,
  concurrency limits, and append-only JSONL audit events for `streamable-http`

This MCP still does not ship:

- full identity management
- built-in TLS termination
- turnkey public SaaS deployment controls
- API gateway policy enforcement
Those controls still belong to the deployment environment, not the deterministic exposure engine.
