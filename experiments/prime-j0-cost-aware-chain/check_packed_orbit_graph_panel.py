#!/usr/bin/env python3
"""Replay frozen packed graph recipes against stored-structure graph recipes."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields
from make_tau_wide_orbits import build
from screen_tapered_residue import SCHEDULE_32, SCHEDULE_56


REFERENCE = "tapered-residue-graph-batch128"
CANDIDATE = "tapered-residue-packed-batch128"
ARMS = (REFERENCE, CANDIDATE)
COUNTERS = ("triples", "adds", "rotations", "output_inversions", "fallbacks",
            "second_recodes", "steered_blocks", "static_map_bytes", "recipe_bytes",
            "prep_slot_lookups", "prep_triples", "prep_adds", "prep_rotations",
            "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
            "online_scratch_bytes", "point_entries", "point_table_bytes")
SHARED = ("triples", "adds", "rotations", "output_inversions", "fallbacks",
          "second_recodes", "steered_blocks", "static_map_bytes", "prep_triples",
          "prep_adds", "prep_rotations", "prep_layer_inversions", "prep_bytes",
          "prep_temp_heap_bytes", "online_scratch_bytes", "point_entries",
          "point_table_bytes")


def check(bench, root):
    fixture_path = root / "orbit-graph-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8:
        raise ValueError("unexpected eight-point fixture")
    screen = json.loads((root / "packed-orbit-graph-screen.json").read_text())
    atlases = {width: build(width) for width in (8, 10, 12)}
    models = {}
    for name, schedule in (("glv-j0-32", SCHEDULE_32), ("j0-56", SCHEDULE_56)):
        models[name] = {"reference_recipe_bytes": sum(8 * len(atlases[width]["reps"])
                                                      for width in set(schedule)),
                        "candidate_recipe_bytes": screen["schedule_recipe_bytes"][name],
                        "candidate_slot_lookups": sum(len(atlases[width]["reps"]) - 1
                                                      for width in schedule)}
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / case["scalar_file"]
        if hashlib.sha256(scalar_path.read_bytes()).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        runs = {}
        for arm in ARMS[index % 2:] + ARMS[:index % 2]:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
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
                    row["operations"] = {key: int(got[key]) for key in COUNTERS}
                    row["timings_exploratory_ms"] = {
                        key: got[key] for key in ("prep_ms", "online_ms", "verify_ms")}
            runs[arm] = row
        passed = False
        if all(runs[arm]["verified"] for arm in ARMS):
            reference = runs[REFERENCE]["operations"]
            candidate = runs[CANDIDATE]["operations"]
            model = models[case["curve"]["name"]]
            passed = (all(reference[key] == candidate[key] for key in SHARED) and
                      reference["recipe_bytes"] == model["reference_recipe_bytes"] and
                      candidate["recipe_bytes"] == model["candidate_recipe_bytes"] and
                      candidate["prep_slot_lookups"] == model["candidate_slot_lookups"] and
                      reference["prep_slot_lookups"] == 0 and
                      candidate["recipe_bytes"] < reference["recipe_bytes"] and
                      candidate["fallbacks"] == 0 and
                      candidate["output_inversions"] == 32)
        results.append({"id": case["id"], "verified": passed,
                        "predicted": models[case["curve"]["name"]], "runs": runs})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
                    repo / "tests" / "test_curve.c", repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau_wide_orbits.h",
                    repo / "src" / "generated" / "tau_wide_graph.h",
                    repo / "src" / "generated" / "tau_wide_packed_graph.h",
                    root / "README.md", root / "INTEGRATION.md",
                    root / "ORBIT_GRAPH_PRECOMPUTE.md", root / "PACKED_ORBIT_GRAPH.md",
                    root / "bench.c", root / "make_isolated_manifest.py",
                    root / "make_graph_inputs.py", Path(__file__),
                    root / "make_tau_wide_packed_graph.py",
                    root / "packed-orbit-graph-screen.json",
                    root / "make_tau_wide_graph.py", root / "make_tau_wide_orbits.py",
                    root / "run.py", bench, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "packed_orbit_graph_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths},
              "results": results}
    (root / "packed-orbit-graph-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(results), "models": models}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
