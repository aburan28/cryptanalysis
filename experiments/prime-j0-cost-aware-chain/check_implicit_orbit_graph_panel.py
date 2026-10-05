#!/usr/bin/env python3
"""Replay the frozen implicit graph builder against stored graph recipes."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields
from check_orbit_graph_panel import graph_model
from make_tau_wide_graph import recipes
from make_tau_wide_orbits import build
from screen_tapered_residue import SCHEDULE_32, SCHEDULE_56


REFERENCE = "tapered-residue-graph-batch128"
CANDIDATE = "tapered-residue-implicit-batch128"
ARMS = (REFERENCE, CANDIDATE)
COUNTERS = ("triples", "adds", "rotations", "output_inversions", "fallbacks",
            "second_recodes", "steered_blocks", "static_map_bytes", "recipe_bytes",
            "descriptor_bytes", "prep_recode_calls", "prep_digit_slots_scanned",
            "prep_integer_tau_steps", "prep_parent_index_lookups",
            "prep_exact_parent_checks", "prep_triples", "prep_adds", "prep_rotations",
            "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
            "online_scratch_bytes", "point_entries", "point_table_bytes")
ONLINE = ("triples", "adds", "rotations", "output_inversions", "fallbacks",
          "second_recodes", "steered_blocks", "online_scratch_bytes")
SHARED_PREP = ("prep_triples", "prep_adds", "prep_rotations",
               "prep_layer_inversions", "prep_bytes", "point_entries",
               "point_table_bytes", "static_map_bytes")


def implicit_model(schedule, width_rows, graph):
    prediction = {"prep_adds": graph["prep_adds"],
                  "prep_rotations": graph["prep_rotations"],
                  "recipe_bytes": 0,
                  "descriptor_bytes": max(width_rows[str(width)]["descriptor_temp_bytes"]
                                          for width in schedule)}
    mapping = {"prep_recode_calls": "recode_calls",
               "prep_digit_slots_scanned": "digit_slots_scanned",
               "prep_integer_tau_steps": "integer_tau_steps",
               "prep_parent_index_lookups": "parent_index_lookups",
               "prep_exact_parent_checks": "exact_parent_checks"}
    for output_key, width_key in mapping.items():
        prediction[output_key] = sum(width_rows[str(width)][width_key]
                                     for width in schedule)
    prediction["prep_temp_heap_bytes"] = (max(width_rows[str(width)]["orbits"]
                                               for width in schedule) * 32 +
                                          prediction["descriptor_bytes"])
    return prediction


def check(bench, root):
    fixture_path = root / "orbit-graph-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8:
        raise ValueError("unexpected eight-point graph fixture")
    screen = json.loads((root / "implicit-orbit-graph-screen.json").read_text())
    atlases = {width: build(width) for width in (8, 10, 12)}
    graphs = {width: recipes(atlas) for width, atlas in atlases.items()}
    models = {}
    for name, schedule in (("glv-j0-32", SCHEDULE_32), ("j0-56", SCHEDULE_56)):
        baseline = graph_model(schedule, graphs)
        models[name] = implicit_model(schedule, screen["widths"], baseline)
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / case["scalar_file"]
        if hashlib.sha256(scalar_path.read_bytes()).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        runs = {}
        for arm in ARMS[index % 2:] + ARMS[:index % 2]:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            proc = subprocess.run(command, capture_output=True, text=True)
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
            baseline = runs[REFERENCE]["operations"]
            candidate = runs[CANDIDATE]["operations"]
            model = models[case["curve"]["name"]]
            passed = (all(baseline[key] == candidate[key]
                          for key in ONLINE + SHARED_PREP) and
                      all(candidate[key] == value for key, value in model.items()) and
                      all(baseline[key] == 0 for key in
                          ("descriptor_bytes", "prep_recode_calls",
                           "prep_digit_slots_scanned", "prep_integer_tau_steps",
                           "prep_parent_index_lookups", "prep_exact_parent_checks")) and
                      baseline["recipe_bytes"] > 0 and
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
                    root / "README.md", root / "INTEGRATION.md",
                    root / "ORBIT_GRAPH_PRECOMPUTE.md",
                    root / "IMPLICIT_ORBIT_GRAPH.md", root / "bench.c",
                    root / "make_isolated_manifest.py", root / "make_graph_inputs.py",
                    root / "check_orbit_graph_panel.py", Path(__file__),
                    root / "screen_implicit_orbit_graph.py",
                    root / "implicit-orbit-graph-screen.json",
                    root / "make_tau_wide_graph.py", root / "make_tau_wide_orbits.py",
                    root / "run.py", bench, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "implicit_orbit_graph_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths},
              "results": results}
    (root / "implicit-orbit-graph-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(results),
                      "models": models}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
