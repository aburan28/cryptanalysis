#!/usr/bin/env python3
"""Replay gated-selector inputs and check actual selector and point operations."""

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
from screen_gated_table_aware import score


ARMS = ("fused-hot-batch128", "fused-hot-adapt2-batch128",
        "fused-hot-gated-batch128")
OPERATIONS = ("triples", "adds", "rotations", "output_inversions",
              "fallbacks", "second_recodes", "prep_triples", "prep_adds",
              "prep_rotations", "prep_layer_inversions", "prep_bytes",
              "prep_temp_heap_bytes", "online_scratch_bytes")
SETUP = ("prep_triples", "prep_adds", "prep_rotations",
         "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
         "online_scratch_bytes")


def predict(scalars, order, lambda_omega, blocks, indexes, patterns,
            orbit_ids, hot):
    additions = [0, 0, 0]
    second_recodes = [0, 0, 0]
    full_chosen = gated_chosen = 0
    for scalar in scalars:
        choices = sorted(enumerate(representatives(
            order, lambda_omega, scalar)), key=lambda row: (
                row[1][0], row[0]))
        first = score(choices[0][1][1], choices[0][1][2], blocks,
                      indexes, patterns, orbit_ids, hot)
        second = score(choices[1][1][1], choices[1][1][2], blocks,
                       indexes, patterns, orbit_ids, hot)
        choose_second = second[2] and second[0] < first[0]
        trigger = scalar != 0 and (not first[2] or first[3] > 0)
        additions[0] += first[0]
        additions[1] += second[0] if choose_second else first[0]
        additions[2] += second[0] if trigger and choose_second else first[0]
        second_recodes[1] += scalar != 0
        second_recodes[2] += trigger
        full_chosen += choose_second
        gated_chosen += trigger and choose_second
    return additions, second_recodes, full_chosen, gated_chosen


def check(bench, root):
    fixture_path = root / "gated-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    indexes, patterns = build_atlas()
    orbit_ids, _, _ = build_orbits()
    hot = set(json.loads((root / "hot-orbit-screen.json").read_text())[
        "selected_orbit_ids"])
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "gated-inputs" / case["scalar_file"]
        data = scalar_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        scalars = [int.from_bytes(data[i:i + 8], "little")
                   for i in range(0, len(data), 8)]
        order = ARMS[index % 3:] + ARMS[:index % 3]
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
        predicted = None
        if all(completed[arm].get("verified") for arm in ARMS):
            actual = [completed[arm]["operations"] for arm in ARMS]
            lambdas = [int(fields(completed[arm]["stdout"])["endo_lambda"])
                       for arm in ARMS]
            subgroup_order = case["curve"]["order"]
            omega_lambda = (subgroup_order - lambdas[0]) % subgroup_order
            if (len(set(lambdas)) == 1 and
                    omega_lambda in omega_eigenvalues(subgroup_order)):
                blocks = 6 if case["curve"]["name"] == "j0-56" else 4
                predicted = predict(scalars, subgroup_order, omega_lambda,
                                    blocks, indexes, patterns, orbit_ids, hot)
                predicted_adds, predicted_recodes, full_chosen, gated_chosen = predicted
                prediction_matches = all(
                    actual[i]["adds"] == predicted_adds[i] and
                    actual[i]["second_recodes"] == predicted_recodes[i]
                    for i in range(3))
            else:
                prediction_matches = False
            same_setup = all(
                actual[0][key] == actual[1][key] == actual[2][key]
                for key in SETUP)
            hot_adds, full_adds, gated_adds = [item["adds"]
                                                 for item in actual]
            full_saving = hot_adds - full_adds
            gated_saving = hot_adds - gated_adds
            nonzero = sum(scalar != 0 for scalar in scalars)
            passed = (
                prediction_matches and same_setup and full_saving > 0 and
                gated_saving * 100 >= hot_adds * 3 and
                gated_saving * 4 >= full_saving * 3 and
                actual[2]["second_recodes"] * 4 <= nonzero * 3 and
                actual[0]["prep_adds"] == blocks * 2048 and
                all(item["triples"] == 0 and
                    item["output_inversions"] == 32 for item in actual))
            retained = f"{gated_saving / full_saving:.6f}"
            second_fraction = f"{actual[2]['second_recodes'] / nonzero:.6f}"
        else:
            passed = prediction_matches = False
            full_saving = gated_saving = retained = second_fraction = None
            full_chosen = gated_chosen = None
        results.append({
            "id": case["id"], "verified": bool(passed),
            "selector_prediction_matches": prediction_matches,
            "predicted_adds": predicted[0] if predicted else None,
            "predicted_second_recodes": predicted[1] if predicted else None,
            "full_second_chosen": full_chosen,
            "gated_second_chosen": gated_chosen,
            "full_saved_adds": full_saving,
            "gated_saved_adds": gated_saving,
            "saving_retained": retained,
            "gated_second_recode_fraction": second_fraction,
            "runs": completed,
        })
    repo = root.parents[1]
    source_paths = [
        repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
        repo / "tests" / "test_curve.c",
        root / "README.md", root / "INTEGRATION.md",
        root / "GATED_TABLE_AWARE.md", root / "bench.c",
        root / "screen_gated_table_aware.py",
        root / "gated-table-aware-screen.json",
        root / "make_gated_inputs.py", root / "make_isolated_manifest.py",
        Path(__file__), root / "TABLE_AWARE_HOT.md",
        root / "screen_table_aware.py", root / "table-aware-screen.json",
        root / "make_adapt_inputs.py", root / "check_adapt_panel.py",
        root / "HOT_ORBIT_TABLE.md", root / "screen_hot_orbits.py",
        root / "hot-orbit-screen.json", root / "make_tau8_hot.py",
        root / "make_hot_inputs.py", root / "check_hot_panel.py",
        root / "make_residue_atlas.py", root / "make_tau8_orbits.py",
        root / "make_tau8_pairs.py", root / "run.py",
        repo / "src" / "ec_tau.c", repo / "src" / "ec_tau_internal.h",
        repo / "src" / "generated" / "tau4_residue_atlas.h",
        repo / "src" / "generated" / "tau8_pair_map.h",
        repo / "src" / "generated" / "tau8_orbit_map.h",
        repo / "src" / "generated" / "tau8_hot_map.h",
        bench, bench.parent / "CMakeCache.txt",
    ]
    report = {
        "schema": 1, "status": "gated_selector_operation_diagnostic_only",
        "cpu_timing_claim": None, "architecture": platform.machine(),
        "os": platform.platform(),
        "input_manifest_sha256": hashlib.sha256(
            fixture_path.read_bytes()).hexdigest(),
        "source_sha256": {
            str(path.relative_to(repo)): hashlib.sha256(
                path.read_bytes()).hexdigest() for path in source_paths},
        "results": results,
    }
    (root / "gated-panel.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({
        "status": report["status"], "verified": passed,
        "saving_retained": [row["saving_retained"] for row in results],
        "second_recode_fraction": [
            row["gated_second_recode_fraction"] for row in results],
    }, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
