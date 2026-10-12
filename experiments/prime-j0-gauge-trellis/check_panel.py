#!/usr/bin/env python3
"""Serial held-out gauge-trellis panel with independent frozen digests."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = (
    "CMakeLists.txt", "src/ec_tau.c", "src/ec_tau_internal.h",
    "tests/test_joint_tau.c", "experiments/prime-j0-joint-tau-stream/bench.c",
    "src/generated/tau_gauge_trellis.h",
    "experiments/prime-j0-gauge-trellis/make_trellis_table.py",
    "experiments/prime-j0-gauge-trellis/make_inputs.py",
    "experiments/prime-j0-gauge-trellis/check_panel.py",
    "experiments/prime-j0-gauge-trellis/PROTOCOL.md",
)
COUNTERS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "doubles",
    "mixed_adds", "full_adds", "rotations", "output_inversions",
    "overlaps", "fused_hits", "recode_attempts", "pair_scores",
    "selected_changed", "lattice_points_checked", "gauge_selected",
    "digit_rotations", "gauge_transitions", "final_rotations",
    "gauge_table_lookups", "gauge_model_rotations",
)
MODES = ("joint", "paired2", "paired2-gauge", "paired2-trellis",
         "paired2-trellis", "paired2-gauge", "paired2", "joint")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench, mode, curve, path):
    command = [str(bench), mode, curve, str(path)]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    record = {"mode": mode, "curve": curve, "command": command,
              "returncode": process.returncode, "stdout": process.stdout,
              "stderr": process.stderr, "fields": None}
    if process.returncode == 0:
        fields = {}
        for part in process.stdout.strip().split():
            if part.count("=") != 1:
                record["parse_error"] = part
                return record
            key, value = part.split("=", 1)
            if key in fields:
                record["parse_error"] = f"duplicate {key}"
                return record
            fields[key] = value
        record["fields"] = fields
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bench", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bench = args.bench.resolve()
    input_path = HERE / "inputs.json"
    inputs = json.loads(input_path.read_text())
    result = {
        "schema": 1, "kind": "held-out-algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "input_manifest_sha256": sha(input_path),
        "source_sha256": {name: sha(REPO / name) for name in SOURCE},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        if (inputs.get("schema") != 1 or inputs.get("count") != 1024 or
                inputs.get("oracle") != "independent_affine_scalar_and_mix64_digest"):
            raise ValueError("unexpected independent fixture")
        prior = [json.loads((HERE.parent / name / "inputs.json").read_text())
                 for name in ("prime-j0-joint-tau-stream", "prime-j0-hot-orbit-table",
                              "prime-j0-paired-lattice-stream",
                              "prime-j0-unit-gauge-stream")]
        for curve, spec in inputs["curves"].items():
            path = HERE / spec["file"]
            if sha(path) != spec["sha256"] or any(
                    spec["sha256"] == entry["curves"][curve]["sha256"] for entry in prior):
                raise ValueError(f"held-out input SHA mismatch: {curve}")
            trials = [run(bench, mode, curve, path) for mode in MODES]
            result["trials"].extend(trials)
            for trial in trials:
                fields = trial["fields"]
                if trial["returncode"] or fields is None:
                    raise ValueError(f"failed trial: {curve} {trial['mode']}")
                for key, expected in (
                    ("curve", curve), ("mode", trial["mode"]), ("count", "1024"),
                    ("base_x", str(spec["base_x"])), ("base_y", str(spec["base_y"])),
                    ("partner_x", str(spec["partner_x"])),
                    ("partner_y", str(spec["partner_y"])),
                    ("input_digest", spec["generic_input_digest"]),
                    ("output_digest", spec["generic_output_digest"]),
                    ("verified", "1"),
                ):
                    if fields.get(key) != expected:
                        raise ValueError(f"{curve} {trial['mode']}: {key} mismatch")
            def counts(mode):
                pair = [trial["fields"] for trial in trials if trial["mode"] == mode]
                if any(pair[0][key] != pair[1][key] for key in COUNTERS):
                    raise ValueError(f"nondeterministic counters: {curve} {mode}")
                return {key: int(pair[0][key]) for key in COUNTERS}
            joint, two, gauge, trellis = (counts(mode) for mode in
                                          ("joint", "paired2", "paired2-gauge",
                                           "paired2-trellis"))
            for key in ("precomp_bytes", "prep_tau", "prep_doubles",
                        "prep_mixed_adds", "prep_rotations", "prep_inversions",
                        "output_inversions"):
                if len({arm[key] for arm in (joint, two, gauge, trellis)}) != 1:
                    raise ValueError(f"unpaired {key}: {curve}")
            for key in ("recode_attempts", "pair_scores", "lattice_points_checked"):
                if len({arm[key] for arm in (two, gauge, trellis)}) != 1:
                    raise ValueError(f"extra recoding or scoring: {curve} {key}")
            for key in ("tau_steps", "mixed_adds", "full_adds", "selected_changed"):
                if two[key] != trellis[key]:
                    raise ValueError(f"unpaired stream choice: {curve} {key}")
            if two["gauge_selected"] != 0 or not 0 <= gauge["gauge_selected"] <= 1024:
                raise ValueError(f"invalid gauge count: {curve}")
            if trellis["rotations"] != (trellis["digit_rotations"] +
                                        trellis["gauge_transitions"] +
                                        trellis["final_rotations"]):
                raise ValueError(f"trellis rotation accounting: {curve}")
            if trellis["rotations"] > gauge["rotations"] or trellis["rotations"] > two["rotations"]:
                raise ValueError(f"trellis lost rotation objective: {curve}")
            if trellis["gauge_model_rotations"] < trellis["rotations"]:
                raise ValueError(f"invalid trellis model: {curve}")
            if trellis["gauge_table_lookups"] <= 0:
                raise ValueError(f"missing trellis lookups: {curve}")
            for arm in (joint, two, gauge, trellis):
                arm["field_operation_model"] = (6 * arm["tau_steps"] +
                                                 11 * arm["mixed_adds"] +
                                                 arm["rotations"])
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "arms": {"joint": joint, "paired2": two,
                         "paired2-gauge": gauge, "paired2-trellis": trellis},
                "gauge_rotations_saved_vs_paired2": two["rotations"] - gauge["rotations"],
                "gauge_model_saved_vs_paired2": (two["field_operation_model"] -
                                                  gauge["field_operation_model"]),
                "trellis_rotations_saved_vs_paired2": two["rotations"] - trellis["rotations"],
                "trellis_rotations_saved_vs_global_gauge": gauge["rotations"] - trellis["rotations"],
                "verified": True,
            }
        result["pass"] = True
    except (KeyError, ValueError, OSError) as exc:
        result["error"] = str(exc)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pass": result["pass"], "curves": result["curves"],
                      "error": result.get("error")}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
