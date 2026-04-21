"""Filter and replay JSONL audit events emitted by streamable-http deployments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from exposure_scenario_mcp.http_audit import (
    build_http_audit_replay_report,
    load_http_audit_events,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the JSONL audit log.")
    parser.add_argument(
        "--request-id", help="Filter to a specific requestId from the response header."
    )
    parser.add_argument(
        "--input-digest",
        help="Filter to a normalizedInputDigestSha256 value to group equivalent requests.",
    )
    parser.add_argument("--operation", help="Filter to a specific tool, prompt, or resource name.")
    parser.add_argument(
        "--latest",
        type=int,
        help="Keep only the latest N matching events after other filters are applied.",
    )
    args = parser.parse_args(argv)

    events = load_http_audit_events(args.path)
    report = build_http_audit_replay_report(
        events,
        request_id=args.request_id,
        normalized_input_digest=args.input_digest,
        operation_name=args.operation,
        latest=args.latest,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
