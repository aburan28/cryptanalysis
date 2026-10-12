#!/usr/bin/env python3
"""Freeze Q1512 ordinary N83 raw-x prefilter comparison."""
import hashlib
import json
import platform
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
INPUTS = PARENT / "q20261012_n83_complement_pair_probe/frozen_inputs.json"
Q1505 = PARENT / "q20261012_n83_deferred_y_scan/result.json"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1512-native-prefilter")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (HERE / "protocol.json").exists()
    inputs = json.loads(INPUTS.read_text())
    baseline = json.loads(Q1505.read_text())
    predecessor = json.loads((Q1505.parent / "protocol.json").read_text())
    assert sha(BASE) == predecessor["base_point_file_sha256"]
    assert sha(INPUTS) == predecessor["frozen_inputs_sha256"]
    assert baseline["proposal_id"] == "Q1505"
    assert baseline["curve_id"] == predecessor["curve_id"]
    assert baseline["factor_base_actual_B"] == predecessor["factor_base_actual_B"]
    assert baseline["factor_base_folded_columns_K"] == predecessor["factor_base_folded_columns_K"]
    assert BINARY.exists()
    ordinary = {}
    for label in ("selected", "holdout"):
        comp = inputs["inputs"][label]["complements"][0]
        ordinary[label] = {"workload_id": inputs["inputs"][label]["workload_id"],
                           "complement_index": 0, "signs": comp["signs"],
                           "x_onb_hex": comp["x_onb_hex"],
                           "y_onb_hex": comp["y_onb_hex"]}
    protocol = {
        "proposal_id": "Q1512", "candidate_id": None, "run_id": None,
        "curve_id": predecessor["curve_id"], "isogeny": "none",
        "factor_base_actual_B": predecessor["factor_base_actual_B"],
        "factor_base_folded_columns_K": predecessor["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": sha(BASE),
        "point_decomposition_stage_code": "PDP4hybrid",
        "change": "Bloom over raw x of every signed-Frobenius orbit point before exact canonical-x membership",
        "source_sha256": sha(HERE / "native_prefilter.cpp"),
        "binary_sha256": sha(BINARY),
        "parent_native_source_sha256": sha(Q1505.parent / "native_deferred_y.cpp"),
        "base_point_file_sha256": sha(BASE),
        "frozen_inputs_sha256": sha(INPUTS),
        "q1505_result_sha256": sha(Q1505),
        "ordinary_inputs": ordinary,
        "screen_pair_count": 2000000,
        "full_pair_count": predecessor["scan_pairs_per_complement"],
        "batch_pairs": predecessor["primary_batch_pairs"],
        "screen_modes": [[0, 0], [26, 4], [27, 4], [28, 4], [29, 4], [27, 6], [28, 6]],
        "full_modes_in_run_order": [["selected", 0, 0], ["selected", 27, 4],
                                    ["selected", 28, 4], ["holdout", 28, 4],
                                    ["holdout", 27, 4], ["holdout", 0, 0]],
        "wall_cap_seconds_per_cell": 180,
        "host_isolation": "none; exact counters primary, wall times exploratory",
        "machine": {"architecture": platform.machine(), "system": platform.system()},
        "complete_n131_solve_operation_log2": None,
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print("FROZEN Q1512", protocol["curve_id"], protocol["binary_sha256"])


if __name__ == "__main__":
    main()
