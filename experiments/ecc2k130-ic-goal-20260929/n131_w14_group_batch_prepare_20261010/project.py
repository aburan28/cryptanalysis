#!/usr/bin/env python3
"""Exact full-seed storage/inversion counts and labeled timing projection."""

import hashlib
import json
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOUND = HERE.parent / "n131_w14_fixed_seed_support_gate_20261010/result_bounds.json"
OLD = HERE.parent / "n131_mixed_s3_stream64_20261010/setup.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (HERE / "projection.json").exists()
    bounds = json.loads(BOUND.read_text())
    prior = json.loads(OLD.read_text())
    measured = json.loads((HERE / "result_v2.json").read_text())["setup"]
    assert bounds["status"] == "PASS_EXACT_MASK_PAIR_SUPPORT_BOUND"
    assert bounds["n131"]["usable_unordered_mask_pairs"] == 33780028
    assert measured["usable_mask_pairs"] == prior["usable_mask_pairs"] == 132101
    getcontext().prec = 40
    total_pairs = bounds["n131"]["usable_unordered_mask_pairs"]
    sample_pairs = measured["usable_mask_pairs"]
    total_seeds = 16383
    full_entries = 2*total_pairs
    exact_bytes = 12+6*total_seeds+59*full_entries
    full_inversions = 1+4*total_seeds
    old_inversions = 6*total_pairs
    measured_variable_ns = measured["setup_ns"]-measured["source_ns"]
    extrap_ns = Decimal(measured["source_ns"]) + \
        Decimal(measured_variable_ns)*Decimal(total_pairs)/Decimal(sample_pairs)
    value = {"status": "PASS_EXACT_FULL_SEED_COUNTS_WITH_TIMING_EXTRAPOLATION",
             "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
             "full_seed_count": total_seeds,
             "full_usable_unordered_pairs": total_pairs,
             "full_entries_per_rotation": full_entries,
             "full_packed_index_bytes": exact_bytes,
             "full_rotated_group_field_inversions": full_inversions,
             "full_old_per_pair_field_inversions": old_inversions,
             "sample_seed_count": 64, "sample_pairs": sample_pairs,
             "sample_rotated_group_setup_ns": measured["setup_ns"],
             "sample_source_setup_ns": measured["source_ns"],
             "old_sample_setup_ns": prior["setup_ns"],
             "linear_pair_count_extrapolated_full_setup_seconds": str(extrap_ns/Decimal(10**9)),
             "extrapolation_policy": "target-independent setup only; source setup once, all remaining sample wall proportional to usable pair count; unisolated-host diagnostic, not a bound",
             "full_index_built": False,
             "sha256": {"producer": sha(HERE / "prepare_rotated.cpp"),
                        "sample_result": sha(HERE / "result_v2.json"),
                        "support_bound": sha(BOUND), "prior_setup": sha(OLD)}}
    with (HERE / "projection.json").open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": value["status"],
                      "full_packed_index_bytes": exact_bytes,
                      "full_inversions": full_inversions,
                      "setup_extrapolated_seconds": value["linear_pair_count_extrapolated_full_setup_seconds"]}))


if __name__ == "__main__":
    main()
