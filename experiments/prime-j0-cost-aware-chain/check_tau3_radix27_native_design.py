#!/usr/bin/env python3
"""Pair native radix-27 and sparse evaluators on old design inputs."""

import argparse
import hashlib
import json
from pathlib import Path

from check_tau3_atlas_panel import arm, int_field


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
SCREEN = ROOT / "tau3-radix27-screen.json"
OUTPUT = ROOT / "tau3-radix27-native-design.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    screen = json.loads(SCREEN.read_text())
    expected = {row["case_id"]: row for row in screen["rows"]}
    receipt = {"schema": 1, "status": "retrospective_radix27_native_control",
               "cpu_timing_claim": None, "isolated_receipt": None,
               "runner_sha256": sha256(Path(__file__)),
               "arm_runner_sha256": sha256(ROOT / "check_tau3_atlas_panel.py"),
               "fixture_sha256": sha256(FIXTURE),
               "screen_sha256": sha256(SCREEN),
               "bench_sha256": sha256(bench),
               "bench_source_sha256": sha256(ROOT / "bench.c"),
               "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
               "map_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_radix27.h"),
               "rows": [], "pairs": []}
    for case in fixture["cases"]:
        baseline = arm(bench, case, "tau3-sparse-pos")
        candidate = arm(bench, case, "tau3-radix27-pos")
        receipt["rows"].extend((baseline, candidate))
        design = expected[case["id"]]
        verified = baseline["verified"] and candidate["verified"]
        sparse_adds = int_field(baseline, "adds")
        optimal_adds = int_field(candidate, "adds")
        entries = 396 if case["curve"]["name"] == "glv-j0-32" else 756
        passed = (verified and sparse_adds == design["native_sparse_additions"]
                  and optimal_adds == design["optimal_additions"]
                  and optimal_adds <= sparse_adds
                  and int_field(candidate, "point_entries") == entries
                  and int_field(candidate, "point_table_bytes") == entries * 32
                  and int_field(candidate, "sparse_preparation_checks") == entries
                  and int_field(candidate, "radix27_checks") == 4096
                  and int_field(candidate, "radix27_action_fallbacks") == 0
                  and int_field(candidate, "fallbacks") == 0
                  and int_field(candidate, "radix27_dp_states") is not None
                  and int_field(candidate, "radix27_dp_states") > 0
                  and int_field(candidate, "radix27_dp_options") is not None
                  and int_field(candidate, "radix27_dp_options") > 0
                  and int_field(candidate, "static_map_bytes") == 55222
                  and int_field(candidate, "online_scratch_bytes") is not None)
        receipt["pairs"].append({"case_id": case["id"], "verified": verified,
                                 "gate_pass": passed, "sparse_adds": sparse_adds,
                                 "optimal_adds": optimal_adds,
                                 "dp_states": int_field(candidate, "radix27_dp_states"),
                                 "dp_options": int_field(candidate, "radix27_dp_options")})
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["pairs"], indent=2))
    if not all(pair["gate_pass"] for pair in receipt["pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
