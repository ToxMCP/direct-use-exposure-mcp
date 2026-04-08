# Direct-Use Exposure MCP Contracts

This folder documents the public contract surface for Direct-Use Exposure MCP.

## Generated Artifacts

- `contract_manifest.json`: machine-readable mapping of tools, resources, prompts, schemas, and examples
- `schemas/`: mirrored JSON Schemas for all public request/response models

## Contract Rules

- Every outward-facing object is versioned.
- All public scenario outputs include provenance, limitations, quality flags, fit-for-purpose metadata, and assumption records.
- All essential tools are deterministic and synchronous in `v0.1.0`.
- Resources are read-only and safe for orchestration-time discovery.
