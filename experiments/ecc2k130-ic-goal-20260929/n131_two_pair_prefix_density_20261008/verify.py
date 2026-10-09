#!/usr/bin/env python3
"""Independent arithmetic and cross-artifact audit of the density gate."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    out = HERE / "verification.json"
    if out.exists():
        raise FileExistsError("preserve first audit")
    protocol = load(HERE / "protocol.json")
    freeze = load(HERE / "freeze.json")
    census = load(HERE / "n41_census.json")
    bound = load(HERE / "bound.json")
    frontier_path = (HERE / protocol["n131_frontier_source"]).resolve()
    frontier = load(frontier_path)
    reference = load(GOAL / "q1448_pair_bloom/result.json")
    sage_audit = load(GOAL / "q1448_pair_bloom/sage_audit_v2.json")
    complete_rows = load(GOAL / "n41_w6_s8_all_rows/rows.json")
    prior_batch = load(GOAL / "n41_two_free_pair_s3_norm_20261008/native_search.json")

    assert freeze["status"] == "FROZEN_BEFORE_N41_CENSUS"
    for name in ("protocol", "source", "binary", "input"):
        path = {"protocol": HERE / "protocol.json", "source": HERE / "census.cpp",
                "binary": HERE / "census", "input": (HERE / protocol["n41_input"]).resolve()}[name]
        assert sha(path) == freeze[f"{name}_sha256"]
    assert sha(frontier_path) == protocol["n131_frontier_sha256"]
    assert bound["source_sha256"]["source"] == sha(HERE / "bound.py")
    assert bound["source_sha256"]["n41_census"] == sha(HERE / "n41_census.json")
    assert census["status"] == "COMPLETE_CENSUS"
    assert census["target"] == protocol["n41_public_target"] == reference["target"]
    assert census["pair_list_sizes"] == [1956] * 4
    assert census["raw_completion_combinations"] == 1956**2
    assert census["distinct_completion_points"] == census["raw_completion_combinations"]
    assert census["identity_raw_combinations"] == 0
    assert census["prefixes_seen"] == 1956**2
    assert census["admissible_prefixes"] + census["prefix_column_rejects"] == 1956**2
    assert census["sumset_hits"] == census["exact_pair_witnesses"] == 20
    assert census["sumset_hits"] == census["complete_rows"] + census["full_column_rejects"]
    assert census["complete_rows"] == len(complete_rows) == 12
    assert census["first_valid_index"] == reference["second_pair_states"] == 513088
    assert census["first_row"] == reference["row"]
    assert sage_audit["status"] == "PASS"
    assert prior_batch["status"] == "ONLINE_TIME_CAP"
    assert prior_batch["residuals"] < census["first_hit_index"]
    assert prior_batch["x_hits"] == 0

    subgroup = int(frontier["subgroup_order"])
    signed_points = frontier["slot_usable_points_B"]
    pair_upper = math.comb(signed_points, 2)
    p_upper = Fraction(pair_upper * pair_upper, subgroup - 1)
    minimum = (p_upper.denominator + 2 * p_upper.numerator - 1) // (2 * p_upper.numerator)
    assert pair_upper == int(bound["n131"]["unordered_pair_states_per_domain_upper"])
    assert pair_upper**2 == int(bound["n131"]["two_free_pair_completion_support_upper"])
    assert minimum == int(bound["n131"]["prefixes_necessary_for_50_percent_success_by_union_bound"])
    recorded = bound["n131"]["single_target_independent_prefix_success_upper_fraction"]
    assert p_upper == Fraction(int(recorded["numerator"]), int(recorded["denominator"]))
    p41 = Fraction(census["distinct_completion_points"], census["subgroup_order"] - 1)
    recorded41 = bound["n41"]["uniform_nonidentity_residual_hit_fraction"]
    assert p41 == Fraction(int(recorded41["numerator"]), int(recorded41["denominator"]))

    report = {
        "kind": "two_fixed_pair_prefix_density_independent_audit",
        "status": "PASS",
        "proposal_id": protocol["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "n41_exact_support_size": census["distinct_completion_points"],
        "n41_group_hits": census["sumset_hits"],
        "n41_eight_column_rows": census["complete_rows"],
        "n131_union_bound_minimum_prefixes": str(minimum),
        "prior_independent_sage_row_audit_sha256": sha(GOAL / "q1448_pair_bloom/sage_audit_v2.json"),
        "source_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "freeze.json", "census.cpp", "census",
            "n41_census.json", "bound.py", "bound.json")},
    }
    out.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
