#!/usr/bin/env python3
"""Prospective paired sparse versus exact radix-27 block-path experiment."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

from check_tau3_atlas_panel import arm, int_field


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "tau3-radix27-inputs.json"
OUTPUT = ROOT / "tau3-radix27-panel.json"
MODES = ("tau3-sparse-pos", "tau3-radix27-pos")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_result(case, arms):
    baseline, candidate = (arms[mode] for mode in MODES)
    verified = baseline["verified"] and candidate["verified"]
    sparse_adds = int_field(baseline, "adds")
    optimal_adds = int_field(candidate, "adds")
    entries = 396 if case["curve"]["name"] == "glv-j0-32" else 756
    passed = (verified and sparse_adds is not None and optimal_adds is not None
              and optimal_adds < sparse_adds
              and int_field(candidate, "point_entries") == entries
              and int_field(candidate, "point_table_bytes") == entries * 32
              and int_field(candidate, "prep_adds") == (324 if entries == 396 else 630)
              and int_field(candidate, "sparse_preparation_checks") == entries
              and int_field(candidate, "radix27_checks") == 4096
              and int_field(candidate, "radix27_action_fallbacks") == 0
              and int_field(candidate, "fallbacks") == 0
              and int_field(baseline, "fallbacks") == 0
              and int_field(candidate, "radix27_dp_states") is not None
              and int_field(candidate, "radix27_dp_states") > 0
              and int_field(candidate, "radix27_dp_options") is not None
              and int_field(candidate, "radix27_dp_options") > 0
              and int_field(candidate, "static_map_bytes") == 55222
              and int_field(candidate, "online_scratch_bytes") == 53312)
    return {"case_id": case["id"], "verified": verified, "gate_pass": passed,
            "sparse_adds": sparse_adds, "radix27_adds": optimal_adds,
            "dp_states": int_field(candidate, "radix27_dp_states"),
            "dp_options": int_field(candidate, "radix27_dp_options")}


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    if fixture["status"] != "frozen_tau3_radix27_disjoint_fixture":
        raise ValueError("prospective radix-27 fixture is not frozen")
    receipt = {"schema": 1, "status": "prospective_radix27_operation_gate",
               "protocol": "TAU3_RADIX27_PATH.md",
               "runner_sha256": sha256(Path(__file__)),
               "arm_runner_sha256": sha256(ROOT / "check_tau3_atlas_panel.py"),
               "fixture_sha256": sha256(FIXTURE),
               "bench_sha256": sha256(bench),
               "bench_source_sha256": sha256(ROOT / "bench.c"),
               "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
               "map_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_radix27.h"),
               "host_exploratory": {"system": platform.system(),
                                    "machine": platform.machine()},
               "isolated_receipt": None, "cpu_timing_claim": None,
               "online_interval": "first scalar lattice reduction after point preparation through final affine output",
               "rows": [], "pairs": []}
    for index, case in enumerate(fixture["cases"]):
        if sha256(ROOT / case["scalar_file"]) != case["scalar_file_sha256"]:
            raise ValueError(f"changed frozen scalar file: {case['id']}")
        order = MODES if index % 2 == 0 else tuple(reversed(MODES))
        arms = {}
        for mode in order:
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
