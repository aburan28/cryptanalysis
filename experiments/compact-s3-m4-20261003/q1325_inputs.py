#!/usr/bin/env python3
"""Freeze Q1325's complete n83 weight-five base and ordinary workload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, sha


def read_inputs():
    base_path = HERE / "bases/n83_weight5_full_orbits.json"
    base = json.loads(base_path.read_text())
    fb = base["factor_base"]
    key_path = HERE / "bases" / fb["point_key_file"]
    data = key_path.read_bytes()
    assert base["proposal_id"] == "Q1325"
    assert base["candidate_id"] is None and base["isogeny"] == "none"
    assert len(data) == fb["point_key_file_bytes"] == (
        21 * fb["signed_frobenius_columns"])
    assert hashlib.sha256(data).hexdigest() == fb["enumerated_set_sha256"]
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert keys == sorted(set(keys))
    assert fb["actual_usable_points_B_before_folding"] == 166 * len(keys)
    assert fb["normal_basis_weight_bound"] == 5
    assert fb["signed_frobenius_columns"] > 24097
    baseline_path = HERE / "runs/n83_ordinary_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    assert baseline["curve_id"] == base["curve"]["curve_id"]
    assert baseline["workload_id"] == "bab50a1e5f66"
    assert baseline["isogeny"] == "none"
    return base_path, base, key_path, keys, baseline_path, baseline


def frozen_protocol():
    base_path, base, key_path, _, baseline_path, baseline = read_inputs()
    fb = base["factor_base"]
    return {
        "kind": "q1325_full_weight5_projected_s3_stage_protocol",
        "proposal_id": "Q1325", "candidate_id": None,
        "field": base["field"], "curve": base["curve"],
        "isogeny": "none",
        "factor_base": {
            "construction": fb["construction"],
            "normal_basis_weight_bound": 5,
            "nominal_x_mask_count": fb["nominal_x_mask_count"],
            "geometric_point_count_before_projection": fb[
                "geometric_point_count_before_projection"],
            "actual_usable_points_B_before_folding": fb[
                "actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": fb["signed_frobenius_columns"],
            "quotient_rule": fb["quotient_rule"],
            "enumerated_set_sha256": fb["enumerated_set_sha256"],
            "base_receipt_sha256": sha(base_path),
            "point_key_file_sha256": sha(key_path),
        },
        "point_decomposition": {
            "m": 4,
            "summation_chain": "three compact S3 links, two free intermediate x coordinates",
            "leaf_encoding": "four rational nonzero normal-x masks of weight at most five, each mapped by exact cofactor-four x identity",
            "solver": "cryptominisat5, one thread, native XOR",
            "ordinary_wall_limit_seconds": 120,
            "planted_locked_wall_limit_seconds": 30,
            "max_conflicts": 1000000,
            "source_sha256": sha(HERE / "chain_s3_projected_sparse.py"),
        },
        "ordinary_workload_id": baseline["workload_id"],
        "ordinary_public_target": baseline["public_subgroup_target"],
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "planted_control": {
            "normal_x_support_seed": 830525,
            "normal_x_hamming_weight": 5,
            "workload_id": None,
        },
        "relation_collection": None,
        "relation_linear_algebra": None,
        "target_descent": None,
        "complete_solve_cost_log2": None,
        "comparison": "same curve and ordinary public target as Q1302 and Q1324; complete normal-x weight-at-most-five factor base is the controlled change",
        "input_source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "q1325_protocol.json"
    content = json.dumps(frozen_protocol(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert path.read_text() == content
    else:
        assert not path.exists()
        path.write_text(content)
    print(json.dumps({"protocol_sha256": sha(path),
                      "B": frozen_protocol()["factor_base"][
                          "actual_usable_points_B_before_folding"]}))


if __name__ == "__main__":
    main()
