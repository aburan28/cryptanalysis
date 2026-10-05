#!/usr/bin/env python3
"""Verify frozen orbit-folded tau outputs and retain raw diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from check_panel import fields


def check(bench, root):
    fixture_path = root / "orbit-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    results = []
    for index, case in enumerate(fixture["cases"]):
        scalar_path = root / "orbit-inputs" / case["scalar_file"]
        if hashlib.sha256(scalar_path.read_bytes()).hexdigest() != case[
                "scalar_file_sha256"]:
            raise ValueError(f"frozen scalar hash mismatch: {scalar_path}")
        arms = ("fused-batch128", "fused-orbit-batch128")
        if index % 2:
            arms = arms[::-1]
        completed = {}
        for arm in arms:
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
                            "base_x": case["base_x"],
                            "base_y": case["base_y"],
                            "input_digest": case["input_digest"],
                            "output_digest": case["expected_output_digest"],
                            "prep_repeats": "1", "verified": "1"}
                record["verified"] = all(got.get(key) == value
                                         for key, value in expected.items())
                if record["verified"]:
                    record["operations"] = {key: int(got[key]) for key in (
                        "triples", "adds", "rotations", "output_inversions",
                        "fallbacks", "prep_triples", "prep_adds",
                        "prep_rotations", "prep_layer_inversions",
                        "prep_bytes", "prep_temp_heap_bytes",
                        "online_scratch_bytes")}
            completed[arm] = record
        reference = completed["fused-batch128"]
        candidate = completed["fused-orbit-batch128"]
        ok = bool(reference.get("verified") and candidate.get("verified"))
        if ok:
            ref = reference["operations"]
            got = candidate["operations"]
            blocks = 6 if case["curve"]["name"] == "j0-56" else 4
            ok = (got["adds"] == ref["adds"] and
                  got["rotations"] > 0 and ref["rotations"] == 0 and
                  got["triples"] == ref["triples"] == 0 and
                  got["fallbacks"] == ref["fallbacks"] == 0 and
                  got["output_inversions"] == ref["output_inversions"] == 32
                  and got["prep_adds"] == blocks * 4860 and
                  ref["prep_adds"] == blocks * 29160 and
                  got["prep_bytes"] < ref["prep_bytes"] and
                  got["prep_triples"] == ref["prep_triples"] and
                  got["prep_layer_inversions"] == blocks + 1 and
                  got["online_scratch_bytes"] == ref[
                      "online_scratch_bytes"] == 4096)
        results.append({"id": case["id"], "verified": bool(ok),
                        "saved_prep_adds": (reference["operations"]["prep_adds"] -
                                            candidate["operations"]["prep_adds"])
                        if ok else None,
                        "saved_table_bytes": (reference["operations"]["prep_bytes"] -
                                              candidate["operations"]["prep_bytes"])
                        if ok else None, "runs": completed})
    repo = root.parents[1]
    source_paths = [repo / "CMakeLists.txt",
                    repo / "scripts" / "isolated_bench.py", root / "bench.c",
                    root / "make_orbit_inputs.py", root / "make_fused_inputs.py",
                    root / "make_tau8_orbits.py", root / "make_tau8_pairs.py",
                    root / "make_inputs.py", root / "check_panel.py",
                    root / "make_isolated_manifest.py",
                    root / "make_residue_atlas.py", root / "run.py",
                    root / "FUSED_TAU_PAIRS.md", root / "FUSED_TAU_ORBITS.md",
                    Path(__file__),
                    repo / "src" / "ec_tau.c",
                    repo / "src" / "ec_tau_internal.h",
                    repo / "src" / "generated" / "tau4_residue_atlas.h",
                    repo / "src" / "generated" / "tau8_pair_map.h",
                    repo / "src" / "generated" / "tau8_orbit_map.h", bench,
                    bench.parent / "CMakeCache.txt"]
    report = {"schema": 1, "status": "orbit_tau_operation_diagnostic_only",
              "cpu_timing_claim": None, "architecture": platform.machine(),
              "os": platform.platform(),
              "input_manifest_sha256": hashlib.sha256(
                  fixture_path.read_bytes()).hexdigest(),
              "source_sha256": {
                  str(path.relative_to(repo)):
                      hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths},
              "results": results}
    output = root / "orbit-panel.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    passed = all(item["verified"] for item in results)
    print(json.dumps({"status": report["status"], "cases": len(results),
                      "verified": passed,
                      "saved_prep_adds": [item["saved_prep_adds"]
                                          for item in results],
                      "saved_table_bytes": [item["saved_table_bytes"]
                                            for item in results]},
                     sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", type=Path, required=True)
    args = parser.parse_args()
    check(args.bench.resolve(), Path(__file__).resolve().parent)
