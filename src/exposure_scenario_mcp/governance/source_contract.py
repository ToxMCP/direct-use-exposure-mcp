"""Fail-closed PRODUCER EMISSION-CONTRACT validation for the Track-B gate.

Before projecting a released ``AggregateExposureSummary`` onto the spine, the gate
MUST validate the raw source packet against the producer's STRICT emission contract
— the ``additionalProperties:false`` JSON schema at
``aggregate_exposure_summary.strict.schema.json`` (this directory), which mirrors the
pydantic ``StrictModel`` (``extra='forbid'``) serializer
(``model_dump(mode='json', by_alias=True)``) the real producer
(``exposure_scenario_mcp.runtime`` / ``examples.build_examples``) emits.

WHY THIS GUARD EXISTS (the dead-arm root cause it closes)
---------------------------------------------------------
A gate that projects FIRST and validates never (or validates a projected object,
not the source packet) can "advertise" public-release-blocking codes whose only
trigger is a SOURCE field the producer's own strict contract cannot carry. Such a
code bites only on a hand-crafted, schema-INVALID fixture (one carrying an
undeclared root field, e.g. a smuggled ``smuggledRiskConclusion`` /
``allowedDownstreamUses``) and NEVER on a packet the real producer emits — a DEAD
ARM.

This module is the structural fix: every source/corpus packet is validated against
the strict emission schema at the TOP of ``run_gate`` BEFORE any projection. A
packet that FAILS the producer contract is a ``SOURCE_CONTRACT_VIOLATION`` meta
finding that BLOCKS (exit 1) and is NEVER projected / safe-defaulted. An undeclared
root (or nested) field is rejected here, so the dead-arm class cannot silently
return: a "fault" that only fires a scientific code by carrying a schema-forbidden
field is caught as a contract violation instead.

WHY THE STRICT SCHEMA IS AUTHORED, NOT THE PUBLISHED ONE
--------------------------------------------------------
The published ``docs/contracts/schemas/aggregateExposureSummary.v1.json`` is
``additionalProperties:false`` but its ``required`` list is LAXER than the real
producer (it omits the always-stamped ``schema_version`` / ``scenario_class`` /
``aggregationMode`` / ``uncertaintyTier`` and the default-factory list fields). The
strict schema here DECLARES AND REQUIRES every field the real producer seam stamps,
so it refuses to under-validate. It also uses ``$ref`` / ``$defs`` / ``anyOf`` (for
the nullable optional doses + validation summary), so the validator below supports
exactly that bounded keyword set.

FAIL-CLOSED / DEPENDENCY-FREE
-----------------------------
The validator is a small, self-contained Draft-07 *subset* checker covering exactly
the keywords the emission schema uses (``type``, ``properties``, ``required``,
``enum``, ``const``, ``additionalProperties``, ``items``, ``minItems``,
``minLength``, ``format: date-time``, ``$ref`` to local ``#/$defs/*``, ``anyOf``).
It depends on nothing outside the standard library, so the guard can never be
silently skipped because an optional dependency is missing. A schema we cannot load,
or a keyword we do not recognise appearing in the schema, is itself treated as a
hard block (we refuse to under-validate).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from exposure_scenario_mcp.governance.errors import (
    SOURCE_CONTRACT_VIOLATION,
    BlockingFinding,
)

# --- the advertised meta fail-closed code -----------------------------------
#
# ``SOURCE_CONTRACT_VIOLATION`` (re-exported from ``errors``): the raw source packet
# failed the producer's STRICT emission contract (additionalProperties:false JSON
# schema mirroring the pydantic extra=forbid serializer). BLOCKS; the packet is never
# projected. This is the guard that closes the producer-emission-contract dead-arm
# class.
__all__ = ["SOURCE_CONTRACT_VIOLATION", "validate_source_packet"]

# .../src/exposure_scenario_mcp/governance/source_contract.py -> this directory.
_THIS_DIR = Path(__file__).resolve().parent
_EMISSION_SCHEMA_PATH = _THIS_DIR / "aggregate_exposure_summary.strict.schema.json"

# The exact, bounded set of Draft-07 keywords the emission schema uses. If the
# schema ever grows a keyword outside this set, the loader REFUSES it (fail-closed:
# we will not silently under-validate a contract we cannot fully enforce).
_SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "properties",
        "required",
        "enum",
        "const",
        "additionalProperties",
        "items",
        "minItems",
        "minLength",
        "format",
        "default",
        "anyOf",
    }
)

# RFC3339 date-time (the only ``format`` the schema would use). Mirrors what a strict
# producer emits; tolerant of an offset or a ``Z`` zone, requires a real T-separated
# time. A non-conforming string is a contract violation.
_DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


class SchemaUnsupportedError(Exception):
    """The emission schema uses a keyword the validator does not enforce.

    Raised at load time so the gate fails closed rather than under-validating.
    """


def _assert_supported(node: Any, where: str) -> None:
    """Recursively confirm every schema node uses only enforced keywords.

    Structure-aware: ``properties`` and ``$defs`` map NAMES (arbitrary, not
    keywords) to subschemas, so we recurse into their VALUES only; ``items`` is a
    subschema; ``anyOf`` is a list of subschemas; ``enum`` / ``const`` / ``required``
    carry data values (not subschemas), so they are NOT recursed into. A subschema
    using any keyword outside ``_SUPPORTED_KEYWORDS`` is a hard fail (we refuse to
    under-validate).
    """
    if not isinstance(node, dict):
        return
    for key in node:
        if key not in _SUPPORTED_KEYWORDS:
            raise SchemaUnsupportedError(
                f"Emission schema uses unsupported keyword {key!r} at {where}; "
                "the source-contract validator refuses to under-validate."
            )
    for container in ("properties", "$defs"):
        sub = node.get(container)
        if isinstance(sub, dict):
            for name, subschema in sub.items():
                _assert_supported(subschema, f"{where}.{container}.{name}")
    items = node.get("items")
    if isinstance(items, dict):
        _assert_supported(items, f"{where}.items")
    any_of = node.get("anyOf")
    if isinstance(any_of, list):
        for idx, subschema in enumerate(any_of):
            _assert_supported(subschema, f"{where}.anyOf[{idx}]")


@lru_cache(maxsize=1)
def _emission_schema() -> dict[str, Any]:
    schema = json.loads(_EMISSION_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise SchemaUnsupportedError("Emission schema root is not an object.")
    _assert_supported(schema, "$")
    return schema


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a LOCAL ``#/$defs/<name>`` ref against the schema root.

    Only local ``#/$defs/*`` refs are supported; anything else is fail-closed.
    """
    if not ref.startswith("#/$defs/"):
        raise SchemaUnsupportedError(f"Unsupported non-local $ref {ref!r}.")
    name = ref[len("#/$defs/") :]
    defs = root.get("$defs", {})
    target = defs.get(name) if isinstance(defs, dict) else None
    if not isinstance(target, dict):
        raise SchemaUnsupportedError(f"$ref target not found: {ref!r}.")
    return target


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    # Defensive: an unrecognised type keyword should fail closed at load time, but
    # if one slips through, treat the instance as non-conforming.
    return False


def _validate(
    node: dict[str, Any], value: Any, path: str, errors: list[str], root: dict[str, Any]
) -> None:
    """Validate ``value`` against schema ``node`` (Draft-07 subset), appending every
    violation message to ``errors``."""
    # $ref: resolve and validate against the target (the only key that matters).
    ref = node.get("$ref")
    if isinstance(ref, str):
        _validate(_resolve_ref(ref, root), value, path, errors, root)
        return

    # anyOf: the value must satisfy AT LEAST ONE branch. We collect no per-branch
    # noise; a failure of every branch is a single contract violation.
    any_of = node.get("anyOf")
    if isinstance(any_of, list):
        for branch in any_of:
            branch_errors: list[str] = []
            if isinstance(branch, dict):
                _validate(branch, value, path, branch_errors, root)
            if not branch_errors:
                return
        errors.append(f"{path}: does not match any permitted variant (anyOf)")
        return

    expected_type = node.get("type")
    if isinstance(expected_type, str) and not _type_ok(value, expected_type):
        errors.append(f"{path}: expected type {expected_type!r}")
        return  # type mismatch makes deeper checks meaningless

    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected const {node['const']!r}")

    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {node['enum']!r}")

    if isinstance(value, str):
        min_len = node.get("minLength")
        if isinstance(min_len, int) and len(value) < min_len:
            errors.append(f"{path}: shorter than minLength {min_len}")
        if node.get("format") == "date-time" and not _DATE_TIME_RE.match(value):
            errors.append(f"{path}: not an RFC3339 date-time")

    if isinstance(value, dict):
        props: dict[str, Any] = node.get("properties", {}) or {}
        for req in node.get("required", []) or []:
            if req not in value:
                errors.append(f"{path}: missing required property {req!r}")
        # additionalProperties:false is the load-bearing strict guard — an
        # undeclared root (or nested) field is a contract violation here, which is
        # exactly what closes the dead-arm class.
        if node.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(
                        f"{path}: additional property {key!r} is not permitted "
                        "(producer emission contract is additionalProperties:false)"
                    )
        for key, subschema in props.items():
            if key in value and isinstance(subschema, dict):
                _validate(subschema, value[key], f"{path}.{key}", errors, root)

    if isinstance(value, list):
        min_items = node.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: fewer than minItems {min_items}")
        item_schema = node.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate(item_schema, item, f"{path}[{idx}]", errors, root)


def validate_source_packet(source: Any, *, corpus: str) -> BlockingFinding | None:
    """Validate one raw source packet against the producer's STRICT emission schema.

    Returns a ``SOURCE_CONTRACT_VIOLATION`` blocking meta finding if the packet
    fails the contract (including any undeclared / schema-forbidden field, since the
    schema is ``additionalProperties:false``), else ``None``.

    A schema we cannot load / fully enforce is itself a hard block (fail-closed).
    """
    try:
        schema = _emission_schema()
    except (OSError, json.JSONDecodeError, SchemaUnsupportedError) as exc:
        return BlockingFinding.meta(
            SOURCE_CONTRACT_VIOLATION,
            f"Producer emission schema could not be loaded/enforced: {exc}",
            path="$",
            corpus=corpus,
        )

    errors: list[str] = []
    _validate(schema, source, "$", errors, schema)
    if errors:
        return BlockingFinding.meta(
            SOURCE_CONTRACT_VIOLATION,
            "Source packet violates the producer's strict emission contract "
            f"({_EMISSION_SCHEMA_PATH.name}): " + "; ".join(errors[:8]),
            path=errors[0].split(":", 1)[0] if errors else "$",
            corpus=corpus,
        )
    return None
