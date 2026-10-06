#!/usr/bin/env python3
"""Retrospective native sparse-vs-full control on the old compact fixture."""

import argparse
import hashlib
import json
from pathlib import Path

from check_tau3_atlas_panel import arm, int_field


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
SCREEN = ROOT / "tau3-sparse-screen.json"
OUTPUT = ROOT / "tau3-sparse-native-design.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    screen = json.loads(SCREEN.read_text())
    design = {record["curve"]: record for record in screen["records"]}
    receipt = {"schema": 1, "status": "retrospective_sparse_native_control",
               "cpu_timing_claim": None,
               "runner_sha256": sha256(Path(__file__)),
               "fixture_sha256": sha256(FIXTURE), "screen_sha256": sha256(SCREEN),
               "bench_sha256": sha256(bench),
               "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
               "header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_sparse.h"),
               "rows": [], "pairs": [], "aggregate": {}}
    for case in fixture["cases"]:
        old = arm(bench, case, "tau3-atlas-pos")
        new = arm(bench, case, "tau3-sparse-pos")
        receipt["rows"].extend((old, new))
        curve = case["curve"]["name"]
        target = design[curve]
        verified = old["verified"] and new["verified"]
        old_adds = int_field(old, "adds")
        new_adds = int_field(new, "adds")
        cold = int_field(new, "sparse_cold_pairs")
        passed = (verified and old_adds is not None and new_adds is not None
                  and cold is not None and new_adds - old_adds == cold
                  and int_field(new, "point_entries") == target["point_entries"]
                  and int_field(new, "point_table_bytes") == target["point_bytes"]
                  and int_field(new, "prep_adds") == target["hot_entries"]
                  and int_field(new, "sparse_preparation_checks") == target["point_entries"]
                  and int_field(new, "sparse_checks") == 4096
                  and int_field(new, "sparse_action_fallbacks") == 0
                  and int_field(new, "fallbacks") == 0
                  and new.get("fields", {}).get("sparse_action_digest") is not None
                  and new.get("fields", {}).get("sparse_action_digest") ==
                  old.get("fields", {}).get("tau3_action_digest"))
        receipt["pairs"].append({"case_id": case["id"], "verified": verified,
                                 "gate_pass": passed, "full_adds": old_adds,
                                 "sparse_adds": new_adds, "cold_pairs": cold})
    for curve, target in design.items():
        pairs = [pair for pair in receipt["pairs"] if pair["case_id"].startswith(curve + "-point")]
        full = sum(pair["full_adds"] for pair in pairs if pair["full_adds"] is not None)
        sparse = sum(pair["sparse_adds"] for pair in pairs if pair["sparse_adds"] is not None)
        receipt["aggregate"][curve] = {"full_adds": full, "sparse_adds": sparse,
                                       "screen_full_adds": target["full_fused_adds"],
                                       "screen_sparse_adds": target["predicted_sparse_adds"],
                                       "matched": full == target["full_fused_adds"] and
                                                  sparse == target["predicted_sparse_adds"]}
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pairs": receipt["pairs"], "aggregate": receipt["aggregate"]}, indent=2))
    if not all(pair["gate_pass"] for pair in receipt["pairs"]) or not all(
            row["matched"] for row in receipt["aggregate"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
