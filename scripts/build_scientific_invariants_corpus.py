#!/usr/bin/env python3
"""Generate the Track-B scientific-invariants golden corpus from the REAL producer.

The corpus is a byte-faithful capture of the real producer emission
(``exposure_scenario_mcp.examples.build_examples`` -> the two
``aggregateExposureSummary.v1`` summaries), serialized exactly as the production
seam serializes it (``model_dump(mode='json', by_alias=True)`` is what
``build_examples`` already returns). Committing the captured bytes — rather than a
hand-authored fixture — guarantees the gate runs against what the producer actually
emits, so the source-contract guard and the spine projection are exercised on the
genuine released shape.

Run ``uv run python scripts/generate_scientific_invariants_corpus.py`` to (re)write
the fixtures after any intentional producer change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from exposure_scenario_mcp.examples import build_examples  # noqa: E402

CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "governance"

# example key -> committed fixture filename
TARGETS = {
    "aggregate_summary": "aggregate_external_summary.json",
    "aggregate_internal_equivalent_summary": "aggregate_internal_equivalent_summary.json",
}


def main() -> int:
    examples = build_examples()
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for key, filename in TARGETS.items():
        if key not in examples:
            print(f"[corpus] FAIL: example key not found: {key}", file=sys.stderr)
            return 1
        payload = examples[key]
        out = CORPUS_DIR / filename
        out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[corpus] wrote {out.relative_to(REPO_ROOT)} ({len(payload)} top-level keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
