#!/usr/bin/env python3
"""Retain exact positional-tau correctness and operation counts."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import WEIGHTS, fields


def check(bench, root):
    fixture = json.loads((root / "pos-inputs.json").read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        order = ("baseline", "pos") if index % 2 == 0 else ("pos", "baseline")
        completed = {}
        for arm in order:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]),
                       str(root / "pos-inputs" / case["scalar_file"])]
            run = subprocess.run(command, text=True, capture_output=True)
            record = {"arm": arm, "returncode": run.returncode,
                      "stdout": run.stdout, "stderr": run.stderr}
            if run.returncode:
                completed[arm] = record
                continue
            got = fields(run.stdout)
            expected = {"curve": case["curve"]["name"],
                        "point_index": str(case["point_index"]),
                        "count": str(case["scalars"]),
                        "base_x": case["base_x"], "base_y": case["base_y"],
                        "input_digest": case["input_digest"],
                        "output_digest": case["expected_output_digest"],
                        "verified": "1"}
            record["verified"] = all(got.get(key) == value
                                     for key, value in expected.items())
            if record["verified"]:
                record["operations"] = {key: int(got[key]) for key in WEIGHTS}
                record["weighted_online_cost"] = sum(
                    WEIGHTS[key] * record["operations"][key] for key in WEIGHTS)
                record["prep_triples"] = int(got["prep_triples"])
                record["prep_layer_inversions"] = int(got["prep_layer_inversions"])
                record["prep_bytes"] = int(got["prep_bytes"])
            completed[arm] = record
        baseline, candidate = completed["baseline"], completed["pos"]
        verified = baseline.get("verified") and candidate.get("verified")
        results.append({"id": case["id"], "verified": bool(verified),
                        "baseline": baseline, "positional": candidate,
                        "saved_online_weight": (
                            baseline["weighted_online_cost"] -
                            candidate["weighted_online_cost"])
                        if verified else None})
    source_paths = [root / "bench.c", root / "make_pos_inputs.py",
                    Path(__file__), root.parents[1] / "src" / "ec_tau.c", bench]
    report = {"schema": 1, "status": "positional_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "weights": WEIGHTS,
              "input_manifest_sha256": hashlib.sha256(
                  (root / "pos-inputs.json").read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(root.parents[1])):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    (root / "pos-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "verified_cases": sum(item["verified"] for item in results),
                      "total_cases": len(results),
                      "saved_online_weight": [item["saved_online_weight"]
                                              for item in results]}, sort_keys=True))
    if not all(item["verified"] for item in results):
        raise SystemExit(1)
    if any(item["positional"]["operations"]["triples"] != 0
           for item in results):
        raise SystemExit("online positional triple count is nonzero")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
