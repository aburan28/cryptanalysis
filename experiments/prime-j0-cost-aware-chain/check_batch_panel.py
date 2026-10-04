#!/usr/bin/env python3
"""Verify frozen block-normalized tau outputs and retain raw diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields


BLOCKS = (32, 128, 512, 4096)
OPERATIONS = ("triples", "adds", "rotations")


def scalars_from(path):
    raw = path.read_bytes()
    if len(raw) != 4096 * 8:
        raise ValueError(f"wrong frozen scalar byte count: {path}")
    return [int.from_bytes(raw[i:i + 8], "little")
            for i in range(0, len(raw), 8)]


def check(bench, root):
    fixture_path = root / "batch-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "batch-inputs" / case["scalar_file"]
        if hashlib.sha256(scalar_path.read_bytes()).hexdigest() != case[
                "scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        values = scalars_from(scalar_path)
        arms = ["pos-global"] + [f"pos-batch{b}" for b in BLOCKS]
        if index % 2:
            arms.reverse()
        completed = {}
        for arm in arms:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            run = subprocess.run(command, text=True, capture_output=True)
            record = {"arm": arm, "command": command,
                      "returncode": run.returncode, "stdout": run.stdout,
                      "stderr": run.stderr}
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
                        "prep_repeats": "1", "verified": "1"}
            record["verified"] = all(got.get(key) == value
                                     for key, value in expected.items())
            if record["verified"]:
                record["operations"] = {key: int(got[key])
                                        for key in OPERATIONS}
                record["output_inversions"] = int(got["output_inversions"])
                record["online_scratch_bytes"] = int(got[
                    "online_scratch_bytes"])
                record["prep_bytes"] = int(got["prep_bytes"])
                record["prep_triples"] = int(got["prep_triples"])
                record["prep_layer_inversions"] = int(got[
                    "prep_layer_inversions"])
            completed[arm] = record
        reference = completed["pos-global"]
        checked = {}
        for block in BLOCKS:
            arm = f"pos-batch{block}"
            candidate = completed[arm]
            expected_inversions = sum(
                any(values[i:i + block])
                for i in range(0, len(values), block))
            verified = (reference.get("verified") and candidate.get("verified")
                        and candidate["operations"] == reference["operations"]
                        and candidate["output_inversions"] == expected_inversions
                        and candidate["online_scratch_bytes"] == block * 32
                        and candidate["prep_bytes"] == reference["prep_bytes"]
                        and candidate["prep_triples"] == reference[
                            "prep_triples"]
                        and candidate["prep_layer_inversions"] == 1)
            checked[arm] = {"verified": bool(verified),
                            "expected_output_inversions": expected_inversions,
                            "saved_output_inversions": (
                                reference["output_inversions"] -
                                candidate["output_inversions"])
                            if verified else None}
        reference_inversions = sum(value != 0 for value in values)
        reference_verified = (reference.get("verified") and
                              reference["output_inversions"] ==
                              reference_inversions and
                              reference["online_scratch_bytes"] == 0)
        results.append({"id": case["id"],
                        "reference_verified": bool(reference_verified),
                        "reference_expected_inversions": reference_inversions,
                        "checks": checked, "runs": completed})
    repo = root.parents[1]
    source_paths = [root / "bench.c", root / "make_batch_inputs.py",
                    Path(__file__), repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h", bench]
    report = {"schema": 1, "status": "batch_output_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(
                  fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(repo)):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    (root / "batch-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(item["reference_verified"] and all(
        result["verified"] for result in item["checks"].values())
        for item in results)
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "arms_per_case": 5, "verified": passed,
                      "inversions": {
                          arm: [item["runs"][arm].get("output_inversions")
                                for item in results]
                          for arm in ["pos-global"] + [
                              f"pos-batch{block}" for block in BLOCKS]}},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
