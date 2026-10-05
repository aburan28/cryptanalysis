#!/usr/bin/env python3
"""Exact fixed-offset gate for the N83 four-sum root-index continuations.

This is a counting bound for one specified search scheme, not a PDP benchmark.
Offsets are target-independent: one factor-base point for m=5, or one
factor-base point pair for m=6. Each residual is sent to the same complete
four-summand root-index query. The union bound requires at least k offsets
for 50% target coverage when k * C(B+3, 4) / r >= 1/2.
"""

from __future__ import annotations

import hashlib
import json
from math import comb
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
GEOMETRY = HERE / "runs/n83_next_geometry_v1/geometry.json"
FULL = HERE / "runs/n83_w3_pair_root_full_v1/left539.json"
R = 2417851639230796216685689
N = 83


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output: Path) -> None:
    geometry = json.loads(GEOMETRY.read_text())
    full = json.loads(FULL.read_text())
    assert geometry["curve_id"] == full["curve_id"] == "EC1N83Ckb1h2bcb59d56ad6"
    assert full["s3_calls"] == full["s3_roots_found"] == N * 539 * 539
    assert full["left_limit"] == 539
    assert len(geometry["checkpoints"]) == 5
    choices = [(0, 6), (1600, 5), (2000, 5), (4000, 5)]
    rows = []
    for prefix, summands in choices:
        checkpoint = next(
            row for row in geometry["checkpoints"] if row["w4_mask_orbits"] == prefix
        )
        b = checkpoint["actual_usable_projected_points_B"]
        k = checkpoint["effective_signed_frobenius_columns"]
        four_multisets = comb(b + 3, 4)
        assert four_multisets == int(checkpoint["multisets_with_repetition"]["4"])
        states = N * k * k
        assert states == checkpoint["root_index_pair_state_loops_NK2"]
        # ceil(r/(2 M4)); success among fewer fixed offsets has probability < 1/2.
        first_possible_median_offset = (R + 2 * four_multisets - 1) // (2 * four_multisets)
        assert first_possible_median_offset >= 1
        offsets_available = b if summands == 5 else comb(b + 1, 2)
        assert first_possible_median_offset <= offsets_available
        rows.append({
            "method": f"W3+{prefix}W4_m{summands}" if prefix else "W3_m6",
            "w4_mask_orbits": prefix,
            "summands": summands,
            "actual_usable_points_B": b,
            "folded_columns_K": k,
            "four_sum_multiset_count": str(four_multisets),
            "four_sum_support_ceiling_numerator": str(four_multisets),
            "four_sum_support_ceiling_denominator": str(R),
            "minimum_offsets_for_50_percent_union_bound": first_possible_median_offset,
            "complete_four_sum_query_states_per_miss": states,
            "minimum_states_across_preceding_misses_for_median_target": str(
                (first_possible_median_offset - 1) * states
            ),
            "minimum_target_s3_calls_across_preceding_misses_if_two_per_state": str(
                2 * (first_possible_median_offset - 1) * states
            ),
            "claim_boundary": "Only fixed target-independent offsets and exhaustive scans using the existing one-global-orientation-per-state four-sum query. This is not a generic IC lower bound; its sampled orientation may miss valid four-sums.",
        })
    report = {
        "schema_version": 1,
        "kind": "n83_fixed_offset_root_index_cost_screen",
        "curve_id": full["curve_id"],
        "candidate_id": None,
        "subgroup_order": str(R),
        "geometry_sha256": sha(GEOMETRY),
        "full_pair_root_result_sha256": sha(FULL),
        "source_sha256": sha(Path(__file__)),
        "proof": "For a uniform target and any target-independent set of k offsets, each shifted four-sum support has at most C(B+3,4) targets. The union has at most k*C(B+3,4) targets, so 50% success requires k >= ceil(r/(2*C(B+3,4))). Earlier failed exhaustive queries inspect every index state. This bound applies only to the stated offset-and-query scheme.",
        "rows": rows,
        "claim_boundary": "Exact combinatorial and state-count screen, not measured ordinary-query yield, wall time, complete PDP, DLP, or speedup.",
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: n83_next_offset_cost.py output.json")
    main(Path(sys.argv[1]))
