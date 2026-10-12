#!/usr/bin/env python3
"""Replay the frozen orbit-pair scalar panel and retain every raw arm result."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import subprocess

from make_inputs import read_fields


ARMS = ("tail-double-residue", "tail-pair-fused")
OPERATIONS = ("triples", "adds", "rotations", "prep_seed_ops", "prep_adds",
              "prep_rotations", "prep_layer_inversions", "prep_bytes",
              "point_entries", "point_table_bytes", "static_map_bytes",
              "online_scratch_bytes", "output_inversions")


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
            if sha256(scalar_path) != case["scalar_file_sha256"] or len(raw) % 8:
                raise ValueError(f"prior scalar file mismatch: {scalar_path}")
            excluded.setdefault(case["curve"]["name"], set()).update(
                struct.unpack(f"<{len(raw)//8}Q", raw))
    return excluded


def run_arm(bench, arm, case, scalars):
    command = [str(bench), arm, case["curve"]["name"], str(case["point_index"]),
               str(scalars)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        row = {"arm": arm, "command": command, "returncode": proc.returncode,
               "stdout": proc.stdout, "stderr": proc.stderr, "verified": False}
        if proc.returncode == 0:
            got = read_fields(proc.stdout)
            expected = {"curve": case["curve"]["name"],
                        "point_index": str(case["point_index"]),
                        "count": str(case["scalars"]), "base_x": case["base_x"],
                        "base_y": case["base_y"], "input_digest": case["input_digest"],
                        "output_digest": case["expected_output_digest"],
                        "verified": "1", "prep_repeats": "1",
                        "tail_double_checks": str(case["scalars"] if arm == ARMS[0] else 0),
                        "tail_pair_checks": str(case["scalars"] if arm == ARMS[1] else 0),
                        "tail_pair_preparation_checks": str(121 if arm == ARMS[1] else 0)}
            row["verified"] = all(got.get(key) == value for key, value in expected.items())
            if row["verified"]:
                row["operations"] = {key: int(got[key]) for key in OPERATIONS}
                row["timings_exploratory_ms"] = {
                    key: got[key] for key in ("prep_ms", "online_ms", "verify_ms")}
    except subprocess.TimeoutExpired as exc:
        row = {"arm": arm, "command": command, "returncode": None,
               "timeout": True, "verified": False,
               "stdout": (exc.stdout or b"").decode(errors="replace"),
               "stderr": (exc.stderr or b"").decode(errors="replace")}
    return row


def check(bench, test_curve, root):
    fixture_path = root / "tail-pair-fused-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture.get("schema") != 2 or len(fixture["cases"]) != 8:
        raise ValueError("expected eight frozen orbit-pair cases")
    if fixture["source_sha256"] != sha256(root / "make_tail_pair_fused_inputs.py"):
        raise ValueError("input generator changed after fixture freeze")
    excluded = excluded_values(root, fixture)
    seen = {}
    test = subprocess.run([str(test_curve)], text=True, capture_output=True, timeout=120)
    direct_ok = (test.returncode == 0 and
                 re.search(r"ok: [0-9]+ checks", test.stdout) is not None)
    rows = []
    for case_index, case in enumerate(fixture["cases"]):
        scalars = root / case["scalar_file"]
        raw = scalars.read_bytes()
        if sha256(scalars) != case["scalar_file_sha256"] or len(raw) % 8:
            raise ValueError(f"frozen scalar hash mismatch: {scalars}")
        values = struct.unpack(f"<{len(raw)//8}Q", raw)
        curve_name = case["curve"]["name"]
        accepted = seen.setdefault(curve_name, set())
        if (len(values) != case["scalars"] or len(set(values)) != len(values) or
                set(values) & excluded[curve_name] or set(values) & accepted):
            raise ValueError(f"scalar overlap or count mismatch: {scalars}")
        accepted.update(values)
        order = ARMS[case_index % 2:] + ARMS[:case_index % 2]
        runs = {arm: run_arm(bench, arm, case, scalars) for arm in order}
        passed = all(runs[arm]["verified"] for arm in ARMS)
        scores = None
        if passed:
            old = runs[ARMS[0]]["operations"]
            new = runs[ARMS[1]]["operations"]
            scores = {arm: weighted(runs[arm]["operations"]) for arm in ARMS}
            passed = (old["static_map_bytes"] == 31660 and
                      new["static_map_bytes"] == 33289 and
                      new["point_entries"] == 121 and
                      new["point_table_bytes"] == 3872 and
                      new["prep_layer_inversions"] == 2 and
                      old["output_inversions"] == new["output_inversions"] and
                      scores[ARMS[1]] < scores[ARMS[0]])
        rows.append({"id": case["id"], "verified": passed,
                     "weighted_scores": scores, "runs": runs})
    repo = root.parents[1]
    sources = [repo / "CMakeLists.txt", repo / "src/ec_tau.c",
               repo / "src/ec_tau_internal.h", repo / "src/generated/tau_pair_fused.h",
               repo / "tests/test_curve.c", repo / "scripts/isolated_bench.py",
               root / "README.md", root / "TAIL_PAIR_FUSED.md", root / "bench.c",
               root / "make_isolated_manifest.py", root / "make_tau_pair_fused.py",
               root / "make_tail_pair_fused_inputs.py", root / "screen_tau_pair_fused.py",
               root / "tail-pair-fused-screen.json", Path(__file__), fixture_path,
               bench, test_curve, bench.parent / "CMakeCache.txt"]
    sources.extend(root / entry["name"] for entry in fixture["excluded_prior_manifests"])
    report = {"schema": 1, "status": "orbit_pair_fused_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "input_manifest_sha256": sha256(fixture_path),
              "disjoint_prior_scalars": True,
              "source_sha256": {str(path.relative_to(repo)): sha256(path) for path in sources},
              "direct_test": {"command": [str(test_curve)], "returncode": test.returncode,
                              "stdout": test.stdout, "stderr": test.stderr,
                              "verified": direct_ok},
              "results": rows}
    (root / "tail-pair-fused-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = direct_ok and all(row["verified"] for row in rows)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(rows), "direct_test": direct_ok}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--test-curve", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), args.test_curve.resolve(), Path(__file__).resolve().parent)
