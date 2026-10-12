#!/usr/bin/env python3
"""Verify a two-digit tau-pair tail against frozen public scalar controls."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import subprocess

from make_inputs import read_fields


ARMS = ("baseline", "tail-oracle-gated", "tail-double")
OPERATIONS = ("triples", "adds", "rotations", "prep_bytes", "static_map_bytes",
              "point_entries", "point_table_bytes", "prep_triples", "prep_adds",
              "prep_rotations", "output_inversions")
SHARED = ("prep_bytes", "point_entries", "point_table_bytes", "prep_triples",
          "prep_adds", "prep_rotations", "output_inversions")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted(ops):
    return 10 * ops["triples"] + 16 * ops["adds"] + ops["rotations"]


def excluded_values(root, fixture):
    excluded = {}
    for entry in fixture["excluded_prior_manifests"]:
        path = root / entry["name"]
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"prior manifest hash mismatch: {path}")
        prior = json.loads(path.read_text())
        for case in prior["cases"]:
            scalar_path = root / case["scalar_file"]
            raw = scalar_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != case["scalar_file_sha256"] or len(raw) % 8:
                raise ValueError(f"prior scalar file mismatch: {scalar_path}")
            excluded.setdefault(case["curve"]["name"], set()).update(
                struct.unpack(f"<{len(raw) // 8}Q", raw))
    return excluded


def check(bench, test_curve, root):
    fixture_path = root / "tail-double-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture.get("schema") != 2 or len(fixture["cases"]) != 8:
        raise ValueError("expected the eight-case disjoint fixture")
    excluded = excluded_values(root, fixture)
    seen = {}
    test = subprocess.run([str(test_curve)], text=True, capture_output=True)
    direct_check = (test.returncode == 0 and
                    re.search(r"ok: [0-9]+ checks", test.stdout) is not None)
    rows = []
    for index, case in enumerate(fixture["cases"]):
        scalars = root / case["scalar_file"]
        raw = scalars.read_bytes()
        if hashlib.sha256(raw).hexdigest() != case["scalar_file_sha256"] or len(raw) % 8:
            raise ValueError(f"frozen scalar hash mismatch: {scalars}")
        values = struct.unpack(f"<{len(raw) // 8}Q", raw)
        curve_name = case["curve"]["name"]
        seen_curve = seen.setdefault(curve_name, set())
        if (len(values) != case["scalars"] or len(set(values)) != len(values) or
                any(value in excluded[curve_name] or value in seen_curve for value in values)):
            raise ValueError(f"scalar overlap or count mismatch: {scalars}")
        seen_curve.update(values)
        runs = {}
        order = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
        for arm in order:
            command = [str(bench), arm, curve_name, str(case["point_index"]), str(scalars)]
            proc = subprocess.run(command, text=True, capture_output=True)
            row = {"arm": arm, "command": command, "returncode": proc.returncode,
                   "stdout": proc.stdout, "stderr": proc.stderr, "verified": False}
            if proc.returncode == 0:
                got = read_fields(proc.stdout)
                expected = {"curve": curve_name, "point_index": str(case["point_index"]),
                            "count": str(case["scalars"]),
                            "base_x": case["base_x"], "base_y": case["base_y"],
                            "input_digest": case["input_digest"],
                            "output_digest": case["expected_output_digest"],
                            "verified": "1", "prep_repeats": "1",
                            "tail_stream_checks": str(case["scalars"] if arm ==
                                                      "tail-oracle-gated" else 0),
                            "tail_double_checks": str(case["scalars"] if arm ==
                                                      "tail-double" else 0)}
                row["verified"] = all(got.get(key) == value for key, value in expected.items())
                if row["verified"]:
                    row["operations"] = {key: int(got[key]) for key in OPERATIONS}
                    row["tail_stream_checks"] = int(got["tail_stream_checks"])
                    row["tail_double_checks"] = int(got["tail_double_checks"])
                    row["timings_exploratory_ms"] = {
                        key: got[key] for key in ("prep_ms", "online_ms", "verify_ms")}
            runs[arm] = row
        passed = all(runs[arm]["verified"] for arm in ARMS)
        costs = None
        if passed:
            base = runs["baseline"]["operations"]
            gated = runs["tail-oracle-gated"]["operations"]
            double = runs["tail-double"]["operations"]
            costs = {arm: weighted(runs[arm]["operations"]) for arm in ARMS}
            passed = (all(base[key] == gated[key] == double[key] for key in SHARED) and
                      base["static_map_bytes"] == 0 and
                      gated["static_map_bytes"] == 3 * 129 * 129 + (3 * 129 * 129 + 7) // 8 and
                      double["static_map_bytes"] == 2 * 3 * 129 * 129 +
                      (3 * 129 * 129 + 7) // 8 and
                      costs["tail-double"] < costs["tail-oracle-gated"] < costs["baseline"])
        rows.append({"id": case["id"], "verified": passed, "runs": runs,
                     "weighted_costs": costs})
    repo = root.parents[1]
    sources = [repo / "CMakeLists.txt", repo / "src/ec_tau.c",
               repo / "src/ec_tau_internal.h", repo / "src/generated/tau_tail_oracle.h",
               repo / "src/generated/tau_tail_gate.h",
               repo / "src/generated/tau_tail_double.h", repo / "tests/test_curve.c",
               repo / "scripts/isolated_bench.py", root / "README.md", root / "TAIL_GATE.md",
               root / "TAIL_DOUBLE_PAIR.md", root / "bench.c", root / "make_isolated_manifest.py",
               root / "make_tau_tail_oracle.py", root / "make_tau_tail_gate.py",
               root / "make_tau_tail_double.py", root / "make_tail_double_inputs.py",
               root / "screen_tau_tail_double.py", root / "tail-double-screen.json",
               Path(__file__), fixture_path, bench, test_curve, bench.parent / "CMakeCache.txt"]
    sources.extend(root / entry["name"] for entry in fixture["excluded_prior_manifests"])
    report = {"schema": 1, "status": "tail_double_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "input_manifest_sha256": sha256(fixture_path),
              "disjoint_prior_scalars": True,
              "source_sha256": {str(path.relative_to(repo)): sha256(path) for path in sources},
              "direct_test": {"command": [str(test_curve)], "returncode": test.returncode,
                              "stdout": test.stdout, "stderr": test.stderr,
                              "verified": direct_check},
              "results": rows}
    (root / "tail-double-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = direct_check and all(row["verified"] for row in rows)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(rows), "direct_test": direct_check}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--test-curve", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), args.test_curve.resolve(), Path(__file__).resolve().parent)
