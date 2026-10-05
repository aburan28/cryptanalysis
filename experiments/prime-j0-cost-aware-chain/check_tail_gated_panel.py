#!/usr/bin/env python3
"""Verify pre-gated and original tail digit streams on fresh public inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
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


def prior_values(root, fixture):
    excluded = {}
    for entry in fixture["excluded_prior_manifests"]:
        path = root / entry["name"]
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"prior manifest hash mismatch: {path}")
        prior = json.loads(path.read_text())
        for case in prior["cases"]:
            scalar_path = root / case["scalar_file"]
            raw = scalar_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != case["scalar_file_sha256"]:
                raise ValueError(f"prior scalar file hash mismatch: {scalar_path}")
            excluded.setdefault(case["curve"]["name"], set()).update(
                struct.unpack(f"<{len(raw) // 8}Q", raw))
    return excluded


def check(bench, test_curve, root, fixture_name, report_name):
    fixture_path = root / fixture_name
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8:
        raise ValueError("expected eight frozen cases")
    disjoint_fixture = fixture.get("schema") == 2
    excluded = prior_values(root, fixture) if disjoint_fixture else {}
    seen = {}
    test = subprocess.run([str(test_curve)], text=True, capture_output=True)
    recode_check = (test.returncode == 0 and
                    re.search(r"ok: [0-9]+ checks", test.stdout) is not None)
    rows = []
    for index, case in enumerate(fixture["cases"]):
        scalars = root / case["scalar_file"]
        if sha256(scalars) != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalars}")
        if disjoint_fixture:
            raw = scalars.read_bytes()
            values = struct.unpack(f"<{len(raw) // 8}Q", raw)
            curve_name = case["curve"]["name"]
            if len(values) != case["scalars"] or len(set(values)) != len(values) or any(
                    value in excluded[curve_name] or value in seen.setdefault(curve_name, set())
                    for value in values):
                raise ValueError(f"v2 scalar overlap or count mismatch: {scalars}")
            seen[curve_name].update(values)
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
    if disjoint_fixture:
        sources.append(root / "make_tail_gated_v2_inputs.py")
        sources.extend(root / entry["name"] for entry in fixture["excluded_prior_manifests"])
    report = {"schema": 1, "status": "tail_gate_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "input_manifest_sha256": sha256(fixture_path),
              "disjoint_prior_scalars": disjoint_fixture,
              "source_sha256": {str(path.relative_to(repo)): sha256(path) for path in sources},
              "recode_test": {"command": [str(test_curve)], "returncode": test.returncode,
                              "stdout": test.stdout, "stderr": test.stderr,
                              "verified": recode_check},
              "results": rows}
    (root / report_name).write_text(
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
    parser.add_argument("--fixture", default="tail-gated-inputs.json")
    parser.add_argument("--output", default="tail-gated-panel.json")
    args = parser.parse_args()
    check(args.bench.resolve(), args.test_curve.resolve(), Path(__file__).resolve().parent,
          args.fixture, args.output)
