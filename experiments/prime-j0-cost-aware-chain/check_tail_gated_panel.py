#!/usr/bin/env python3
"""Verify pre-gated and original tail digit streams on fresh public inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

from make_inputs import read_fields


ARMS = ("baseline", "tail-oracle", "tail-oracle-gated")
OPERATIONS = ("triples", "adds", "rotations", "prep_bytes", "static_map_bytes",
              "point_entries", "point_table_bytes", "prep_triples", "prep_adds",
              "prep_rotations", "output_inversions")
EVALUATION = ("triples", "adds", "rotations")
SHARED = ("prep_bytes", "point_entries", "point_table_bytes", "prep_triples",
          "prep_adds", "prep_rotations", "output_inversions")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted(ops):
    return 10 * ops["triples"] + 16 * ops["adds"] + ops["rotations"]


def check(bench, test_curve, root):
    fixture_path = root / "tail-gated-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8:
        raise ValueError("expected eight frozen cases")
    test = subprocess.run([str(test_curve)], text=True, capture_output=True)
    recode_check = (test.returncode == 0 and
                    re.search(r"ok: [0-9]+ checks", test.stdout) is not None)
    rows = []
    for index, case in enumerate(fixture["cases"]):
        scalars = root / case["scalar_file"]
        if sha256(scalars) != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalars}")
        runs = {}
        order = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
        for arm in order:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalars)]
            proc = subprocess.run(command, text=True, capture_output=True)
            row = {"arm": arm, "command": command, "returncode": proc.returncode,
                   "stdout": proc.stdout, "stderr": proc.stderr, "verified": False}
            if proc.returncode == 0:
                got = read_fields(proc.stdout)
                expected = {"curve": case["curve"]["name"],
                            "point_index": str(case["point_index"]),
                            "count": str(case["scalars"]),
                            "base_x": case["base_x"], "base_y": case["base_y"],
                            "input_digest": case["input_digest"],
                            "output_digest": case["expected_output_digest"],
                            "verified": "1", "prep_repeats": "1"}
                row["verified"] = all(got.get(key) == value for key, value in expected.items())
                if row["verified"]:
                    row["operations"] = {key: int(got[key]) for key in OPERATIONS}
                    row["timings_exploratory_ms"] = {
                        key: got[key] for key in ("prep_ms", "online_ms", "verify_ms")}
            runs[arm] = row
        passed = all(runs[arm]["verified"] for arm in ARMS)
        costs = None
        if passed:
            base = runs["baseline"]["operations"]
            old = runs["tail-oracle"]["operations"]
            gated = runs["tail-oracle-gated"]["operations"]
            costs = {arm: weighted(runs[arm]["operations"]) for arm in ARMS}
            passed = (all(old[key] == gated[key] for key in EVALUATION + SHARED) and
                      all(base[key] == gated[key] for key in SHARED) and
                      old["static_map_bytes"] == 3 * 129 * 129 and
                      gated["static_map_bytes"] == 3 * 129 * 129 + (3 * 129 * 129 + 7) // 8 and
                      base["static_map_bytes"] == 0 and
                      costs["tail-oracle-gated"] < costs["baseline"])
        rows.append({"id": case["id"], "verified": passed, "runs": runs,
                     "weighted_costs": costs})
    repo = root.parents[1]
    sources = [repo / "CMakeLists.txt", repo / "src/ec_tau.c",
               repo / "src/ec_tau_internal.h", repo / "src/generated/tau_tail_oracle.h",
               repo / "src/generated/tau_tail_gate.h", repo / "tests/test_curve.c",
               repo / "scripts/isolated_bench.py", root / "README.md",
               root / "TAIL_ORACLE.md", root / "TAIL_GATE.md", root / "bench.c",
               root / "make_isolated_manifest.py", root / "make_tau_tail_oracle.py",
               root / "make_tau_tail_gate.py", root / "make_tail_gated_inputs.py",
               Path(__file__), fixture_path, bench, test_curve,
               bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "tail_gate_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "input_manifest_sha256": sha256(fixture_path),
              "source_sha256": {str(path.relative_to(repo)): sha256(path) for path in sources},
              "recode_test": {"command": [str(test_curve)], "returncode": test.returncode,
                              "stdout": test.stdout, "stderr": test.stderr,
                              "verified": recode_check},
              "results": rows}
    (root / "tail-gated-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = recode_check and all(row["verified"] for row in rows)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(rows), "recode_test": recode_check}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--test-curve", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), args.test_curve.resolve(), Path(__file__).resolve().parent)
