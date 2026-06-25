"""Track-B scientific-invariants governance layer.

This package projects direct-use-exposure-mcp's released scientific object
(``aggregateExposureSummary.v1``) onto the canonical ToxMCP schema-spine shapes
and runs the vendored, digest-pinned spine policy engine over them via a
fail-closed Node bridge. It is a *regression tripwire* + proof-of-machinery:
direct-use-exposure-mcp is deterministic and non-LLM and already enforces these
invariants natively, so on the pristine corpus the gate is GREEN — its job is to
BLOCK if a future change ever lets an external-exposure-as-internal-dose /
risk / regulatory overclaim, or a dropped uncertainty/confidence-ceiling, leak
into a released object.

Modules:
    errors           — the blocking-failure model + meta fail-closed codes.
    source_contract  — fail-closed producer STRICT emission-contract guard.
    spine_bridge     — fail-closed Node shell-out to the vendored engine.
    project_to_spine — total, deterministic projection summary -> spine objects.
"""

from exposure_scenario_mcp.governance.errors import (
    BlockingFinding,
    ProjectionIncompleteError,
)

__all__ = ["BlockingFinding", "ProjectionIncompleteError"]
