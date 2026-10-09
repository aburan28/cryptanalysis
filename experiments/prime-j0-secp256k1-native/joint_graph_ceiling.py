#!/usr/bin/env python3
"""Post-hoc complete-graph ceiling for the frozen joint-design panels."""

import argparse
from collections import Counter
import json
from pathlib import Path

from joint_graph_screen import HERE, choose_one, panel_features, sha
from radius2_graph_screen import matching_atlas
from tau6_comb13_sparse_screen import SPARSE_TOP_ORBITS
from width6_tau_screen import build_width_six_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output exists")
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    selected = set(SPARSE_TOP_ORBITS)
    complete_cardinality = tuple(mask.bit_count() // 2 for mask in range(1 << 12))
    panels = {}
    for panel in ("design", "holdout"):
        receipt_path = HERE / f"joint-graph-{panel}.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["panel"] == panel
        scalars, features, input_hash = panel_features(panel, table, selected)
        assert len(scalars) == receipt["count"] and input_hash == receipt["input_sha256"]
        reference_cardinality = tuple(len(entry) for entry in
                                      matching_atlas(tuple(map(tuple, receipt["reference_edges"]))))
        totals = Counter()
        deltas = Counter()
        for options in features:
            reference = choose_one(options, reference_cardinality)
            complete = choose_one(options, complete_cardinality)
            assert complete[0] <= reference[0]
            totals.update({"cases": 1, "reference_proxy": reference[0],
                           "complete_graph_proxy": complete[0],
                           "reference_mixed_additions": reference[2],
                           "complete_graph_mixed_additions": complete[2],
                           "reference_fusions": reference[5],
                           "complete_graph_fusions": complete[5]})
            deltas[reference[0] - complete[0]] += 1
        assert totals["reference_proxy"] == receipt["totals"]["reference_proxy"]
        gap = totals["reference_proxy"] - totals["complete_graph_proxy"]
        panels[panel] = {"input_sha256": input_hash, "source_receipt_sha256": sha(receipt_path),
                         "totals": dict(totals), "gap_units": gap,
                         "gap_percent_of_reference": 100 * gap / totals["reference_proxy"],
                         "per_case_gap_counts": dict(sorted(deltas.items()))}
    result = {"schema": 1, "status": "post_hoc_diagnostic",
              "scope": "same nine representatives, width-six digits, 13-column comb, and pair-only fusion",
              "complete_graph_edges": 66,
              "complete_graph_slot_bytes": 66 * 81 * 81 * 6 * 72,
              "parent_graph_edges": 33,
              "parent_graph_slot_bytes": 33 * 81 * 81 * 6 * 72,
              "panels": panels, "checker_sha256": sha(Path(__file__))}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "design_gap_percent": panels["design"]["gap_percent_of_reference"],
                      "holdout_gap_percent": panels["holdout"]["gap_percent_of_reference"],
                      "receipt_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
