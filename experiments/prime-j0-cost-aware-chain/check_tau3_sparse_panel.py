#!/usr/bin/env python3
"""Run the frozen three-arm prospective sparse-tau3 operation panel."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

from check_tau3_atlas_panel import arm, int_field


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tau3-sparse-inputs.json"
OUTPUT = ROOT / "tau3-sparse-panel.json"
MODES = ("pos-compact", "tau3-atlas-pos", "tau3-sparse-pos")
ORDERS = (MODES, (MODES[1], MODES[2], MODES[0]),
          (MODES[2], MODES[0], MODES[1]))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_result(case, arms):
    compact, full, sparse = (arms[mode] for mode in MODES)
    curve = case["curve"]["name"]
    compact_entries = 198 if curve == "glv-j0-32" else 378
    sparse_entries = compact_entries * 2
    hot_entries = 324 if curve == "glv-j0-32" else 630
    verified = all(row["verified"] for row in (compact, full, sparse))
    compact_adds, full_adds, sparse_adds = (
        int_field(row, "adds") for row in (compact, full, sparse))
    cold_pairs = int_field(sparse, "sparse_cold_pairs")
    passed = (
        verified and all(value is not None for value in
                         (compact_adds, full_adds, sparse_adds, cold_pairs))
        and sparse_adds < compact_adds
        and sparse_adds >= full_adds
        and sparse_adds - full_adds == cold_pairs
        and int_field(compact, "point_entries") == compact_entries
        and int_field(sparse, "point_entries") == sparse_entries
        and int_field(sparse, "point_table_bytes") == sparse_entries * 32
        and int_field(sparse, "prep_adds") == hot_entries
        and int_field(sparse, "sparse_preparation_checks") == sparse_entries
        and int_field(sparse, "sparse_checks") == 4096
        and int_field(sparse, "fallbacks") == 0
        and int_field(sparse, "sparse_action_fallbacks") == 0
        and int_field(full, "fallbacks") == 0
        and int_field(full, "tau3_action_fallbacks") == 0
        and int_field(full, "tau3_checks") == 4096
        and int_field(full, "tau3_atlas_checks") == 4096
        and sparse.get("fields", {}).get("sparse_action_digest") is not None
        and sparse["fields"]["sparse_action_digest"] ==
        full.get("fields", {}).get("tau3_action_digest")
    )
    return {"case_id": case["id"], "verified": verified, "gate_pass": passed,
            "compact_adds": compact_adds, "full_adds": full_adds,
            "sparse_adds": sparse_adds, "cold_pairs": cold_pairs}


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    if fixture["status"] != "frozen_tau3_sparse_disjoint_fixture":
        raise ValueError("prospective fixture is not frozen")
    receipt = {
        "schema": 1, "status": "prospective_sparse_operation_gate",
        "protocol": "TAU3_SPARSE_HOT.md",
        "runner_sha256": sha256(Path(__file__)),
        "arm_runner_sha256": sha256(ROOT / "check_tau3_atlas_panel.py"),
        "fixture_sha256": sha256(FIXTURE),
        "bench_sha256": sha256(bench),
        "bench_source_sha256": sha256(ROOT / "bench.c"),
        "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
        "atlas_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_atlas.h"),
        "sparse_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_sparse.h"),
        "host_exploratory": {"system": platform.system(), "machine": platform.machine()},
        "isolated_receipt": None, "cpu_timing_claim": None,
        "online_interval": "first target scalar reduction after point preparation through final affine output",
        "rows": [], "pairs": []}
    for index, case in enumerate(fixture["cases"]):
        if sha256(ROOT / case["scalar_file"]) != case["scalar_file_sha256"]:
            raise ValueError(f"changed frozen input: {case['id']}")
        arms = {}
        for mode in ORDERS[index % len(ORDERS)]:
            arms[mode] = arm(bench, case, mode)
            receipt["rows"].append(arms[mode])
        receipt["pairs"].append(pair_result(case, arms))
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["pairs"], indent=2))
    if not all(pair["gate_pass"] for pair in receipt["pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
