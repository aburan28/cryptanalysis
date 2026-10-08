#!/usr/bin/env python3
"""Replay packed graph and affine-wavefront preparation on frozen public inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

from check_panel import fields


REFERENCE = "tapered-residue-packed-batch128"
CANDIDATE = "tapered-residue-wavefront-batch128"
ARMS = (REFERENCE, CANDIDATE)
SHARED = ("prep_triples", "prep_adds", "prep_rotations", "prep_bytes",
          "point_entries", "point_table_bytes", "static_map_bytes", "recipe_bytes",
          "prep_slot_lookups", "triples", "adds", "rotations", "output_inversions",
          "fallbacks", "second_recodes", "steered_blocks", "online_scratch_bytes")
EXTRA = ("prep_layer_inversions", "prep_temp_heap_bytes",
         "prep_batch_denominators", "prep_affine_exceptions",
         "prep_affine_doublings", "prep_affine_edge_mults_model",
         "prep_affine_edge_squarings_model")
MODELS = {"glv-j0-32": {"reference_inversions": 5, "candidate_inversions": 9,
                         "prep_adds": 39096, "slot_lookups": 39368,
                         "extra_scratch_bytes": 9843 * 16},
          "j0-56": {"reference_inversions": 6, "candidate_inversions": 9,
                    "prep_adds": 267552, "slot_lookups": 267910,
                    "extra_scratch_bytes": 88575 * 16}}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bench, test_curve, root):
    fixture_path = root / "orbit-graph-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8:
        raise ValueError("unexpected eight-point fixture")
    test = subprocess.run([str(test_curve)], text=True, capture_output=True)
    table_check = (test.returncode == 0 and
                   re.search(r"ok: [0-9]+ checks", test.stdout) is not None)
    rows = []
    for index, case in enumerate(fixture["cases"]):
        scalars = root / case["scalar_file"]
        if sha256(scalars) != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalars}")
        runs = {}
        for arm in ARMS[index % 2:] + ARMS[:index % 2]:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalars)]
            proc = subprocess.run(command, text=True, capture_output=True)
            row = {"arm": arm, "command": command, "returncode": proc.returncode,
                   "stdout": proc.stdout, "stderr": proc.stderr, "verified": False}
            if proc.returncode == 0:
                got = fields(proc.stdout)
                expected = {"curve": case["curve"]["name"],
                            "point_index": str(case["point_index"]),
                            "count": str(case["scalars"]),
                            "base_x": case["base_x"], "base_y": case["base_y"],
                            "input_digest": case["input_digest"],
                            "output_digest": case["expected_output_digest"],
                            "verified": "1", "prep_repeats": "1"}
                row["verified"] = all(got.get(key) == value for key, value in expected.items())
                if row["verified"]:
                    row["operations"] = {key: int(got[key]) for key in SHARED + EXTRA}
                    row["timings_exploratory_ms"] = {
                        key: got[key] for key in ("prep_ms", "online_ms", "verify_ms")}
            runs[arm] = row
        model = MODELS[case["curve"]["name"]]
        passed = False
        if all(runs[arm]["verified"] for arm in ARMS):
            ref = runs[REFERENCE]["operations"]
            candidate = runs[CANDIDATE]["operations"]
            passed = (all(ref[key] == candidate[key] for key in SHARED) and
                      ref["prep_layer_inversions"] == model["reference_inversions"] and
                      candidate["prep_layer_inversions"] == model["candidate_inversions"] and
                      candidate["prep_adds"] == model["prep_adds"] and
                      candidate["prep_slot_lookups"] == model["slot_lookups"] and
                      candidate["prep_temp_heap_bytes"] - ref["prep_temp_heap_bytes"] ==
                      model["extra_scratch_bytes"] and
                      candidate["prep_batch_denominators"] == candidate["prep_adds"] and
                      candidate["prep_affine_exceptions"] == 0 and
                      candidate["prep_affine_doublings"] == 0 and
                      candidate["prep_affine_edge_mults_model"] ==
                      5 * candidate["prep_batch_denominators"] and
                      candidate["prep_affine_edge_squarings_model"] ==
                      candidate["prep_batch_denominators"] and
                      candidate["fallbacks"] == 0)
        rows.append({"id": case["id"], "verified": passed, "model": model, "runs": runs})
    repo = root.parents[1]
    sources = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
               repo / "tests" / "test_curve.c",
               repo / "src" / "ec_tau.c", repo / "src" / "ec_tau_internal.h",
               repo / "src" / "generated" / "tau_wide_orbits.h",
               repo / "src" / "generated" / "tau_wide_graph.h",
               repo / "src" / "generated" / "tau_wide_packed_graph.h",
               root / "README.md", root / "INTEGRATION.md",
               root / "AFFINE_WAVEFRONT.md", root / "bench.c", Path(__file__),
               root / "make_isolated_manifest.py", root / "orbit-graph-inputs.json",
               root / "make_tau_wide_packed_graph.py",
               root / "packed-orbit-graph-screen.json",
               bench, test_curve, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "affine_wavefront_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(), "input_manifest_sha256": sha256(fixture_path),
              "source_sha256": {str(path.relative_to(repo)): sha256(path) for path in sources},
              "table_equality_test": {"command": [str(test_curve)], "returncode": test.returncode,
                                      "stdout": test.stdout, "stderr": test.stderr,
                                      "verified": table_check},
              "results": rows}
    (root / "affine-wavefront-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = table_check and all(row["verified"] for row in rows)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(rows), "table_equality_test": table_check}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--test-curve", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), args.test_curve.resolve(), Path(__file__).resolve().parent)
