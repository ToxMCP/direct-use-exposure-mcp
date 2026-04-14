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
- Set request-size limits appropriate for the schema surface
- Capture structured access logs with timestamps and client identity

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

Those controls belong to the deployment environment, not the deterministic exposure engine.
