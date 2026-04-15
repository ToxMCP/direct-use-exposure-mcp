# Security Policy

## Supported Versions

The following versions of Direct-Use Exposure MCP are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not open a public issue.**
2. Email the maintainers at the contact address listed in the repository organization profile or open a private security advisory via GitHub.
3. Include a clear description of the issue, steps to reproduce, and any potential impact.
4. Allow reasonable time for assessment and remediation before any public disclosure.

We aim to acknowledge reports within 5 business days and will coordinate fixes and disclosures transparently.

## Security Considerations

- This MCP is designed to run as a deterministic, stateless screening engine.
- For remote deployment, external authentication, TLS termination, and origin allow-listing are required. See [docs/deployment_hardening.md](./docs/deployment_hardening.md).
- The server does not ship built-in identity management or API gateway policy enforcement.
- Input payloads are validated against published JSON Schemas; unbounded inputs should be rate-limited at the deployment boundary.
