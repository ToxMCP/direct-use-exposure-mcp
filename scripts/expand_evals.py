"""Append new two-zone and worker-tier2 eval Q&A pairs."""

import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = REPO_ROOT / "evals" / "exposure_scenario_mcp_readonly.xml"

NEW_PAIRS = [
    {
        "question": (
            "Inspect the Tier 1 inhalation scenario example. Is the two-zone solver "
            "active for this scenario? Answer with true or false only."
        ),
        "answer": "true",
    },
    {
        "question": (
            "From the Tier 1 inhalation scenario example, what is the exact value of "
            "the solver_variant route metric? Answer exactly."
        ),
        "answer": "two_zone_v1",
    },
    {
        "question": (
            "In the Tier 1 inhalation scenario example, which concentration is higher: "
            "the near-field peak concentration or the far-field peak concentration? "
            "Answer with near_field or far_field only."
        ),
        "answer": "near_field",
    },
    {
        "question": (
            "Look at the worker inhalation tier 2 execution result example. What is the "
            "effectiveWorkerControlFactor route metric value? "
            "Respond with the numeric value only."
        ),
        "answer": "0.7",
    },
    {
        "question": (
            "In the worker inhalation tier 2 execution result example, what is the "
            "templateAlignmentStatus? Answer exactly."
        ),
        "answer": "aligned",
    },
    {
        "question": (
            "From the worker inhalation tier 2 execution result example, what is the "
            "baselineModelFamily route metric? Answer exactly."
        ),
        "answer": "tier1_nf_ff_screening",
    },
]


def main() -> None:
    tree = ET.parse(EVAL_PATH)  # noqa: S314
    root = tree.getroot()

    for pair_data in NEW_PAIRS:
        pair = ET.SubElement(root, "qa_pair")
        q = ET.SubElement(pair, "question")
        q.text = pair_data["question"]
        a = ET.SubElement(pair, "answer")
        a.text = pair_data["answer"]

    # Write back with pretty printing
    ET.indent(root, space="  ")
    tree.write(EVAL_PATH, encoding="utf-8", xml_declaration=True)

    print(f"Added {len(NEW_PAIRS)} new Q&A pairs. Total: {len(root.findall('qa_pair'))}")


if __name__ == "__main__":
    main()
