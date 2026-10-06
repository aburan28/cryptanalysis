#!/usr/bin/env python3
"""Freeze Q1324 against Q1041's exact n83 weight-five subgroup base."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from run_probe import HERE, ROOT, field, sha

Q1041 = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(Q1041))
from orbit_key import OrbitKey  # noqa: E402


def read_inputs():
    base_path = Q1041 / "runs/n83_weight5_orbit_base.json"
    base = json.loads(base_path.read_text())
    point_key_path = Q1041 / base["factor_base"]["orbit_key_file"]
    data = point_key_path.read_bytes()
    fb = base["factor_base"]
    assert len(data) == fb["orbit_key_file_bytes"] == 21 * 24097
    assert hashlib.sha256(data).hexdigest() == fb["enumerated_set_sha256"]
    assert base["proposal_id"] == "Q1041"
    assert base["candidate_id"] is None and base["isogeny"] == "none"
    assert fb["actual_usable_points_B_before_folding"] == 166 * 24097
    assert fb["signed_frobenius_columns"] == 24097

    baseline_path = HERE / "runs/n83_ordinary_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    assert baseline["curve_id"] == base["curve_id"]
    assert baseline["isogeny"] == "none"
    assert baseline["workload_id"] == "bab50a1e5f66"
    assert baseline["protocol_sha256"] == sha(HERE / "protocol.json")

    onb = field.Onb(83)
    orbit = OrbitKey(onb)
    point_keys = [int.from_bytes(data[i:i + 21], "little")
                  for i in range(0, len(data), 21)]
    assert point_keys == sorted(set(point_keys))
    xkeys = sorted(onb.toCoords(orbit.point_from_key(key)[0])
                   for key in point_keys)
    assert len(xkeys) == len(set(xkeys)) == 24097
    x_data = b"".join(key.to_bytes(11, "little") for key in xkeys)
    return base_path, base, point_key_path, baseline_path, baseline, xkeys, (
        hashlib.sha256(x_data).hexdigest())


def frozen_protocol():
    (base_path, base, point_key_path, baseline_path, baseline, xkeys,
     x_digest) = read_inputs()
    fb = base["factor_base"]
    return {
        "kind": "q1324_exact_weight5_four_summand_stage_protocol",
        "proposal_id": "Q1324",
        "candidate_id": None,
        "field": base["curve_identity_record"]["field"],
        "curve": dict(base["curve_identity_record"]["curve"],
                      curve_id=base["curve_id"]),
        "isogeny": "none",
        "factor_base": {
            "source_proposal_id": "Q1041",
            "construction": fb["construction"],
            "normal_x_hamming_weight": fb["normal_x_hamming_weight"],
            "normal_x_support_seed": fb["normal_x_support_seed"],
            "actual_usable_points_B_before_folding": fb[
                "actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": fb["signed_frobenius_columns"],
            "enumerated_set_sha256": fb["enumerated_set_sha256"],
            "derived_representative_x_sha256": x_digest,
            "point_key_file_sha256": sha(point_key_path),
            "base_receipt_sha256": sha(base_path),
        },
        "point_decomposition": {
            "m": 4,
            "summation_chain": "three compact S3 links, two free intermediate x coordinates",
            "leaf_encoding": "four ordered exact Q1041 subgroup x-orbit selectors plus Frobenius shifts",
            "solver": "cryptominisat5, one thread, native XOR",
            "ordinary_wall_limit_seconds": 120,
            "planted_locked_wall_limit_seconds": 30,
            "max_conflicts": 1000000,
            "source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        },
        "ordinary_workload_id": baseline["workload_id"],
        "ordinary_public_target": baseline["public_subgroup_target"],
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "planted_control": {
            "representative_indices": [101, 137, 231, 499],
            "frobenius_shifts": [2, 7, 11, 19],
            "signs": [1, -1, 1, -1],
            "workload_id": None,
        },
        "relation_collection": None,
        "relation_linear_algebra": None,
        "target_descent": None,
        "complete_solve_cost_log2": None,
        "comparison": "same curve and ordinary public target as Q1302; factor-base construction and size change explicitly",
        "input_source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "q1324_protocol.json"
    content = json.dumps(frozen_protocol(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert path.read_text() == content
    else:
        assert not path.exists()
        path.write_text(content)
    print(json.dumps({"protocol_sha256": sha(path),
                      "derived_representative_x_sha256": (
                          frozen_protocol()["factor_base"][
                              "derived_representative_x_sha256"])}))


if __name__ == "__main__":
    main()
