#!/usr/bin/env python3
"""Replay frozen gated dual carry-steering inputs and verify operations."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields
from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from make_tau8_pairs import make_map
from make_tau8_steer import build_map
from run import omega_eigenvalues, representatives
from screen_carry_steer import steered
from screen_gated_dual_steer import requires_second


ARMS = ("fused-hot-steer-batch128", "fused-hot-steer-gated2-batch128")
OPERATIONS = ("triples", "adds", "rotations", "output_inversions",
              "fallbacks", "second_recodes", "steered_blocks", "static_map_bytes",
              "prep_triples", "prep_adds", "prep_rotations",
              "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
              "online_scratch_bytes")
SETUP = ("prep_triples", "prep_adds", "prep_rotations",
         "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
         "online_scratch_bytes")


def predict(scalars, order, lambda_omega, blocks, selected, indexes,
            patterns, pair_map, orbit_ids, hot):
    first_adds = gated_adds = first_substitutions = gated_substitutions = 0
    gated_recodes = first_span_fallbacks = gated_span_fallbacks = 0
    for scalar in scalars:
        choices = sorted(enumerate(representatives(order, lambda_omega, scalar)),
                         key=lambda row: (row[1][0], row[0]))
        _, a, b = choices[0][1]
        first = steered(a, b, blocks, selected, indexes, patterns,
                        pair_map, orbit_ids, hot)
        trigger = requires_second(a, b, blocks, selected, indexes,
                                  patterns, pair_map, orbit_ids, hot)
        chosen = first
        if trigger:
            _, second_a, second_b = choices[1][1]
            second = steered(second_a, second_b, blocks, selected, indexes,
                             patterns, pair_map, orbit_ids, hot)
            if second[1] and (not first[1] or second[0] < first[0]):
                chosen = second
            gated_recodes += 1
        first_adds += first[0]
        gated_adds += chosen[0]
        first_substitutions += first[2] if first[1] else 0
        gated_substitutions += chosen[2] if chosen[1] else 0
        first_span_fallbacks += not first[1]
        gated_span_fallbacks += not chosen[1]
    return {"first_adds": first_adds, "gated_adds": gated_adds,
            "first_substitutions": first_substitutions,
            "gated_substitutions": gated_substitutions,
            "gated_second_recodes": gated_recodes,
            "first_span_fallbacks": first_span_fallbacks,
            "gated_span_fallbacks": gated_span_fallbacks}


def check(bench, root):
    fixture_path = root / "gated2-steer-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    selected = build_map(root / "hot-orbit-screen.json")
    indexes, patterns = build_atlas()
    pair_map = make_map()
    orbit_ids, _, _ = build_orbits()
    hot = set(json.loads((root / "hot-orbit-screen.json").read_text())[
        "selected_orbit_ids"])
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "gated2-steer-inputs" / case["scalar_file"]
        data = scalar_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        scalars = [int.from_bytes(data[i:i + 8], "little")
                   for i in range(0, len(data), 8)]
        if len(scalars) != case["scalars"]:
            raise ValueError("frozen scalar count mismatch")
        completed = {}
        for arm in ARMS[index % 2:] + ARMS[:index % 2]:
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
        passed = False
        if all(completed[arm].get("verified") for arm in ARMS):
            actual = [completed[arm]["operations"] for arm in ARMS]
            lambdas = [int(fields(completed[arm]["stdout"])["endo_lambda"])
                       for arm in ARMS]
            subgroup_order = case["curve"]["order"]
            omega_lambda = (subgroup_order - lambdas[0]) % subgroup_order
            if len(set(lambdas)) == 1 and omega_lambda in omega_eigenvalues(subgroup_order):
                blocks = 6 if case["curve"]["name"] == "j0-56" else 4
                predicted = predict(scalars, subgroup_order, omega_lambda,
                                    blocks, selected, indexes, patterns,
                                    pair_map, orbit_ids, hot)
                first_adds, gated_adds = actual[0]["adds"], actual[1]["adds"]
                nonzero = sum(scalar != 0 for scalar in scalars)
                passed = (first_adds == predicted["first_adds"] and
                          gated_adds == predicted["gated_adds"] and
                          actual[0]["steered_blocks"] == predicted["first_substitutions"] and
                          actual[1]["steered_blocks"] == predicted["gated_substitutions"] and
                          actual[1]["second_recodes"] == predicted["gated_second_recodes"] and
                          actual[0]["second_recodes"] == 0 and
                          actual[0]["static_map_bytes"] ==
                          actual[1]["static_map_bytes"] == 13122 and
                          all(actual[0][key] == actual[1][key] for key in SETUP) and
                          all(item["triples"] == 0 and
                              item["output_inversions"] == 32 for item in actual) and
                          (first_adds - gated_adds) * 100 >= first_adds and
                          actual[1]["second_recodes"] * 10 <= nonzero * 3)
        results.append({"id": case["id"], "verified": passed,
                        "predicted": predicted,
                        "saved_addition_fraction":
                            f"{(completed[ARMS[0]]['operations']['adds'] - completed[ARMS[1]]['operations']['adds']) / completed[ARMS[0]]['operations']['adds']:.6f}"
                            if all(completed[arm].get("verified") for arm in ARMS) else None,
                        "runs": completed})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
                    repo / "tests" / "test_curve.c", root / "README.md",
                    root / "INTEGRATION.md", root / "GATED_DUAL_STEER.md",
                    root / "CARRY_STEERED_TAU8.md", root / "bench.c",
                    root / "make_gated2_steer_inputs.py", Path(__file__),
                    root / "screen_gated_dual_steer.py",
                    root / "gated-dual-steer-screen.json",
                    root / "runpod-isolation-preflight-20261004.json",
                    root / "screen_carry_steer.py", root / "make_tau8_steer.py",
                    root / "make_isolated_manifest.py", root / "hot-orbit-screen.json",
                    root / "make_residue_atlas.py", root / "make_tau8_orbits.py",
                    root / "make_tau8_pairs.py", root / "run.py",
                    repo / "src" / "ec_tau.c", repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau8_steer_map.h",
                    repo / "src" / "generated" / "tau8_hot_map.h",
                    bench, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "gated_dual_steer_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in source_paths},
              "results": results}
    (root / "gated2-steer-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "saved_addition_fraction": [row["saved_addition_fraction"]
                                                  for row in results]}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
