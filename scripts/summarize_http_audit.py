"""Summarize JSONL audit events emitted by streamable-http deployments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from exposure_scenario_mcp.http_audit import load_http_audit_events, summarize_http_audit_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the JSONL audit log.")
    args = parser.parse_args(argv)

    events = load_http_audit_events(args.path)
    print(json.dumps(summarize_http_audit_events(events), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
