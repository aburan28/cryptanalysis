#!/usr/bin/env python3
"""Retrospective native differential on the old compact positional fixture."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from check_tau3_fused_panel import fields


ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "compact-pos-inputs.json"
OUTPUT = ROOT / "tau3-atlas-native-design.json"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench):
    fixture = json.loads(FIXTURE.read_text())
    receipt = {"schema": 1, "status": "retrospective_native_design_control",
               "fixture_sha256": sha256(FIXTURE),
               "runner_sha256": sha256(Path(__file__)),
               "bench_sha256": sha256(bench),
               "ec_tau_source_sha256": sha256(ROOT.parents[1] / "src/ec_tau.c"),
               "atlas_header_sha256": sha256(ROOT.parents[1] / "src/generated/tau3_atlas.h"),
               "cpu_timing_claim": None, "rows": [], "pairs": []}
    for case in fixture["cases"]:
        arms = {}
        for mode in ("tau3-fused-pos", "tau3-atlas-pos"):
            cmd = [str(bench), mode, case["curve"]["name"], str(case["point_index"]),
                   str(ROOT / case["scalar_file"])]
            try:
                process = subprocess.run(cmd, text=True, capture_output=True, timeout=120,
                                         check=False)
                row = {"case_id": case["id"], "mode": mode, "exit_code": process.returncode,
                       "stdout": process.stdout, "stderr": process.stderr, "timed_out": False}
            except subprocess.TimeoutExpired as error:
                row = {"case_id": case["id"], "mode": mode, "exit_code": None,
                       "stdout": str(error.stdout or ""), "stderr": str(error.stderr or ""),
                       "timed_out": True}
            if row["exit_code"] == 0:
                try:
                    row["fields"] = fields(row["stdout"])
                except ValueError as error:
                    row["parse_error"] = str(error)
            row["verified"] = (
                "fields" in row and row["fields"].get("verified") == "1"
                and row["fields"].get("input_digest") == case["input_digest"]
                and row["fields"].get("output_digest") == case["expected_output_digest"]
                and row["fields"].get("base_x") == case["base_x"]
                and row["fields"].get("base_y") == case["base_y"]
                and row["fields"].get("count") == "4096"
            )
            receipt["rows"].append(row)
            arms[mode] = row
        old = arms["tau3-fused-pos"]
        new = arms["tau3-atlas-pos"]
        paired = old["verified"] and new["verified"]
        if paired:
            a, b = old["fields"], new["fields"]
            paired = (all(a.get(key) == b.get(key) for key in
                          ("adds", "rotations", "output_inversions", "point_entries",
                           "point_table_bytes", "tau3_action_digest"))
                      and b.get("tau3_atlas_checks") == "4096"
                      and b.get("tau3_action_fallbacks") == "0"
                      and b.get("fallbacks") == "0"
                      and int(b.get("static_map_bytes", -1)) -
                      int(a.get("static_map_bytes", -1)) == 26244)
        receipt["pairs"].append({"case_id": case["id"], "matched": paired})
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["pairs"], indent=2))
    if not all(pair["matched"] for pair in receipt["pairs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    run(args.bench.resolve())
