# Deployment Hardening Guide

This MCP is safest over `stdio`. If you expose `streamable-http`, harden the deployment externally.

## Minimum controls

- Authentication in front of the MCP service
- TLS termination
- Explicit origin allow-list
- Rate limiting
- Request logging and audit retention
- Network scoping so the service is not broadly exposed by default

## Recommended reverse-proxy posture

- Terminate TLS at a gateway or reverse proxy
- Enforce bearer-token or equivalent upstream authentication
- Restrict allowed origins to trusted clients only
- Set request-size limits appropriate for the schema surface (suggest ≤10 MB)
- Set gateway-level request timeouts (suggest 30–60 s for screening tools, 120 s for envelope or probability-bound builds)
- Capture structured access logs with timestamps and client identity

## Request and execution guardrails

- Input schemas enforce `max_length` on the highest-volume list fields (e.g. aggregate component scenarios, evidence reconciliation records).
- Very large payloads should be rejected at the gateway or reverse-proxy layer before they reach the deterministic engine.
- Long-running calculations (Tier B envelopes, Tier C probability bounds, integrated workflows) are bounded but not internally timed-out. Set upstream timeouts based on your latency requirements.

## Operator expectations

- Prefer `127.0.0.1` binding for local development
- Treat unauthenticated public exposure as unsupported
- Re-run release verification after transport or deployment changes
- Keep release posture and warning-level findings visible to downstream users

## Non-goals

This MCP does not ship:

- built-in identity management
- built-in API gateway policy enforcement
- turnkey public SaaS deployment controls
- internal execution timeouts or request-size middleware (these belong at the deployment boundary)

Those controls belong to the deployment environment, not the deterministic exposure engine.
