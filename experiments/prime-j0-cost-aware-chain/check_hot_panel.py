#!/usr/bin/env python3
"""Check fresh hot-orbit outputs and retain raw, nonisolated diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields


ARMS = ("pos-batch128", "fused-orbit-batch128", "fused-hot-batch128")
OPERATIONS = ("triples", "adds", "rotations", "output_inversions",
              "fallbacks", "prep_triples", "prep_adds", "prep_rotations",
              "prep_layer_inversions", "prep_bytes", "prep_temp_heap_bytes",
              "online_scratch_bytes")


def check(bench, root):
    fixture_path = root / "hot-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "hot-inputs" / case["scalar_file"]
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
            pos = completed[ARMS[0]]["operations"]
            full = completed[ARMS[1]]["operations"]
            hot = completed[ARMS[2]]["operations"]
            blocks = 6 if case["curve"]["name"] == "j0-56" else 4
            full_saving = pos["adds"] - full["adds"]
            hot_saving = pos["adds"] - hot["adds"]
            passed = (full_saving > 0 and hot_saving * 2 >= full_saving and
                      full["adds"] <= hot["adds"] < pos["adds"] and
                      hot["prep_adds"] == blocks * 2048 and
                      full["prep_adds"] == blocks * 4860 and
                      hot["prep_bytes"] < full["prep_bytes"] and
                      hot["fallbacks"] > 0 and full["fallbacks"] == 0 and
                      hot["triples"] == full["triples"] == pos["triples"] == 0
                      and hot["output_inversions"] == full[
                          "output_inversions"] == pos["output_inversions"] == 32
                      and hot["prep_layer_inversions"] == blocks + 1 and
                      hot["online_scratch_bytes"] == full[
                          "online_scratch_bytes"] == pos[
                              "online_scratch_bytes"] == 4096)
        else:
            passed = False
            full_saving = hot_saving = None
        results.append({"id": case["id"], "verified": bool(passed),
                        "full_saved_adds": full_saving,
                        "hot_saved_adds": hot_saving,
                        "retained_saved_adds":
                            f"{hot_saving / full_saving:.6f}"
                            if passed else None,
                        "runs": completed})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt",
                    repo / "scripts" / "isolated_bench.py", root / "bench.c",
                    root / "HOT_ORBIT_TABLE.md", root / "screen_hot_orbits.py",
                    root / "hot-orbit-screen.json", root / "make_tau8_hot.py",
                    root / "make_hot_inputs.py", root / "make_isolated_manifest.py",
                    Path(__file__),
                    root / "make_residue_atlas.py", root / "make_tau8_orbits.py",
                    root / "make_tau8_pairs.py", root / "run.py",
                    repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau4_residue_atlas.h",
                    repo / "src" / "generated" / "tau8_pair_map.h",
                    repo / "src" / "generated" / "tau8_orbit_map.h",
                    repo / "src" / "generated" / "tau8_hot_map.h", bench,
                    bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "hot_orbit_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "fallbacks_semantics":
                  "hot cold-block visits plus out-of-span scalar fallbacks",
              "input_manifest_sha256": hashlib.sha256(
                  fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(repo)):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    (root / "hot-panel.json").write_text(json.dumps(
        report, indent=2, sort_keys=True) + "\n")
    passed = all(row["verified"] for row in results)
    print(json.dumps({"status": report["status"], "verified": passed,
                      "retained_saved_adds": [row["retained_saved_adds"]
                                              for row in results]}, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
