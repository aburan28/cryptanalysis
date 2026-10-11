#!/usr/bin/env python3
"""Replay frozen two-representative inputs and retain operation diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields
from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from run import omega_eigenvalues, representatives
from screen_table_aware import plan


ARMS = ("fused-hot-batch128", "fused-hot-adapt2-batch128")
OPERATIONS = ("triples", "adds", "rotations", "output_inversions",
              "fallbacks", "prep_triples", "prep_adds", "prep_rotations",
              "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
              "online_scratch_bytes")


def check(bench, root):
    fixture_path = root / "adapt2-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    indexes, patterns = build_atlas()
    orbit_ids, _, _ = build_orbits()
    selected = set(json.loads(
        (root / "hot-orbit-screen.json").read_text())["selected_orbit_ids"])
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "adapt2-inputs" / case["scalar_file"]
        if hashlib.sha256(scalar_path.read_bytes()).hexdigest() != case[
                "scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        order = ARMS if index % 2 == 0 else ARMS[::-1]
        completed = {}
        for arm in order:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            run = subprocess.run(command, text=True, capture_output=True)
            record = {"arm": arm, "command": command,
                      "returncode": run.returncode, "stdout": run.stdout,
                      "stderr": run.stderr}
            if run.returncode == 0:
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
            completed[arm] = record
        if all(completed[arm].get("verified") for arm in ARMS):
            baseline = completed[ARMS[0]]["operations"]
            candidate = completed[ARMS[1]]["operations"]
            blocks = 6 if case["curve"]["name"] == "j0-56" else 4
            lambdas = [int(fields(completed[arm]["stdout"])["endo_lambda"])
                       for arm in ARMS]
            scalar_data = scalar_path.read_bytes()
            scalars = [int.from_bytes(scalar_data[i:i + 8], "little")
                       for i in range(0, len(scalar_data), 8)]
            predicted_baseline = predicted_candidate = selected_second = 0
            omega_lambda = (case["curve"]["order"] - lambdas[0]) % case[
                "curve"]["order"]
            if (lambdas[0] == lambdas[1] and omega_lambda in
                    omega_eigenvalues(case["curve"]["order"])):
                for scalar in scalars:
                    choices = sorted(enumerate(representatives(
                        case["curve"]["order"], omega_lambda, scalar)),
                        key=lambda row: (row[1][0], row[0]))
                    first = plan(choices[0][1][1], choices[0][1][2],
                                 blocks, indexes, patterns, orbit_ids,
                                 selected)
                    second = plan(choices[1][1][1], choices[1][1][2],
                                  blocks, indexes, patterns, orbit_ids,
                                  selected)
                    choose_second = second[2] and second[0] < first[0]
                    predicted_baseline += first[0]
                    predicted_candidate += second[0] if choose_second else first[0]
                    selected_second += choose_second
            prediction_matches = (
                lambdas[0] == lambdas[1] and
                predicted_baseline == baseline["adds"] and
                predicted_candidate == candidate["adds"])
            same_setup = all(baseline[key] == candidate[key] for key in
                             ("prep_triples", "prep_adds", "prep_rotations",
                              "prep_layer_inversions", "prep_bytes",
                              "prep_temp_heap_bytes", "online_scratch_bytes"))
            saved = baseline["adds"] - candidate["adds"]
            passed = (prediction_matches and baseline["adds"] > 0 and saved * 100 >=
                      baseline["adds"] * 3 and same_setup and
                      baseline["prep_adds"] == blocks * 2048 and
                      candidate["triples"] == baseline["triples"] == 0 and
                      candidate["output_inversions"] ==
                      baseline["output_inversions"] == 32)
            saving_fraction = f"{saved / baseline['adds']:.6f}"
        else:
            passed = False
            saved = saving_fraction = None
            prediction_matches = False
            predicted_baseline = predicted_candidate = selected_second = None
        results.append({"id": case["id"], "verified": bool(passed),
                        "saved_additions": saved,
                        "saved_addition_fraction": saving_fraction,
                        "selector_prediction_matches": prediction_matches,
                        "predicted_baseline_adds": predicted_baseline,
                        "predicted_candidate_adds": predicted_candidate,
                        "selected_second_representative": selected_second,
                        "runs": completed})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt",
                    repo / "scripts" / "isolated_bench.py",
                    repo / "tests" / "test_curve.c",
                    root / "bench.c", root / "README.md",
                    root / "INTEGRATION.md", root / "TABLE_AWARE_HOT.md",
                    root / "screen_table_aware.py",
                    root / "table-aware-screen.json",
                    root / "make_adapt_inputs.py",
                    root / "make_isolated_manifest.py", Path(__file__),
                    root / "HOT_ORBIT_TABLE.md",
                    root / "screen_hot_orbits.py",
                    root / "hot-orbit-screen.json",
                    root / "make_tau8_hot.py",
                    root / "make_hot_inputs.py",
                    root / "check_hot_panel.py",
                    root / "make_residue_atlas.py",
                    root / "make_tau8_orbits.py",
                    root / "make_tau8_pairs.py",
                    root / "run.py",
                    repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau4_residue_atlas.h",
                    repo / "src" / "generated" / "tau8_pair_map.h",
                    repo / "src" / "generated" / "tau8_orbit_map.h",
                    repo / "src" / "generated" / "tau8_hot_map.h",
                    bench, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "adapt2_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(
                  fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(repo)): hashlib.sha256(
                      path.read_bytes()).hexdigest() for path in source_paths},
              "results": results}
    (root / "adapt2-panel.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "saved_addition_fraction":
                          [row["saved_addition_fraction"] for row in results]},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
