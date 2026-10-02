# SDK2 candidate compatibility

The v0.3.0 candidate pins the stable Python MCP SDK 2.2.0. The currently published
release remains v0.2.1 until a separate release is approved and published.

## Client behavior

The existing stdio command, HTTP `/mcp` path, 39 tool names, 63 fixed resources,
two resource templates, and two prompts remain available. Input/output fields,
units, algorithms, defaults packs, qualification limits, and scientific result
metadata retain their meanings. Application version fields advertise v0.3.0.

Older clients still initialize using the 2024-11-05, 2025-03-26, 2025-06-18, or
2025-11-25 protocol. SDK2 clients can discover the 2026-07-28 protocol and make
stateless requests. Catalogs advertise a 60-second private cache hint. Scientific
results receive no reusable cache lifetime. Modern result envelopes add
`resultType` and server identity; optional null result metadata is omitted by the
modern serializer. Application scientific payloads retain their fields.

Domain failures continue to set `isError=true`. SDK1's output validator sometimes
masked these failures with a generic model-validation error. SDK2 returns the
intended domain message and `_meta.errorCode`/`_meta.mcpErrorCode`. Callers should
check `isError` and use the domain code rather than matching the old SDK's
validation-error text.

## Operators

`HOST`, `PORT`, `LOG_LEVEL`, `--host`, and `--port` retain their roles. HTTP uses
stateless JSON responses for both protocol generations; these pure calculation
tools require no protocol session or callback channel. Application runtime state
is still shared within one server and initialized once under a lock.

Host and Origin validation is always enabled. Local development works with the
default loopback allowlists. Hosted operators must configure the gateway's exact
names, for example:

```bash
DIRECT_USE_MCP_ALLOWED_HOSTS=exposure.example.org
DIRECT_USE_MCP_ALLOWED_ORIGINS=https://client.example.org
```

Keep the existing authenticated reverse proxy/gateway boundary. An allowlist
does not authenticate callers. `DIRECT_USE_MCP_MAX_REQUEST_BYTES` controls the
positive body limit; the default is 4 MiB. Empty allowlists and nonpositive
limits fail during startup. MCP-prefixed SDK1 transport environment variables
are replaced by these explicit application settings.

## Python embedding

SDK2 renames `FastMCP` to `MCPServer`, moves wire models to `mcp_types`, uses
snake_case Python attributes, and exposes transport options on app/run methods.
Use `create_mcp_server()` and the new `transport.http.create_http_app()` factory.
Direct `call_tool()` returns `CallToolResult`; use `is_error` and
`structured_content`. JSON-RPC aliases such as `isError` and `structuredContent`
remain unchanged. The server version now uses the public constructor parameter.

Sync tools run in SDK worker threads. Registries and scientific inputs are read
only, and concurrent cold starts coalesce into one provider initialization.
Resource error adaptation calls the SDK's public `read_resource()` API and
preserves the project's error data without re-registering private SDK handlers.

## Verification and rollback

The released v0.2.1 wheel and actual SDK1.30 client establish the catalog baseline.
The pre-version-bump SDK2 wheel matches all successful calculation/resource
payloads exactly when invocation clocks and UUIDs are fixed in a test-only
launcher. Production UUIDs and clocks remain unchanged. The candidate's installed
wheel is exercised by SDK1.30 and SDK2.2 clients over stdio and HTTP; every
application result must match across the four combinations. Only seven schema
defaults containing the application version are normalized in the catalog
fingerprint; all other schema fields must match the released wheel.

HTTP tests cover routing headers, all supported older protocol dates, body
limits, Host/Origin rejection, malformed requests, resource/domain errors,
parallel real calls with repeated request IDs, cancellation recovery, and no
artifact writes. Existing numerical, governance, packaging, and security gates
remain required. This change adds no new scientific capabilities or qualification.

To roll back, use the published v0.2.1 wheel/container and its frozen lockfile.
The migration changes no stored scientific data or defaults format.

Reference: [official SDK migration guide](https://py.sdk.modelcontextprotocol.io/migration/).
