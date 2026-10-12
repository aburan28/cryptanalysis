#!/usr/bin/env python3
"""Check frozen atlas point outputs and exact operation equality."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


WEIGHTS = {"triples": 10, "adds": 16, "rotations": 1}


def fields(stdout):
    return dict(part.split("=", 1) for part in stdout.strip().split())


def main(bench, root):
    fixture = json.loads((root / "atlas-inputs.json").read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        arms = ("baseline", "atlas") if index % 2 == 0 else ("atlas", "baseline")
        completed = {}
        for arm in arms:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]),
                       str(root / "atlas-inputs" / case["scalar_file"])]
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
                record["weighted_cost"] = sum(
                    WEIGHTS[key] * record["operations"][key] for key in WEIGHTS)
            completed[arm] = record
        baseline, candidate = completed["baseline"], completed["atlas"]
        verified = baseline.get("verified") and candidate.get("verified")
        operation_equal = bool(verified and
                               baseline["operations"] == candidate["operations"])
        results.append({"id": case["id"], "verified": bool(verified),
                        "baseline": baseline, "candidate": candidate,
                        "operation_equal": operation_equal})
    source_paths = [root / "bench.c", root / "make_atlas_inputs.py",
                    root / "make_residue_atlas.py", root / "run.py",
                    Path(__file__),
                    root.parents[1] / "src" / "ec_tau.c",
                    root.parents[1] / "src" / "generated" /
                    "tau4_residue_atlas.h", bench]
    report = {"schema": 1, "status": "operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "weights": WEIGHTS,
              "input_manifest_sha256": hashlib.sha256(
                  (root / "atlas-inputs.json").read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(root.parents[1])):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    output = root / "atlas-panel.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "verified_cases": sum(item["verified"] for item in results),
                      "total_cases": len(results),
                      "operation_equal_cases": sum(item["operation_equal"]
                                                   for item in results)},
                     sort_keys=True))
    if not all(item["verified"] and item["operation_equal"]
               for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    main(args.bench.resolve(), Path(__file__).resolve().parent)
