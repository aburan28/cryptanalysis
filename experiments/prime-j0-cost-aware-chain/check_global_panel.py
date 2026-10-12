#!/usr/bin/env python3
"""Retain global-batch table and exact-output diagnostics without a speed claim."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import WEIGHTS, fields


def check(bench, root):
    fixture = json.loads((root / "global-inputs.json").read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        order = ("pos", "pos-global") if index % 2 == 0 else (
            "pos-global", "pos")
        completed = {}
        for arm in order:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]),
                       str(root / "global-inputs" / case["scalar_file"])]
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
                record["prep_triples"] = int(got["prep_triples"])
                record["prep_layer_inversions"] = int(got[
                    "prep_layer_inversions"])
                record["prep_bytes"] = int(got["prep_bytes"])
                record["prep_temp_heap_bytes"] = int(got[
                    "prep_temp_heap_bytes"])
            completed[arm] = record
        baseline, candidate = completed["pos"], completed["pos-global"]
        prep_completed = {}
        prep_order = ("pos-prep", "pos-global-prep") if index % 2 == 0 else (
            "pos-global-prep", "pos-prep")
        for arm in prep_order:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]),
                       str(root / "global-inputs" / case["scalar_file"])]
            run = subprocess.run(command, text=True, capture_output=True)
            record = {"arm": arm, "returncode": run.returncode,
                      "stdout": run.stdout, "stderr": run.stderr}
            if run.returncode:
                prep_completed[arm] = record
                continue
            got = fields(run.stdout)
            expected = {"curve": case["curve"]["name"],
                        "point_index": str(case["point_index"]),
                        "count": str(case["scalars"]),
                        "base_x": case["base_x"], "base_y": case["base_y"],
                        "input_digest": case["input_digest"],
                        "output_digest": case["expected_output_digest"],
                        "prep_repeats": "256", "verified": "1"}
            record["verified"] = all(got.get(key) == value
                                     for key, value in expected.items())
            if record["verified"]:
                record["prep_triples"] = int(got["prep_triples"])
                record["prep_layer_inversions"] = int(got[
                    "prep_layer_inversions"])
            prep_completed[arm] = record
        old_prep = prep_completed["pos-prep"]
        global_prep = prep_completed["pos-global-prep"]
        verified = baseline.get("verified") and candidate.get("verified")
        same_online = verified and baseline["operations"] == candidate[
            "operations"]
        same_triples = verified and baseline["prep_triples"] == candidate[
            "prep_triples"]
        inversion_gate = verified and (
            baseline["prep_layer_inversions"] == 63 and
            candidate["prep_layer_inversions"] == 1)
        prep_gate = (old_prep.get("verified") and global_prep.get("verified")
                     and old_prep["prep_triples"] ==
                         global_prep["prep_triples"] == 256 * 1134
                     and old_prep["prep_layer_inversions"] == 256 * 63
                     and global_prep["prep_layer_inversions"] == 256)
        results.append({"id": case["id"], "verified": bool(verified),
                        "same_online_operations": bool(same_online),
                        "same_precompute_triples": bool(same_triples),
                        "inversion_gate": bool(inversion_gate),
                        "prep_gate": bool(prep_gate),
                        "old_builder": baseline, "global_builder": candidate,
                        "old_prep_benchmark": old_prep,
                        "global_prep_benchmark": global_prep})
    source_paths = [root / "bench.c", root / "make_global_inputs.py",
                    Path(__file__), root.parents[1] / "src" / "ec_tau.c", bench]
    report = {"schema": 1, "status": "global_batch_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "weights": WEIGHTS,
              "input_manifest_sha256": hashlib.sha256(
                  (root / "global-inputs.json").read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(root.parents[1])):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    (root / "global-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "verified_cases": sum(item["verified"] for item in results),
                      "same_online_operations": all(item[
                          "same_online_operations"] for item in results),
                      "same_precompute_triples": all(item[
                          "same_precompute_triples"] for item in results),
                      "inversion_gate": all(item["inversion_gate"]
                                            for item in results),
                      "prep_gate": all(item["prep_gate"]
                                       for item in results)}, sort_keys=True))
    if not all(item["verified"] and item["same_online_operations"] and
               item["same_precompute_triples"] and item["inversion_gate"]
               and item["prep_gate"]
               for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
