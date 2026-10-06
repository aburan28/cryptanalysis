#!/usr/bin/env python3
"""Audit four-leaf target coverage before interpreting n83 SAT timeouts.

For a fixed subgroup base A and a uniform nonidentity target Q, each
unordered four-multiset of A has at most one target sum. Consequently
Pr[Q has a four-leaf representation] <= C(|A|+3,4)/(r-1). This bound does
not assume independent or uniformly distributed subset sums. The Poisson
column is a separate heuristic, never a measured relation yield.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from run_probe import HERE, sha

ROOT = HERE.parents[1]
Q1041 = ROOT / "experiments/koblitz-pair-claw-20260929"


def profile(name: str, b: int, r: int, digest: str) -> dict:
    distinct = math.comb(b, 4)
    multisets = math.comb(b + 3, 4)
    mean = distinct / r
    return {
        "name": name,
        "actual_usable_points_B_before_folding": b,
        "subgroup_order_r": r,
        "factor_base_enumerated_set_sha256": digest,
        "distinct_unordered_four_subsets": str(distinct),
        "four_multisets_allowing_repeated_leaves": str(multisets),
        "uniform_nonidentity_target_coverage_upper_bound": min(
            1.0, multisets / (r - 1)),
        "uniform_target_mean_distinct_four_subsets": mean,
        "poisson_coverage_heuristic": -math.expm1(-mean),
    }


def build() -> dict:
    frozen = json.loads((HERE / "protocol.json").read_text())
    p53, p83 = frozen["profiles"]
    q1041_path = Q1041 / "runs/n83_weight5_orbit_base.json"
    q1041 = json.loads(q1041_path.read_text())
    q1041_key_path = Q1041 / q1041["factor_base"]["orbit_key_file"]
    assert q1041["curve_id"] == p83["curve"]["curve_id"]
    assert q1041["curve_identity_record"]["field"] == p83["field"]
    assert q1041["curve_identity_record"]["curve"] == {
        key: value for key, value in p83["curve"].items() if key != "curve_id"}
    assert q1041["isogeny"] == p83["isogeny"] == "none"
    assert sha(q1041_key_path) == q1041["factor_base"][
        "enumerated_set_sha256"]
    assert q1041_key_path.stat().st_size == q1041["factor_base"][
        "orbit_key_file_bytes"]
    profiles = [
        profile("Q1301 n53 normal-x weight <=3", p53["factor_base"][
            "actual_usable_points_B_before_folding"], p53["curve"][
            "subgroup_order"], p53["factor_base"]["enumerated_set_sha256"]),
        profile("Q1302 n83 normal-x weight <=4", p83["factor_base"][
            "actual_usable_points_B_before_folding"], p83["curve"][
            "subgroup_order"], p83["factor_base"]["enumerated_set_sha256"]),
        profile("Q1041 n83 selected normal-x weight 5", q1041["factor_base"][
            "actual_usable_points_B_before_folding"], p83["curve"][
            "subgroup_order"], q1041["factor_base"][
            "enumerated_set_sha256"]),
    ]
    return {
        "kind": "four_summand_uniform_target_support_screen",
        "status": "exact_count_bound_plus_separately_labeled_heuristic",
        "candidate_id": None,
        "proposal_ids": ["Q1301", "Q1302", "Q1041"],
        "profiles": profiles,
        "bound_scope": "uniform nonidentity subgroup target; four unordered base points with repetition permitted; no independence assumption",
        "distinct_mean_scope": "average over all subgroup targets, distinct unordered base points only",
        "poisson_scope": "heuristic independent uniform four-subset sums; not observed coverage or solver success",
        "q1041_receipt_sha256": sha(q1041_path),
        "q1041_point_key_sha256": sha(q1041_key_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    output = HERE / "runs/n83_four_point_support_screen.json"
    content = json.dumps(build(), indent=2) + "\n"
    if output.exists():
        assert output.read_text() == content
    else:
        output.write_text(content)
    print(json.dumps({row["name"]: row[
        "uniform_nonidentity_target_coverage_upper_bound"] for row in
        json.loads(content)["profiles"]}, sort_keys=True))


if __name__ == "__main__":
    main()
