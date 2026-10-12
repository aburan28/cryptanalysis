#!/usr/bin/env python3
"""Compare direct and graph preparation on frozen public points."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields
from check_tapered_panel import setup_model
from make_tau_wide_graph import recipes
from make_tau_wide_orbits import ID_BITS, build
from run import TABLE
from screen_tapered_residue import SCHEDULE_32, SCHEDULE_56


DIRECT = "tapered-residue-orbit-batch128"
GRAPH = "tapered-residue-graph-batch128"
ARMS = (DIRECT, GRAPH)
COUNTERS = ("triples", "adds", "rotations", "output_inversions",
            "fallbacks", "second_recodes", "steered_blocks",
            "static_map_bytes", "recipe_bytes", "prep_triples",
            "prep_adds", "prep_rotations", "prep_layer_inversions",
            "prep_bytes", "prep_temp_heap_bytes", "online_scratch_bytes",
            "point_entries", "point_table_bytes")
ONLINE = ("triples", "adds", "rotations", "output_inversions",
          "fallbacks", "second_recodes", "steered_blocks", "online_scratch_bytes")
SHARED_PREP = ("prep_triples", "prep_layer_inversions", "prep_bytes",
               "prep_temp_heap_bytes", "point_entries", "point_table_bytes",
               "static_map_bytes")


def graph_model(schedule, all_recipes):
    adds = rotations = 0
    offset = 0
    for width in schedule:
        for parent, slot, position, depth in all_recipes[width]:
            if depth == 0:
                continue
            digit = TABLE[(slot // 9, slot % 9)]
            rotations += (digit[3] + (offset + position) // 2) % 3 != 0
            if depth > 1:
                adds += 1
                rotations += (parent >> ID_BITS) % 3 != 0
        offset += width
    return {"prep_adds": adds, "prep_rotations": rotations,
            "recipe_bytes": sum(len(all_recipes[width]) * 8 for width in set(schedule))}


def check(bench, root):
    fixture_path = root / "orbit-graph-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if len(fixture["cases"]) != 8 or fixture["point_multiples"] != [1, 37, 101, 103]:
        raise ValueError("unexpected graph preparation fixture")
    atlases = {width: build(width) for width in (8, 10, 12)}
    graphs = {width: recipes(atlas) for width, atlas in atlases.items()}
    predictions = {}
    for name, schedule in (("glv-j0-32", SCHEDULE_32), ("j0-56", SCHEDULE_56)):
        predictions[name] = {"direct": setup_model(schedule, atlases),
                             "graph": graph_model(schedule, graphs)}
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
            direct = runs[DIRECT]["operations"]
            graph = runs[GRAPH]["operations"]
            expected = predictions[case["curve"]["name"]]
            direct_model, graph_pred = expected["direct"], expected["graph"]
            passed = (all(direct[key] == graph[key] for key in ONLINE + SHARED_PREP) and
                      all(direct[key] == value for key, value in direct_model.items()) and
                      all(graph[key] == value for key, value in graph_pred.items()) and
                      direct["recipe_bytes"] == 0 and
                      graph["prep_triples"] == 1134 and
                      graph["prep_adds"] < direct["prep_adds"] and
                      graph["prep_rotations"] < direct["prep_rotations"] and
                      graph["fallbacks"] == 0 and
                      graph["output_inversions"] == 32)
        results.append({"id": case["id"], "verified": passed,
                        "predicted": predictions[case["curve"]["name"]], "runs": runs})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
                    repo / "tests" / "test_curve.c", repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau_wide_orbits.h",
                    repo / "src" / "generated" / "tau_wide_graph.h",
                    root / "README.md", root / "INTEGRATION.md",
                    root / "TAPERED_RESIDUE_ORBITS.md", root / "ORBIT_GRAPH_PRECOMPUTE.md",
                    root / "bench.c", root / "make_graph_inputs.py", Path(__file__),
                    root / "make_tau_wide_graph.py", root / "orbit-graph-screen.json",
                    root / "make_tau_wide_orbits.py", root / "make_isolated_manifest.py",
                    root / "check_tapered_panel.py", root / "run.py", bench,
                    bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "orbit_graph_preparation_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths},
              "results": results}
    (root / "orbit-graph-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "cases": len(results),
                      "setup_adds": {name: [model["direct"]["prep_adds"],
                                            model["graph"]["prep_adds"]]
                                     for name, model in predictions.items()}}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
