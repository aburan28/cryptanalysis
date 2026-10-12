#!/usr/bin/env python3
"""Replay the prospective tapered orbit panel with an independent operation model."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_gated2_steer_panel import predict
from check_panel import fields
from make_residue_atlas import build as build_atlas
from make_tau8_orbits import build_orbits
from make_tau8_pairs import make_map
from make_tau8_steer import build_map
from make_tau_wide_orbits import build as build_wide
from run import omega_eigenvalues, recode, representatives
from screen_tapered_residue import SCHEDULE_32, SCHEDULE_56, plan


REFERENCE = "fused-hot-steer-gated2-batch128"
CANDIDATE = "tapered-residue-orbit-batch128"
ARMS = (REFERENCE, CANDIDATE)
COUNTERS = ("triples", "adds", "rotations", "output_inversions",
            "fallbacks", "second_recodes", "steered_blocks",
            "static_map_bytes", "prep_triples", "prep_adds",
            "prep_rotations", "prep_layer_inversions", "prep_bytes",
            "prep_temp_heap_bytes", "online_scratch_bytes", "point_entries",
            "point_table_bytes")


def setup_model(schedule, atlases):
    additions = rotations = 0
    offset = 0
    for width in schedule:
        for a, b in atlases[width]["corrections"]:
            digits = recode(a, b)
            if len(digits) > width:
                raise AssertionError("correction exceeds its prepared window")
            nonzero = 0
            for position, digit in enumerate(digits):
                if digit is None:
                    continue
                nonzero += 1
                rotations += (digit[3] + (offset + position) // 2) % 3 != 0
            additions += max(nonzero - 1, 0)
        offset += width
    entries = sum(len(atlases[width]["reps"]) for width in schedule)
    static_bytes = sum(atlases[width]["modulus"] ** 2 * 4 +
                       len(atlases[width]["reps"]) * 4
                       for width in set(schedule))
    return {"prep_adds": additions, "prep_rotations": rotations,
            "prep_layer_inversions": len(schedule) + 1,
            "point_entries": entries, "point_table_bytes": entries * 32,
            "static_map_bytes": static_bytes,
            "prep_temp_heap_bytes": max(len(atlases[width]["reps"])
                                        for width in schedule) * 32,
            "online_scratch_bytes": 4096}


def candidate_model(scalars, order, omega_lambda, schedule, atlases):
    adds = rotations = fallbacks = 0
    for scalar in scalars:
        choices = sorted(enumerate(representatives(order, omega_lambda, scalar)),
                         key=lambda row: (row[1][0], row[0]))
        _, a, b = choices[0][1]
        result = plan(a, b, schedule, atlases)
        if not result[2]:
            fallbacks += 1
            continue
        adds += result[0]
        rotations += result[1]
    return {"adds": adds, "rotations": rotations, "fallbacks": fallbacks}


def check(bench, root):
    fixture_path = root / "tapered-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture["seed"] != 20271217 or len(fixture["cases"]) != 4:
        raise ValueError("unexpected prospective workload")
    atlases = {width: build_wide(width) for width in (8, 10, 12)}
    selected = build_map(root / "hot-orbit-screen.json")
    indexes, patterns = build_atlas()
    pair_map = make_map()
    orbit_ids, _, _ = build_orbits()
    hot = set(json.loads((root / "hot-orbit-screen.json").read_text())[
        "selected_orbit_ids"])
    rows = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "tapered-inputs" / case["scalar_file"]
        data = scalar_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != case["scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        scalars = [int.from_bytes(data[i:i + 8], "little")
                   for i in range(0, len(data), 8)]
        if len(scalars) != case["scalars"] or len(scalars) != 4096:
            raise ValueError("unexpected scalar count")
        runs = {}
        for arm in ARMS[index % 2:] + ARMS[:index % 2]:
            command = [str(bench), arm, case["curve"]["name"],
                       str(case["point_index"]), str(scalar_path)]
            result = subprocess.run(command, text=True, capture_output=True)
            record = {"arm": arm, "command": command,
                      "returncode": result.returncode, "stdout": result.stdout,
                      "stderr": result.stderr, "verified": False}
            if result.returncode == 0:
                got = fields(result.stdout)
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
                    record["operations"] = {key: int(got[key]) for key in COUNTERS}
                    record["timings_exploratory_ms"] = {
                        key: got[key] for key in ("online_ms", "prep_ms", "verify_ms")}
            runs[arm] = record
        passed = False
        predicted = None
        saved = None
        if all(runs[arm]["verified"] for arm in ARMS):
            reference = runs[REFERENCE]["operations"]
            candidate = runs[CANDIDATE]["operations"]
            lambdas = [int(fields(runs[arm]["stdout"])["endo_lambda"])
                       for arm in ARMS]
            order = case["curve"]["order"]
            omega_lambda = (order - lambdas[0]) % order
            if len(set(lambdas)) == 1 and omega_lambda in omega_eigenvalues(order):
                large = case["curve"]["name"] == "j0-56"
                schedule = SCHEDULE_56 if large else SCHEDULE_32
                old = predict(scalars, order, omega_lambda, 6 if large else 4,
                              selected, indexes, patterns, pair_map, orbit_ids, hot)
                new = candidate_model(scalars, order, omega_lambda, schedule, atlases)
                setup = setup_model(schedule, atlases)
                predicted = {"reference": old, "candidate": new, "setup": setup}
                saved = (reference["adds"] - candidate["adds"]) / reference["adds"]
                passed = (reference["adds"] == old["gated_adds"] and
                          reference["second_recodes"] == old["gated_second_recodes"] and
                          reference["steered_blocks"] == old["gated_substitutions"] and
                          all(candidate[key] == value for key, value in new.items()) and
                          all(candidate[key] == value for key, value in setup.items()) and
                          candidate["prep_bytes"] >= candidate["point_table_bytes"] and
                          candidate["prep_bytes"] - candidate["point_table_bytes"] == 38064 and
                          candidate["prep_triples"] == 1134 and
                          candidate["triples"] == candidate["second_recodes"] ==
                          candidate["steered_blocks"] == 0 and
                          reference["output_inversions"] ==
                          candidate["output_inversions"] == 32 and
                          candidate["fallbacks"] == 0 and
                          saved >= (0.25 if large else 0.02))
        rows.append({"id": case["id"], "verified": passed,
                     "saved_addition_fraction": f"{saved:.6f}" if saved is not None else None,
                     "predicted": predicted, "runs": runs})
    repo = root.parents[1]
    paths = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
             repo / "tests" / "test_curve.c", repo / "src" / "ec_tau.c",
             repo / "src" / "ec_tau_internal.h",
             repo / "src" / "generated" / "tau_wide_orbits.h",
             root / "README.md", root / "INTEGRATION.md",
             root / "TAPERED_RESIDUE_ORBITS.md", root / "bench.c",
             root / "make_tapered_inputs.py", Path(__file__),
             root / "screen_tapered_residue.py", root / "tapered-residue-screen.json",
             root / "make_tau_wide_orbits.py", root / "make_isolated_manifest.py",
             root / "make_residue_atlas.py", root / "make_tau8_orbits.py",
             root / "make_tau8_pairs.py", root / "make_tau8_steer.py",
             root / "screen_carry_steer.py", root / "screen_gated_dual_steer.py",
             root / "check_gated2_steer_panel.py", root / "run.py",
             root / "hot-orbit-screen.json", bench, bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "tapered_residue_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {str(path.relative_to(repo)):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in paths},
              "results": rows}
    (root / "tapered-panel.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in rows)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "saved_addition_fraction": [row["saved_addition_fraction"]
                                                  for row in rows]}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
